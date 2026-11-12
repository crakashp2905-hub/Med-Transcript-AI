"""Read-only checks for local links, source references, API examples and tests."""

import ast
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
CODE_SPAN = re.compile(r"`([^`]+)`")
TEST_NAME = re.compile(r"\btest_[A-Za-z0-9_]+\b")
SOURCE_PATH = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:services|tests|apps|evaluation|scripts|docs|\.github)/"
    r"[A-Za-z0-9_./*{}<>-]+"
)
API_EXAMPLE = re.compile(
    r"^\s*(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(/\S+)", re.M | re.I
)
ROUTE_DECORATOR = {"get", "post", "put", "patch", "delete", "head", "options"}


def _markdown_files(root):
    return sorted(
        [root / "README.md", *((root / "docs").rglob("*.md"))],
        key=lambda p: p.as_posix(),
    )


def _slug(heading):
    heading = re.sub(r"[`*_~]", "", heading.strip().lower())
    heading = re.sub(r"[^\w\- ]", "", heading, flags=re.UNICODE)
    return re.sub(r"\s+", "-", heading.strip())


def _anchors(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    headings = {
        _slug(match.group(1))
        for match in re.finditer(r"^#{1,6}\s+(.+?)\s*#*\s*$", text, re.M)
    }
    explicit = set(re.findall(r"\bid=[\"']([^\"']+)[\"']", text, re.I))
    return headings | explicit


def _matches_path(root, target):
    target = unquote(target).replace("\\", "/").strip()
    target = re.split(r"::", target, maxsplit=1)[0]
    target = target.rstrip(".,:;!?)]}")
    if not target:
        return True
    path = Path(target)
    if path.is_absolute():
        return False
    if any(token in target for token in ("*", "<", ">", "{")):
        pattern = re.sub(r"<[^>]+>|\{[^}]+\}", "*", target)
        try:
            return any(root.glob(pattern))
        except (ValueError, OSError):
            return False
    resolved = (root / path).resolve()
    return resolved.is_relative_to(root) and (resolved.is_file() or resolved.is_dir())


def _api_routes(root):
    routes = set()
    for path in (root / "services").rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(
                    decorator.func, ast.Attribute
                ):
                    continue
                if (
                    decorator.func.attr.lower() not in ROUTE_DECORATOR
                    or not decorator.args
                ):
                    continue
                route = decorator.args[0]
                if isinstance(route, ast.Constant) and isinstance(route.value, str):
                    routes.add((decorator.func.attr.upper(), route.value))
    return routes


def _normalize_route(path):
    return re.sub(r"\{[^}/]+\}", "{}", urlsplit(path).path.rstrip("/") or "/")


def scan(root="."):
    root = Path(root).resolve()
    markdown = [path for path in _markdown_files(root) if path.is_file()]
    texts = {
        path: path.read_text(encoding="utf-8", errors="replace") for path in markdown
    }
    results = []
    for path, text in texts.items():
        for raw_target in LINK.findall(text):
            target = raw_target.strip().strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme.lower() in ("http", "https", "mailto"):
                continue
            local_target = unquote(parsed.path)
            resolved = (path.parent / local_target).resolve() if local_target else path
            exists = resolved.is_relative_to(root) and (
                resolved.is_file() or resolved.is_dir()
            )
            fragment_ok = True
            if exists and parsed.fragment:
                if re.fullmatch(r"L\d+(?:-L?\d+)?", parsed.fragment):
                    line = int(re.match(r"L(\d+)", parsed.fragment).group(1))
                    fragment_ok = line <= len(
                        resolved.read_text(
                            encoding="utf-8", errors="replace"
                        ).splitlines()
                    )
                elif resolved.suffix.lower() == ".md":
                    fragment_ok = parsed.fragment in _anchors(resolved)
                else:
                    fragment_ok = False
            results.append(
                {
                    "source": path.relative_to(root).as_posix(),
                    "target": raw_target,
                    "status": "pass" if exists and fragment_ok else "missing",
                    "reason": None
                    if exists and fragment_ok
                    else "target_missing"
                    if not exists
                    else "anchor_missing",
                }
            )

    source_references = []
    test_files = {path.stem for path in (root / "tests").rglob("test_*.py")}
    test_functions = set()
    for path in (root / "tests").rglob("test_*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        test_functions.update(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        )

    for path, text in texts.items():
        prose = re.sub(r"https?://\S+", "", text)
        for span in CODE_SPAN.findall(prose):
            for reference in SOURCE_PATH.findall(span):
                reference = reference.rstrip(".,:;!?)]}")
                exists = _matches_path(root, reference)
                source_references.append(
                    {
                        "source": path.relative_to(root).as_posix(),
                        "target": reference,
                        "status": "pass" if exists else "missing",
                    }
                )
    test_references = []
    for path, text in texts.items():
        for name in sorted(set(TEST_NAME.findall(text))):
            exists = name in test_functions or name in test_files
            test_references.append(
                {
                    "source": path.relative_to(root).as_posix(),
                    "target": name,
                    "status": "pass" if exists else "missing",
                }
            )

    route_catalog = _api_routes(root)
    api_examples = []
    for path, text in texts.items():
        for method, target in API_EXAMPLE.findall(text):
            matches = any(
                method.upper() == actual_method
                and _normalize_route(target) == _normalize_route(actual_path)
                for actual_method, actual_path in route_catalog
            )
            api_examples.append(
                {
                    "source": path.relative_to(root).as_posix(),
                    "method": method.upper(),
                    "path": target,
                    "status": "pass" if matches else "missing",
                }
            )

    readme = texts.get(root / "README.md", "")
    claims = {
        "wer_gate_5_percent": "5%" in readme,
        "clinical_release_blocked": "Real-patient release is not authorized" in readme,
        "failures_visible": "remain visible" in readme or "failures" in readme,
    }
    broken_links = [item for item in results if item["status"] != "pass"]
    broken_source_references = [
        item for item in source_references if item["status"] != "pass"
    ]
    broken_test_references = [
        item for item in test_references if item["status"] != "pass"
    ]
    broken_api_examples = [item for item in api_examples if item["status"] != "pass"]
    return {
        "schema_version": "doc_integrity_v2",
        "links": results,
        "broken_links": broken_links,
        "source_references": source_references,
        "broken_source_references": broken_source_references,
        "test_references": test_references,
        "broken_test_references": broken_test_references,
        "api_examples": api_examples,
        "broken_api_examples": broken_api_examples,
        "claims": claims,
        "status": "pass"
        if all(claims.values())
        and not any(
            (
                broken_links,
                broken_source_references,
                broken_test_references,
                broken_api_examples,
            )
        )
        else "fail",
        "limitations": "Local links, referenced source/test paths and static API route examples only; external URLs are not fetched.",
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = scan()
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "links": len(report["links"]),
                "broken": len(report["broken_links"]),
                "source_refs": len(report["source_references"]),
                "broken_source_refs": len(report["broken_source_references"]),
                "test_refs": len(report["test_references"]),
                "broken_test_refs": len(report["broken_test_references"]),
                "api_examples": len(report["api_examples"]),
                "broken_api_examples": len(report["broken_api_examples"]),
            }
        )
    )
