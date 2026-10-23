"""PostgreSQL development adapter with serialized approval/version transactions."""

import re
from contextlib import contextmanager


class Row(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class Cursor:
    def __init__(self, cursor): self.cursor = cursor
    def fetchone(self):
        row = self.cursor.fetchone()
        return Row(row) if row is not None else None
    def fetchall(self): return [Row(row) for row in self.cursor.fetchall()]
    def __iter__(self): return iter(self.fetchall())


class Connection:
    def __init__(self, connection): self.connection = connection
    def execute(self, sql, params=None):
        if "INSERT OR IGNORE" in sql:
            sql = sql.replace("INSERT OR IGNORE", "INSERT") + " ON CONFLICT DO NOTHING"
        sql = sql.replace("?", "%s")
        return Cursor(self.connection.execute(sql, params))


def postgres_migration(sql):
    def trigger(match):
        name, table = match.group(1), match.group(2)
        return f"CREATE TRIGGER {name} BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION forbid_version_update();"
    sql = re.sub(r"CREATE TRIGGER (\w+) BEFORE UPDATE ON (\w+)\s+BEGIN.*?END;", trigger, sql, flags=re.S)
    sql = sql.replace("DROP TRIGGER transcript_versions_immutable;", "DROP TRIGGER transcript_versions_immutable ON transcript_versions;")
    return sql


class PostgresStore:
    def __init__(self, dsn, migrations):
        import psycopg
        from psycopg.rows import dict_row
        self.psycopg, self.dict_row, self.dsn = psycopg, dict_row, dsn
        with self.transaction() as con:
            con.execute("CREATE TABLE IF NOT EXISTS app_schema_version (id INTEGER PRIMARY KEY, version INTEGER NOT NULL)")
            con.execute("INSERT INTO app_schema_version VALUES (1,0) ON CONFLICT DO NOTHING")
            current = con.execute("SELECT version FROM app_schema_version WHERE id=1").fetchone()[0]
            if current > len(migrations): raise RuntimeError("Database schema is newer than this application")
            con.execute("""CREATE OR REPLACE FUNCTION forbid_version_update() RETURNS trigger AS $$
                BEGIN RAISE EXCEPTION 'Version bodies are immutable'; END; $$ LANGUAGE plpgsql""")
            for version, sql in enumerate(migrations, start=1):
                if version > current:
                    # No parameters: psycopg uses the multi-statement-capable simple protocol.
                    con.execute(postgres_migration(sql))
                    con.execute("UPDATE app_schema_version SET version=? WHERE id=1", (version,))

    @contextmanager
    def transaction(self):
        with self.psycopg.connect(self.dsn, row_factory=self.dict_row, connect_timeout=10) as raw:
            # A conservative development lock keeps the existing exact-version state
            # machine atomic. Replace with scoped locks only after concurrent tests.
            raw.execute("SELECT pg_advisory_xact_lock(714092311)")
            yield Connection(raw)
