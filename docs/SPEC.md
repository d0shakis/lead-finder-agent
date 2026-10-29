# Lead Finder Agent — Spec

## Goal
Given a business type and a city (e.g. "plumbers in Thessaloniki"), find local businesses,
inspect their web presence, and use an LLM to score how likely each one is to benefit from
CRM / automation services. Export ranked leads to CSV/JSON.

Portfolio project: must run with zero API keys (OpenStreetMap + rule-based scoring),
and get smarter when an LLM provider is configured.

## Pipeline
1. **Discover** — Nominatim geocodes the city to a bounding area; Overpass API queries OSM
   for matching tags. `categories.py` maps friendly terms ("plumber", "dentist", "gym") to OSM tags.
   Unknown terms fall back to a name regex search.
2. **Enrich** — for businesses with a website: fetch homepage (async, timeout, concurrency limit)
   and extract signals: HTTPS, response time, viewport meta (mobile), contact form, booking widget,
   chat widget, social links, emails, phone, page title/description, text excerpt.
3. **Analyze** — `Analyzer` interface returning `LeadAnalysis` (score 0-100, problems, opportunities,
   pitch). Providers: `rules` (default, offline), `claude`, `openai`, `ollama`. LLM output is
   validated JSON; on failure falls back to rules.
4. **Export** — sorted by score to CSV / JSON.

## Interfaces
- CLI (typer): `leadfinder search "plumber" --city "Thessaloniki" --limit 30 --provider rules -o leads.csv`
  and `leadfinder categories`.
- Streamlit app (`app.py`): form, progress, results table, map, CSV download.

## Non-goals
Scraping beyond the homepage, email sending, storing data, bypassing robots/rate limits.

## Etiquette
Custom User-Agent, 1 req/s to Nominatim, single Overpass query per search, website fetch
concurrency 5.
