import pytest

from leadfinder.sources import osm


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Every test gets an empty cache and no retry delay."""
    monkeypatch.setenv("LEADFINDER_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("LEADFINDER_NO_CACHE", raising=False)
    monkeypatch.setattr(osm, "RETRY_DELAY", 0)
