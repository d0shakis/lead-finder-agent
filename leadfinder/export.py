from __future__ import annotations

import csv
import json
from pathlib import Path

from leadfinder.models import Lead


def to_csv(leads: list[Lead], path: Path) -> None:
    rows = [l.to_row() for l in leads]
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel reads UTF-8
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def to_json(leads: list[Lead], path: Path) -> None:
    path.write_text(json.dumps([l.model_dump() for l in leads], ensure_ascii=False, indent=2), encoding="utf-8")


def save(leads: list[Lead], path: Path) -> None:
    (to_json if path.suffix.lower() == ".json" else to_csv)(leads, path)
