import httpx
import pytest
import respx

from leadfinder.sources import osm
from leadfinder.sources.categories import resolve

NOMINATIM = [
    {
        "osm_type": "relation",
        "osm_id": "123",
        "name": "Thessaloniki",
        "display_name": "Thessaloniki, Greece",
        "boundingbox": ["40.5", "40.7", "22.8", "23.0"],
    }
]
OVERPASS = {
    "elements": [
        {
            "type": "node",
            "id": 1,
            "lat": 40.6,
            "lon": 22.9,
            "tags": {
                "name": "Pipe Pros",
                "craft": "plumber",
                "website": "pipepros.gr",
                "phone": "+30 2310 000000",
                "addr:street": "Egnatia",
                "addr:housenumber": "10",
            },
        },
        {
            "type": "way",
            "id": 2,
            "center": {"lat": 40.61, "lon": 22.91},
            "tags": {"name": "Pipe Pros", "craft": "plumber"},
        },  # duplicate name
        {"type": "node", "id": 3, "lat": 40.62, "lon": 22.92, "tags": {"craft": "plumber"}},  # no name
        {
            "type": "way",
            "id": 4,
            "center": {"lat": 40.63, "lon": 22.93},
            "tags": {"name": "Aqua Fix", "craft": "plumber", "contact:email": "hi@aquafix.gr"},
        },
    ]
}


def test_resolve_aliases_and_plurals():
    assert resolve("Plumbers")[0] == "plumber"
    assert resolve("plumbing")[1] == [("craft", "plumber")]
    assert resolve("dentists")[0] == "dentist"
    assert resolve("underwater basket weaving") == ("underwater basket weaving", [])


def test_build_query_known_and_unknown():
    area = osm.Area("X", 3600000123, (0, 0, 1, 1))
    _, q = osm.build_query("plumber", area, 10)
    assert "area(id:3600000123)->.searchArea;" in q
    assert 'nwr["craft"="plumber"](area.searchArea);' in q
    assert q.endswith("out center tags 10;")

    bbox_area = osm.Area("X", None, (1.0, 2.0, 3.0, 4.0))
    _, q = osm.build_query('tattoo "studio"', bbox_area, 5)
    assert 'nwr["name"~"tattoo studio",i](1.0,2.0,3.0,4.0);' in q


def test_parse_elements_dedupes_and_normalizes():
    businesses = osm.parse_elements(OVERPASS["elements"], "plumber")
    assert [b.name for b in businesses] == ["Pipe Pros", "Aqua Fix"]
    pipe = businesses[0]
    assert pipe.website == "http://pipepros.gr"
    assert pipe.address == "Egnatia 10"
    assert pipe.osm_id == "node/1"
    assert businesses[1].email == "hi@aquafix.gr"
    assert businesses[1].lat == 40.63


@respx.mock
async def test_search_end_to_end():
    respx.get(osm.NOMINATIM_URL).mock(return_value=httpx.Response(200, json=NOMINATIM))
    route = respx.post(osm.OVERPASS_URL).mock(return_value=httpx.Response(200, json=OVERPASS))
    async with httpx.AsyncClient() as client:
        area, businesses = await osm.search(client, "plumbers", "Thessaloniki", 20)
    assert area.area_id == 3_600_000_123
    assert len(businesses) == 2
    assert b"craft" in route.calls[0].request.content


@respx.mock
async def test_overpass_falls_back_to_mirror():
    respx.post(osm.OVERPASS_MIRRORS[0]).mock(return_value=httpx.Response(502))
    respx.post(osm.OVERPASS_MIRRORS[1]).mock(return_value=httpx.Response(200, json=OVERPASS))
    async with httpx.AsyncClient() as client:
        elements = await osm.run_overpass(client, "q")
    assert len(elements) == 4


@respx.mock
async def test_overpass_all_mirrors_fail():
    for url in osm.OVERPASS_MIRRORS:
        respx.post(url).mock(return_value=httpx.Response(504))
    async with httpx.AsyncClient() as client:
        with pytest.raises(osm.OverpassError, match="All Overpass servers failed"):
            await osm.run_overpass(client, "q")
