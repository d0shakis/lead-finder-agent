import httpx
import respx
from typer.testing import CliRunner

from leadfinder.cli import app
from leadfinder.sources import osm
from tests.test_osm import NOMINATIM, OVERPASS

runner = CliRunner()


@respx.mock
def test_search_command_writes_csv(tmp_path):
    respx.get(osm.NOMINATIM_URL).mock(return_value=httpx.Response(200, json=NOMINATIM))
    respx.post(osm.OVERPASS_URL).mock(return_value=httpx.Response(200, json=OVERPASS))
    respx.get("http://pipepros.gr").mock(return_value=httpx.Response(404))
    out = tmp_path / "leads.csv"

    result = runner.invoke(app, ["search", "plumber", "--city", "Thessaloniki", "-p", "rules", "-o", str(out)])

    assert result.exit_code == 0, result.output
    assert "Pipe Pros" in result.output and "Saved 2 leads" in result.output
    assert out.read_text(encoding="utf-8-sig").startswith("score,name")


@respx.mock
def test_search_command_reports_server_outage():
    respx.get(osm.NOMINATIM_URL).mock(return_value=httpx.Response(200, json=NOMINATIM))
    for url in osm.OVERPASS_MIRRORS:
        respx.post(url).mock(return_value=httpx.Response(503))

    result = runner.invoke(app, ["search", "plumber", "--city", "Thessaloniki", "-p", "rules"])

    assert result.exit_code == 1
    assert "All Overpass servers failed" in result.output


def test_unknown_provider_exit_code():
    result = runner.invoke(app, ["search", "plumber", "--city", "X", "-p", "gemini"])
    assert result.exit_code == 2


def test_demo_command(tmp_path):
    out = tmp_path / "demo.json"
    result = runner.invoke(app, ["demo", "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert "Demo:" in result.output and out.exists()
