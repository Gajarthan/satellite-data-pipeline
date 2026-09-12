from datetime import datetime, timezone
from pathlib import Path

from src.stac_pipeline import build_search_payload, load_geometry, utc_window


def test_load_geometry_from_feature(tmp_path: Path):
    path = tmp_path / "aoi.geojson"
    path.write_text('{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[80.0,9.5],[80.1,9.5],[80.1,9.6],[80.0,9.5]]]}}', encoding="utf-8")
    assert load_geometry(path)["type"] == "Polygon"


def test_utc_window():
    now = datetime(2026, 9, 12, 0, 0, 0, tzinfo=timezone.utc)
    start, end = utc_window(5, now=now)
    assert start == "2026-09-07T00:00:00Z"
    assert end == "2026-09-12T00:00:00Z"


def test_build_search_payload():
    geometry = {"type":"Polygon","coordinates":[[[80.0,9.5],[80.1,9.5],[80.1,9.6],[80.0,9.5]]]}
    payload = build_search_payload(geometry, "sentinel-2-l2a", "2026-09-07T00:00:00Z", "2026-09-12T00:00:00Z", 20, 10)
    assert payload["collections"] == ["sentinel-2-l2a"]
    assert payload["query"]["eo:cloud_cover"]["lt"] == 20
    assert payload["limit"] == 10
    assert payload["sortby"][0]["direction"] == "desc"
