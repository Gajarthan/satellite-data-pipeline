# Daily Satellite Data Pipeline

Starter repository for a daily **Sentinel-2 Level-2A catalogue monitoring pipeline** using the Copernicus Data Space Ecosystem (CDSE) STAC API.

## What it does

- Runs daily with GitHub Actions
- Can also run manually
- Reads an AOI from GeoJSON
- Queries the current CDSE STAC endpoint
- Filters by cloud cover and lookback period
- Detects scene IDs not seen before
- Writes compact scene metadata to `data/`
- Stores state between runs
- Uploads each run as an Actions artifact
- Commits changed state/results back to the repo
- No Copernicus login is required for this catalogue-discovery stage

> Current scope: metadata discovery. Raster download, NDVI, flood detection, and change detection are the next phases.

## Architecture

```text
GitHub Actions schedule
        |
        v
config/aoi.geojson
        |
        v
Copernicus STAC API
        |
        v
Sentinel-2 L2A search
        |
        +--> cloud filter
        +--> compare previous IDs
        |
        v
data/latest_items.json
data/new_items.json
data/state.json
data/run_summary.md
```

## Default schedule

Every day at **06:10 Asia/Colombo**.

## Current API

```text
https://stac.dataspace.copernicus.eu/v1/
```

Collection:

```text
sentinel-2-l2a
```

Documentation: https://documentation.dataspace.copernicus.eu/APIs/STAC.html

## Project structure

```text
.github/workflows/satellite-monitor.yml
config/aoi.geojson
scripts/fetch_latest.py
src/stac_pipeline.py
tests/test_stac_pipeline.py
data/.gitkeep
.env.example
requirements.txt
```

## Local setup

```bash
python -m venv .venv
pip install -r requirements.txt
pytest -q
python scripts/fetch_latest.py
```

## Configuration

| Variable | Default |
|---|---|
| `STAC_API_URL` | `https://stac.dataspace.copernicus.eu/v1` |
| `STAC_COLLECTION` | `sentinel-2-l2a` |
| `AOI_FILE` | `config/aoi.geojson` |
| `LOOKBACK_DAYS` | `5` |
| `MAX_CLOUD_COVER` | `25` |
| `RESULT_LIMIT` | `20` |
| `DATA_DIR` | `data` |
| `REQUEST_TIMEOUT` | `60` |

The included AOI is only a **Northern Sri Lanka demo polygon**. Replace it with the actual customer/site AOI.

## Create the GitHub repo

The connected GitHub integration available in this chat can write to existing repositories but cannot create a brand-new repository. On your machine, the fastest route is GitHub CLI:

```bash
gh repo create Gajarthan/satellite-data-pipeline \
  --private \
  --source=. \
  --remote=origin \
  --push
```

Or create an empty private repo named `satellite-data-pipeline` and then:

```bash
git init
git add .
git commit -m "Initial satellite monitoring pipeline"
git branch -M main
git remote add origin git@github.com:Gajarthan/satellite-data-pipeline.git
git push -u origin main
```

## Next phases

1. **Raster acquisition** — authenticated CDSE asset downloads, object storage, checksums.
2. **NDVI** — B04 + B08 processing, AOI clipping, previous-scene comparison.
3. **Flood intelligence** — Sentinel-1 GRD, radar water/change detection.
4. **Commercial platform** — multiple customer AOIs, PostGIS, alerts, dashboard, PDF reports, subscriptions.

## Production note

Do not store large Sentinel raster products in GitHub. Keep only metadata/state here and place raster assets in object storage.
