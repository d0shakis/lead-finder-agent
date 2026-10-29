import httpx
import respx

from leadfinder import cache
from leadfinder.sources import osm
from tests.test_osm import OVERPASS


def test_put_get_clear(monkeypatch):
    assert cache.get("ns", "k") is None
    cache.put("ns", "k", {"a": [1, 2]})
    assert cache.get("ns", "k") == {"a": [1, 2]}
    assert cache.get("ns", "k", ttl=-1) is None  # expired
    assert cache.clear() == 1
    assert cache.get("ns", "k") is None


def test_disabled(monkeypatch):
    monkeypatch.setenv("LEADFINDER_NO_CACHE", "1")
    cache.put("ns", "k", 1)
    assert cache.get("ns", "k") is None


@respx.mock
async def test_overpass_result_is_cached():
    route = respx.post(osm.OVERPASS_MIRRORS[0]).mock(return_value=httpx.Response(200, json=OVERPASS))
    async with httpx.AsyncClient() as client:
        first = await osm.run_overpass(client, "same query")
        second = await osm.run_overpass(client, "same query")
    assert first == second
    assert route.call_count == 1


@respx.mock
async def test_overpass_retries_another_round():
    route = respx.post(osm.OVERPASS_MIRRORS[0]).mock(
        side_effect=[httpx.Response(502), httpx.Response(200, json=OVERPASS)]
    )
    for url in osm.OVERPASS_MIRRORS[1:]:
        respx.post(url).mock(return_value=httpx.Response(504))
    async with httpx.AsyncClient() as client:
        elements = await osm.run_overpass(client, "q")
    assert len(elements) == 4 and route.call_count == 2
