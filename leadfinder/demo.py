"""Bundled sample results, so the app can be explored without hitting the live OSM servers."""

from __future__ import annotations

import json
from importlib import resources

from leadfinder.agent import SearchResult
from leadfinder.models import Lead

DEMO_TERM = "dentist"
DEMO_CITY = "Thessaloniki"


def load_demo() -> SearchResult:
    raw = resources.files("leadfinder.data").joinpath("demo_leads.json").read_text(encoding="utf-8")
    leads = [Lead.model_validate(item) for item in json.loads(raw)]
    leads.sort(key=lambda l: l.analysis.score if l.analysis else 0, reverse=True)
    return SearchResult(DEMO_CITY, leads)
