import csv
import json

import httpx
import respx

from leadfinder.agent import find_leads
from leadfinder.export import save
from leadfinder.sources import osm
from tests.test_enrich import GOOD_HTML
from tests.test_osm import NOMINATIM, OVERPASS


@respx.mock
async def test_find_leads_pipeline(tmp_path):
    respx.get(osm.NOMINATIM_URL).mock(return_value=httpx.Response(200, json=NOMINATIM))
    respx.post(osm.OVERPASS_URL).mock(return_value=httpx.Response(200, json=OVERPASS))
    respx.get("http://pipepros.gr").mock(return_value=httpx.Response(200, text=GOOD_HTML))

    steps = []
    result = await find_leads("plumber", "Thessaloniki", provider="rules", progress=lambda m, f: steps.append(f))

    assert result.area_name == "Thessaloniki"
    assert [l.business.name for l in result.leads] == ["Aqua Fix", "Pipe Pros"]  # no site ranks first
    assert steps[-1] == 1.0 and steps == sorted(steps)

    csv_path, json_path = tmp_path / "l.csv", tmp_path / "l.json"
    save(result.leads, csv_path)
    save(result.leads, json_path)
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
    assert rows[0]["name"] == "Aqua Fix" and rows[1]["email"] == "info@pipepros.gr"
    assert json.loads(json_path.read_text(encoding="utf-8"))[1]["signals"]["has_booking"] is True
