"""Supervised local development worker; contains no client or hosted-provider credentials."""

import argparse
import json
import os
import time
from pathlib import Path

from services.api.ingest import run_once as ingest_once
from services.asr.worker import run_once as asr_once
from services.api.storage import default_asset_root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.environ.get("MED_TRANSCRIPT_DB", "data/development.sqlite3"))
    parser.add_argument("--assets", default=os.environ.get("MED_TRANSCRIPT_ASSETS"))
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    assets = args.assets or default_asset_root(args.db)
    while True:
        try:
            for function in (ingest_once, asr_once):
                result = function(args.db, assets)
                if result:
                    print(json.dumps(result), flush=True)
        except Exception:
            print(json.dumps({"code": "worker_iteration_failed"}), flush=True)
        if args.once:
            return
        time.sleep(1)


if __name__ == "__main__":
    main()
