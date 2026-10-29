"""Discover businesses on OpenStreetMap via Nominatim (geocoding) and Overpass (search)."""

from __future__ import annotations

import asyncio
import re

import httpx

from leadfinder import cache
from leadfinder.models import Business
from leadfinder.sources.categories import resolve

USER_AGENT = "lead-finder-agent/0.1 (+https://github.com/lead-finder-agent)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Public Overpass servers are often overloaded; try mirrors in order.
OVERPASS_MIRRORS = [
    OVERPASS_URL,
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# Rounds through the mirror list, with a pause between rounds
OVERPASS_ROUNDS = 2
RETRY_DELAY = 3.0

# Overpass area ids are offset from the OSM object id
_AREA_OFFSET = {"relation": 3_600_000_000, "way": 2_400_000_000}


class GeocodeError(RuntimeError):
    pass


class OverpassError(RuntimeError):
    pass


class Area:
    """A searchable region: an Overpass area id, or a bounding box fallback."""

    def __init__(self, name: str, area_id: int | None, bbox: tuple[float, float, float, float]):
        self.name = name
        self.area_id = area_id
        self.bbox = bbox  # south, west, north, east

    def overpass_filter(self) -> str:
        if self.area_id is not None:
            return "(area.searchArea)"
        s, w, n, e = self.bbox
        return f"({s},{w},{n},{e})"

    def overpass_header(self) -> str:
        return f"area(id:{self.area_id})->.searchArea;" if self.area_id is not None else ""


async def geocode(client: httpx.AsyncClient, city: str) -> Area:
    key = city.strip().lower()
    results = cache.get("geocode", key, ttl=30 * 24 * 3600)
    if results is None:
        resp = await client.get(
            NOMINATIM_URL,
            params={"q": city, "format": "jsonv2", "limit": 10, "featureType": "settlement"},
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        results = resp.json()
        if results:
            cache.put("geocode", key, results)
    if not results:
        raise GeocodeError(f"Could not find a place called {city!r}")
    # Nominatim's first hit isn't always the famous one (e.g. "Larissa" -> Missouri);
    # prefer the most important match.
    r = max(results, key=lambda x: float(x.get("importance") or 0))
    s, n, w, e = (float(x) for x in r["boundingbox"])
    offset = _AREA_OFFSET.get(r.get("osm_type", ""))
    area_id = offset + int(r["osm_id"]) if offset else None
    name = (r.get("name") or r.get("display_name", city).split(",")[0]).strip()
    return Area(name, area_id, (s, w, n, e))


def build_query(term: str, area: Area, limit: int) -> tuple[str, str]:
    """Build the Overpass QL query. Returns (canonical_category, query)."""
    category, tags = resolve(term)
    flt = area.overpass_filter()
    if tags:
        selectors = "".join(f'nwr["{k}"="{v}"]{flt};' for k, v in tags)
    else:
        # Unknown category: search business names (case-insensitive)
        safe = re.sub(r'["\\]', "", term)
        selectors = f'nwr["name"~"{safe}",i]{flt};'
    query = f"[out:json][timeout:25];{area.overpass_header()}({selectors});out center tags {limit};"
    return category, query


def _address(tags: dict) -> str:
    street = " ".join(p for p in (tags.get("addr:street", ""), tags.get("addr:housenumber", "")) if p)
    parts = [street, tags.get("addr:postcode", ""), tags.get("addr:city", "")]
    return ", ".join(p for p in parts if p) or tags.get("addr:full", "")


def _normalize_url(url: str) -> str:
    url = url.strip().split(";")[0].strip()
    if url and not re.match(r"^https?://", url, re.I):
        url = "http://" + url
    return url


def parse_elements(elements: list[dict], category: str) -> list[Business]:
    out: list[Business] = []
    seen: set[str] = set()
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("brand")
        if not name:
            continue
        key = name.lower()
        if key in seen:  # same business mapped as both node and building
            continue
        seen.add(key)
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        out.append(
            Business(
                osm_id=f"{el['type']}/{el['id']}",
                name=name,
                category=category,
                lat=lat,
                lon=lon,
                address=_address(tags),
                phone=tags.get("phone") or tags.get("contact:phone", ""),
                email=tags.get("email") or tags.get("contact:email", ""),
                website=_normalize_url(tags.get("website") or tags.get("contact:website") or tags.get("url", "")),
                opening_hours=tags.get("opening_hours", ""),
            )
        )
    return out


async def search(client: httpx.AsyncClient, term: str, city: str, limit: int = 30) -> tuple[Area, list[Business]]:
    area = await geocode(client, city)
    category, query = build_query(term, area, limit)
    return area, parse_elements(await run_overpass(client, query), category)


async def run_overpass(client: httpx.AsyncClient, query: str) -> list[dict]:
    cached = cache.get("overpass", query)
    if cached is not None:
        return cached
    errors = []
    for attempt in range(OVERPASS_ROUNDS):
        if attempt:
            await asyncio.sleep(RETRY_DELAY * attempt)
        for url in OVERPASS_MIRRORS:
            try:
                resp = await client.post(url, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=35)
                resp.raise_for_status()
                elements = resp.json().get("elements", [])
                cache.put("overpass", query, elements)
                return elements
            except (httpx.HTTPError, ValueError) as e:
                errors.append(f"{httpx.URL(url).host}: {e.__class__.__name__}")
    errors = list(dict.fromkeys(errors))
    raise OverpassError("All Overpass servers failed (" + "; ".join(errors) + "). Try again in a minute.")
