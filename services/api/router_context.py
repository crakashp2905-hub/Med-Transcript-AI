"""Explicit capabilities shared by bounded API routers; no global database state."""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, ContextManager
from services.asr.profiles import ASRProfile


@dataclass(frozen=True)
class ApiServices:
    database: Callable[[], ContextManager[Any]]
    identity: Callable[..., Any]
    encounter: Callable[..., Any]
    audit: Callable[..., None]
    replay: Callable[..., Any]
    remember: Callable[..., None]
    require_processing: Callable[..., None]
    upload_row: Callable[..., Any]
    require_live_upload: Callable[..., None]
    assets: Path
    profiles: dict[str, ASRProfile]
