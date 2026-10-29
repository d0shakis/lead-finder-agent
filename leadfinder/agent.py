"""The Lead Finder pipeline: discover -> enrich -> analyze -> rank."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from leadfinder.enrich import enrich_all
from leadfinder.llm import get_analyzer
from leadfinder.models import Lead
from leadfinder.sources import osm

ProgressFn = Callable[[str, float], None]


@dataclass
class SearchResult:
    area_name: str
    leads: list[Lead] = field(default_factory=list)


async def find_leads(
    term: str,
    city: str,
    limit: int = 30,
    provider: str = "auto",
    model: str | None = None,
    skip_websites: bool = False,
    llm_concurrency: int = 4,
    progress: ProgressFn | None = None,
) -> SearchResult:
    report = progress or (lambda msg, frac: None)
    analyzer = get_analyzer(provider, model)

    async with httpx.AsyncClient() as client:
        report(f"Searching OpenStreetMap for '{term}' in {city}...", 0.05)
        area, businesses = await osm.search(client, term, city, limit)
        report(f"Found {len(businesses)} businesses in {area.name}", 0.25)
        if not businesses:
            return SearchResult(area.name)

        if skip_websites:
            signals = [None] * len(businesses)
        else:
            with_site = sum(1 for b in businesses if b.website)
            report(f"Auditing {with_site} websites...", 0.3)
            signals = await enrich_all(client, businesses)

    leads = [Lead(business=b, signals=s) for b, s in zip(businesses, signals, strict=True)]
    sem = asyncio.Semaphore(llm_concurrency)
    done = 0

    async def analyze(lead: Lead) -> None:
        nonlocal done
        async with sem:
            lead.analysis = await analyzer.analyze(lead.business, lead.signals)
        done += 1
        report(f"Scored {done}/{len(leads)}: {lead.business.name}", 0.4 + 0.6 * done / len(leads))

    await asyncio.gather(*(analyze(l) for l in leads))
    leads.sort(key=lambda l: l.analysis.score if l.analysis else 0, reverse=True)
    report("Done", 1.0)
    return SearchResult(area.name, leads)
