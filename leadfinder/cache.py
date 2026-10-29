"""Tiny JSON disk cache so repeated searches don't hammer the free OSM servers."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

DEFAULT_TTL = 24 * 3600


def cache_dir() -> Path:
    return Path(os.getenv("LEADFINDER_CACHE_DIR", Path.home() / ".cache" / "leadfinder"))


def enabled() -> bool:
    return os.getenv("LEADFINDER_NO_CACHE", "") not in ("1", "true", "yes")


def _path(namespace: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    return cache_dir() / namespace / f"{digest}.json"


def get(namespace: str, key: str, ttl: int = DEFAULT_TTL) -> Any | None:
    if not enabled():
        return None
    path = _path(namespace, key)
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if time.time() - entry.get("ts", 0) > ttl:
        return None
    return entry["value"]


def put(namespace: str, key: str, value: Any) -> None:
    if not enabled():
        return
    path = _path(namespace, key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"ts": time.time(), "value": value}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # caching is best effort


def clear() -> int:
    """Delete all cached entries. Returns how many files were removed."""
    removed = 0
    if cache_dir().exists():
        for f in cache_dir().rglob("*.json"):
            f.unlink(missing_ok=True)
            removed += 1
    return removed
