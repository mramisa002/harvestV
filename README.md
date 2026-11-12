# HarvestV — advisory backend and frontend integration package

The complete original frontend from `Harvest-V-main.zip` is now included and
connected to the backend. Start with **START_HERE.md** for the two-terminal
Windows setup. See `frontend/INTEGRATION.md` for the screen-by-screen wiring.

Farm profiles, text feedback and saved advisory snapshots now persist on the
server under an anonymous browser token. District/crop catalogs, conditions and
localized advisories are fetched from the API. A new database still needs NASA
history ingestion before it can return advice.

## Start on Windows

Use Python **3.12**. From this extracted folder in VS Code's PowerShell terminal:

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python -m app.seed
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/demo** for the diagnostic frontend or
**http://127.0.0.1:8000/docs** for interactive API documentation. Press **Ctrl+C**
in the terminal to stop. SQLite is the default local database; no Docker is
needed for this path. An empty cache deliberately returns HTTP 503 for advice.

In another terminal, fetch historical POWER data for one district first:

```powershell
cd backend
.venv\Scripts\python -m app.ingestion power --district chattogram --years 20
```

This makes one request per calendar-year chunk and can take time. It requests
an extra historical year to allow complete windows near the current date.
Omit `--district chattogram` to ingest all 64 districts. Run the same command
without `--years` daily to refresh the last 46 days. Jobs are idempotent: reruns
update the existing district/day/source row. Partial jobs keep completed chunks;
health reports an unsuccessful run until a full job succeeds.

## Included API

| Method | URL | Result |
| --- | --- | --- |
| GET | `/health` | Last successful source ingestion and recent job failures |
| GET | `/api/v1/districts` | 64 district slugs and approximate reference points |
| GET | `/api/v1/crops` | Wheat, mustard, lentil, potato; starter calendars |
| GET | `/api/v1/conditions?district=chattogram&days=30` | Cached observations, timestamps and age |
| GET | `/api/v1/advisory?district=chattogram&crop=wheat&lang=bn` | Bilingual GO/WAIT/AVOID decision support |

Unknown district: 404. Invalid crop, language or range: 422. Missing, incomplete,
or stale data: 503 with an explanation. The API never contacts NASA during an
advisory or conditions request. Browser-scoped writes require X-Device-Token;
see `frontend/INTEGRATION.md` and the interactive API docs.

## PostgreSQL and Docker

Install Docker Desktop separately, then from the project root:

```powershell
Copy-Item .env.example .env
# Edit POSTGRES_PASSWORD in .env before starting.
docker compose up --build -d db backend frontend
docker compose exec backend python -m app.ingestion power --district chattogram --years 20
```

After bootstrapping historical data, enable the daily POWER worker:

```powershell
docker compose --profile jobs up --build -d worker
```

The database persists in the `postgres_data` volume. `docker compose down` stops
services without deleting that data. PostGIS is not required: this version uses
district reference points, not polygon queries. For non-Docker PostgreSQL, set
`DATABASE_URL=postgresql://user:password@localhost:5432/harvestv` in `backend/.env`.
The bootstrap creates schema version 1; add explicit migrations before changing
an existing production database.

## Earthdata: implemented access, unfinished product pipelines

POWER fetching and cache ingestion are implemented. IMERG, SMAP and NDVI have
authenticated granule downloading, a configurable NetCDF/HDF5 point extractor,
and a validated normalized-data importer. **They are not complete automatic,
product-certified processing pipelines.** Product-version mappings, quality
flags, units, reprojection and aggregation need verification with real granules.
No Earthdata or NASA credentials were provided for live verification.

```powershell
cd backend
.venv\Scripts\python -m pip install -r requirements-earthdata.txt
# Put EARTHDATA_TOKEN in backend/.env, never in frontend/.env.local.
.venv\Scripts\python -m app.earthdata imerg-late --start 2026-11-01 --end 2026-11-10 --bbox 91.5 22.0 92.0 22.7 --out raw-earthdata/imerg
.venv\Scripts\python scripts/extract_grid.py --help
.venv\Scripts\python -m app.ingestion import path/to/normalized.json
```

`earthaccess` authenticates from environment variables. The acquisition command
loads `backend/.env`. Use `GPM_3IMERGDF` (Final), `GPM_3IMERGDL` (Late),
`SPL3SMP_E` (surface), `SPL4SMGP` (root zone), `MOD13Q1` or `VNP13A1` (NDVI).
MODIS projected/HDF4 tiles need a CRS-aware conversion; the generic extractor
rejects unsupported geographic grids. It requires explicit QA criteria and
decoded units, and refuses a distant or missing pixel. A rainfall rate is not
silently treated as a daily total. QA bit masks must be decoded according to the
specific product manual; do not assume that zero is always the only valid flag.

Normalized input is an array of records:

```json
[{"district_id":"chattogram","source":"smap","day":"2026-11-09",
  "source_timestamp":"2026-11-09T06:00:00+00:00","product":"SPL3SMP_E",
  "quality_checked":true,"values":{"sm_surface":0.28}}]
```

This JSON is a **format example, not real observations**. Import only extracted,
quality-checked measurements. Rain is mm/day, soil moisture is volumetric m³/m³,
and NDVI is already scaled to -1..1. The cache records observation time and
ingestion time separately. POWER observation timestamps represent day start,
not a verified publication timestamp.

## Scoring and honest limits

- `backend/config/crops.yaml` contains starter thresholds, weights and calendars.
  Every threshold is explicitly marked **TODO: agronomist review**. They are not
  supported by field validation or a claimed agronomic citation.
- Scores use recent observed rainfall, complete historical 14-day analogues
  from at least 20 prior years, approximate available-moisture estimates when
  possible, temperature suitability and crop calendars. Historical climate
  patterns are **not forecasts**. `app/forecast.py` supplies a future provider
  interface; no provider is connected.
- Future candidates reuse the last valid moisture index, explicitly labelled.
  Future rain and soil conditions are unknown. Current observed vetoes block
  today, not an asserted future weather event. No HIGH confidence is issued by
  this climatology-only, unvalidated version.
- Wilting-point/field-capacity normalization is relative available moisture,
  **not physical saturation**. Unknown soil estimates remain null. Missing
  soil contributions score conservatively as zero, lower confidence and block
  GO; zero contribution is not an invented observed moisture reading.
- Seed coordinates are approximate district-town points, **not official district
  centroids**. Agro-ecological zones and soil estimates are unknown, not made up.
  Replace these with reviewed district geometry/soil survey data before field use.
  Apply reviewed estimates with `python -m app.soil path/to/reviewed-soils.json`;
  the module docstring specifies the input fields and required survey citation.
- Windows are ranked disjoint periods of the configured minimum duration, using
  centered three-day smoothing; future candidates are provisional. Similar
  scores reduce confidence. Season calendars currently support non-wrapping
  date ranges; expand that before adding cross-year sowing calendars.
- English and Bangla reasons are templates. Bangla requires a native-speaker
  review before release. NDVI is excluded from live advice at the database-query
  level. No advice is a substitute for local agricultural extension officers (DAE).

## Tests and backtesting

```powershell
cd backend
.venv\Scripts\python -m unittest discover -s tests -v
# Optional, same unittest cases:
.venv\Scripts\python -m pytest tests
```

Tests use **synthetic** source-schema fixtures; no fixture is claimed to be a
recorded NASA response. They exercise pure scoring, vetoes, missing data,
freshness, idempotency, API handler behavior and Pydantic response contracts.
They do not require network sockets. HTTP transport, Docker/PostgreSQL,
Earthdata grids and the original Next.js build need integration checks in an
environment with their dependencies and source files.

For offline NDVI evaluation:

```powershell
.venv\Scripts\python scripts/backtest_ndvi.py --observations observations.csv --ndvi ndvi.csv --cutoffs cutoffs.csv --out reports/my-backtest
```

CSV column specifications are in the script docstring. `available_at` must be a
verified publication/availability timestamp with timezone. The evaluator only
uses observations available at each cutoff. Downloaded historical data without
availability metadata cannot establish a rigorous point-in-time result.
Green-up minus a lag is a proxy and 16-day composites have temporal uncertainty.
`reports/sample/` demonstrates reporting with synthetic data only. No validated
agricultural accuracy is claimed.

## Remaining work before a complete release

1. Run the Next.js production build and browser checks with npm dependencies
   installed. This environment could not download them because network DNS was
   unavailable. The original source and all assets are now present.
2. Verify product-specific Earthdata extraction with actual granules and schedule
   IMERG/SMAP/NDVI jobs. Only POWER currently has an automatic daily worker.
3. Replace approximate reference points and missing soil/AEZ data with reviewed
   datasets; calibrate and approve crop thresholds with agronomists.
4. Run real point-in-time backtests and Docker/PostgreSQL integration checks.

## Provider documentation

- https://power.larc.nasa.gov/docs/services/api/temporal/daily/
- https://earthaccess.readthedocs.io/en/stable/user/howto/authenticate/
- https://earthaccess.readthedocs.io/en/latest/api/
