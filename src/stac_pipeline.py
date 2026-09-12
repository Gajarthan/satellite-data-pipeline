from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

DEFAULT_STAC_API = "https://stac.dataspace.copernicus.eu/v1"
DEFAULT_COLLECTION = "sentinel-2-l2a"


@dataclass(frozen=True)
class Settings:
    stac_api_url: str
    collection: str
    aoi_file: Path
    lookback_days: int
    max_cloud_cover: float
    result_limit: int
    data_dir: Path
    request_timeout: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            stac_api_url=os.getenv("STAC_API_URL", DEFAULT_STAC_API).rstrip("/"),
            collection=os.getenv("STAC_COLLECTION", DEFAULT_COLLECTION),
            aoi_file=Path(os.getenv("AOI_FILE", "config/aoi.geojson")),
            lookback_days=int(os.getenv("LOOKBACK_DAYS", "5")),
            max_cloud_cover=float(os.getenv("MAX_CLOUD_COVER", "25")),
            result_limit=int(os.getenv("RESULT_LIMIT", "20")),
            data_dir=Path(os.getenv("DATA_DIR", "data")),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "60")),
        )


def load_geometry(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    object_type = payload.get("type")

    if object_type == "Feature":
        geometry = payload.get("geometry")
    elif object_type == "FeatureCollection":
        features = payload.get("features", [])
        if len(features) != 1:
            raise ValueError("FeatureCollection must contain exactly one feature.")
        geometry = features[0].get("geometry")
    else:
        geometry = payload

    if not isinstance(geometry, dict) or "type" not in geometry or "coordinates" not in geometry:
        raise ValueError("AOI file does not contain a valid GeoJSON geometry.")

    return geometry


def utc_window(lookback_days: int, now: datetime | None = None) -> tuple[str, str]:
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(days=lookback_days)
    return (
        start.isoformat(timespec="seconds").replace("+00:00", "Z"),
        now.isoformat(timespec="seconds").replace("+00:00", "Z"),
    )


def build_search_payload(geometry, collection, start, end, max_cloud_cover, limit):
    return {
        "collections": [collection],
        "intersects": geometry,
        "datetime": f"{start}/{end}",
        "query": {"eo:cloud_cover": {"lt": max_cloud_cover}},
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
        "limit": limit,
    }


def query_stac(settings: Settings, geometry: dict[str, Any]) -> dict[str, Any]:
    start, end = utc_window(settings.lookback_days)
    payload = build_search_payload(
        geometry,
        settings.collection,
        start,
        end,
        settings.max_cloud_cover,
        settings.result_limit,
    )
    response = requests.post(
        f"{settings.stac_api_url}/search",
        json=payload,
        timeout=settings.request_timeout,
        headers={
            "Accept": "application/geo+json, application/json",
            "User-Agent": "daily-satellite-data-pipeline/0.1",
        },
    )
    response.raise_for_status()
    body = response.json()
    if body.get("type") != "FeatureCollection":
        raise RuntimeError("Unexpected STAC response: expected FeatureCollection.")
    return body


def _link_href(item: dict[str, Any], rel: str) -> str | None:
    for link in item.get("links", []):
        if link.get("rel") == rel:
            return link.get("href")
    return None


def compact_item(item: dict[str, Any]) -> dict[str, Any]:
    props = item.get("properties", {})
    return {
        "id": item.get("id"),
        "collection": item.get("collection"),
        "datetime": props.get("datetime"),
        "cloud_cover": props.get("eo:cloud_cover"),
        "platform": props.get("platform"),
        "constellation": props.get("constellation"),
        "mgrs_tile": props.get("mgrs:tile"),
        "bbox": item.get("bbox"),
        "self_href": _link_href(item, "self"),
    }


def load_previous_ids(state_file: Path) -> set[str]:
    if not state_file.exists():
        return set()
    try:
        payload = json.loads(state_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    return {x for x in payload.get("seen_item_ids", []) if x}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_summary(path: Path, settings: Settings, total_items: int, new_items: list[dict[str, Any]], run_at: str) -> None:
    lines = [
        "# Daily Satellite Catalogue Run", "",
        f"- Run time (UTC): `{run_at}`",
        f"- Collection: `{settings.collection}`",
        f"- Lookback: `{settings.lookback_days}` days",
        f"- Cloud cover threshold: `< {settings.max_cloud_cover}%`",
        f"- Matching scenes: **{total_items}**",
        f"- New-to-pipeline scenes: **{len(new_items)}**", "",
    ]
    if new_items:
        lines += ["## Newly discovered scenes", "", "| Scene ID | Acquisition time | Cloud cover |", "|---|---|---:|"]
        for item in new_items:
            cloud = item.get("cloud_cover")
            cloud_text = "n/a" if cloud is None else f"{cloud}%"
            lines.append(f"| `{item.get('id')}` | {item.get('datetime') or 'n/a'} | {cloud_text} |")
    else:
        lines += ["No newly discovered scenes in this run."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or Settings.from_env()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    geometry = load_geometry(settings.aoi_file)
    response = query_stac(settings, geometry)
    items = [compact_item(item) for item in response.get("features", [])]
    items = [item for item in items if item.get("id")]

    state_file = settings.data_dir / "state.json"
    previous_ids = load_previous_ids(state_file)
    new_items = [item for item in items if item["id"] not in previous_ids]
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    combined_ids = sorted(previous_ids | {item["id"] for item in items})

    write_json(settings.data_dir / "latest_items.json", {"run_at": run_at, "collection": settings.collection, "count": len(items), "items": items})
    write_json(settings.data_dir / "new_items.json", {"run_at": run_at, "count": len(new_items), "items": new_items})
    write_json(state_file, {"updated_at": run_at, "seen_item_ids": combined_ids})
    write_summary(settings.data_dir / "run_summary.md", settings, len(items), new_items, run_at)
    return {"run_at": run_at, "matching_items": len(items), "new_items": len(new_items)}
