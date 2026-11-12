"""Application services; offline behavior is explicit and inherited by child Python processes."""

import os

if os.getenv("STRICT_OFFLINE") == "1":
    os.environ["MED_TRANSCRIPT_OFFLINE"] = "1"

if os.getenv("MED_TRANSCRIPT_OFFLINE") == "1":
    from services.offline import install

    install()
