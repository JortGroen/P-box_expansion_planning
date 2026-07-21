# E2.S4 D-004 Retrieval/Checksum Execution Plan

Status: metadata-only execution plan. No raw PVGIS or KNMI D-004 data has been downloaded, no concrete site/station/year bundle has been selected, and D-004 remains proposed/scaffold-limited.

## Source Verification

PVGIS is planned through the official non-interactive API at `https://re.jrc.ec.europa.eu/api/v5_3`. The verified relevant tools are `seriescalc` for hourly time-series output and `tmy` for typical-year reference output. PVGIS documents `GET` as the computation method, JSON/CSV-style output options, a 30 calls/second/IP limit, and PVGIS 5.3 availability using SARAH-3/ERA5 coverage through 2023. The official usage page states that PVGIS information is free with no restrictions on use. PVGIS TMY remains calibration/validation reference material only, not an independently sampled realized weather member.

KNMI is planned through the Open Data API at `https://api.dataplatform.knmi.nl/open-data/v1`. The D-004 register currently names the `10-minute-in-situ-meteorological-observations` dataset; the dataset documentation describes NetCDF files, UTC timestamps, availability from 2012-01-01, and a near-real-time archive that may contain incomplete/unvalidated observations. The Open Data API requires an authorization header for file-list and temporary-URL endpoints; the returned temporary download URL itself does not require the authorization header. The D-004 register records the KNMI dataset license as CC-BY-4.0, to be reconfirmed against concrete dataset metadata before retrieval.

Neither official source page publishes stable response byte sizes for the planned concrete files. The retrieval acceptance plan therefore records API/file-list metadata, any available `Content-Length`, final local byte size, and SHA-256 for every accepted concrete file.

## PI Selections Required

Before raw download, the PI must approve:

- `D004_SELECTION_ID`;
- PVGIS latitude/longitude and whether the coordinates represent the grid area, a representative CBS cluster, or another signed site proxy;
- PVGIS radiation database, years, capacity, losses, tilt, azimuth, and whether `seriescalc` is only a reference or part of an approved irradiance bridge;
- KNMI station or station-selection rule, calendar years, filenames/list filters, and required variables;
- whether the named KNMI near-real-time in-situ dataset is acceptable despite documented incompleteness risk, or whether a validated KNMI source should replace it;
- whether the enumerated file count/runtime requires the long-run notice before execution.

## Target Paths

- Raw root: `data/raw/weather_pv`
- PVGIS raw directory: `data/raw/weather_pv/pvgis/<D004_SELECTION_ID>`
- KNMI raw directory: `data/raw/weather_pv/knmi/<D004_SELECTION_ID>`
- PVGIS series output: `data/raw/weather_pv/pvgis/<D004_SELECTION_ID>/pvgis_seriescalc_<D004_SELECTION_ID>.json`
- PVGIS TMY output: `data/raw/weather_pv/pvgis/<D004_SELECTION_ID>/pvgis_tmy_<D004_SELECTION_ID>.json`
- KNMI file-list metadata: `data/metadata/weather_pv/d004_knmi_file_list_<D004_SELECTION_ID>.json`
- Download checkpoint: `data/metadata/weather_pv/d004_download_checkpoint_<D004_SELECTION_ID>.json`
- Checksum/source metadata: `data/metadata/weather_pv/`

## Exact Commands

Metadata-only refresh, safe to run now:

```powershell
.\.venv\Scripts\python.exe data/get_weather_pv.py --write-execution-plan
```

After PI source selection and network approval, PVGIS commands should use the signed URLs recorded in `data/metadata/weather_pv/d004_weather_pv_execution_plan.json`:

```powershell
.\.venv\Scripts\python.exe data/get_weather_pv.py --download-url "<PI_SIGNED_PVGIS_SERIESCALC_URL>" --output-path "data/raw/weather_pv/pvgis/<D004_SELECTION_ID>/pvgis_seriescalc_<D004_SELECTION_ID>.json" --timeout-s 300
.\.venv\Scripts\python.exe data/get_weather_pv.py --record-local-file "data/raw/weather_pv/pvgis/<D004_SELECTION_ID>/pvgis_seriescalc_<D004_SELECTION_ID>.json" --source-kind pvgis --file-role calibration_or_validation_reference --source-url "<PI_SIGNED_PVGIS_SERIESCALC_URL>"
.\.venv\Scripts\python.exe data/get_weather_pv.py --download-url "<PI_SIGNED_PVGIS_TMY_URL>" --output-path "data/raw/weather_pv/pvgis/<D004_SELECTION_ID>/pvgis_tmy_<D004_SELECTION_ID>.json" --timeout-s 300
.\.venv\Scripts\python.exe data/get_weather_pv.py --record-local-file "data/raw/weather_pv/pvgis/<D004_SELECTION_ID>/pvgis_tmy_<D004_SELECTION_ID>.json" --source-kind pvgis --file-role typical_year_calibration_or_validation_only --source-url "<PI_SIGNED_PVGIS_TMY_URL>"
```

After PI source selection and network approval, KNMI commands should first list files and obtain temporary URLs:

```powershell
$Files = Invoke-RestMethod -Headers @{Authorization=$env:KNMI_API_KEY} -Uri "https://api.dataplatform.knmi.nl/open-data/v1/datasets/10-minute-in-situ-meteorological-observations/versions/1.0/files?maxKeys=<PI_SIGNED_MAX_KEYS>&startAfterFilename=<PI_SIGNED_START_AFTER>"
$Files | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 "data/metadata/weather_pv/d004_knmi_file_list_<D004_SELECTION_ID>.json"
$DownloadUrl = (Invoke-RestMethod -Headers @{Authorization=$env:KNMI_API_KEY} -Uri "https://api.dataplatform.knmi.nl/open-data/v1/datasets/10-minute-in-situ-meteorological-observations/versions/1.0/files/<PI_SIGNED_KNMI_FILENAME>/url").temporaryDownloadUrl
.\.venv\Scripts\python.exe data/get_weather_pv.py --download-url $DownloadUrl --output-path "data/raw/weather_pv/knmi/<D004_SELECTION_ID>/<PI_SIGNED_KNMI_FILENAME>" --timeout-s 300
.\.venv\Scripts\python.exe data/get_weather_pv.py --record-local-file "data/raw/weather_pv/knmi/<D004_SELECTION_ID>/<PI_SIGNED_KNMI_FILENAME>" --source-kind knmi --file-role historical_weather_path --source-url "https://api.dataplatform.knmi.nl/open-data/v1/datasets/10-minute-in-situ-meteorological-observations/versions/1.0/files/<PI_SIGNED_KNMI_FILENAME>/url"
```

## Checkpoint/Resume

The current single-URL helper is not resume-capable. Small PVGIS JSON requests may be restarted from byte zero because partial files are not accepted without checksum metadata. Before any KNMI multi-file run or any run expected to exceed 15 minutes, the executor must be extended to stream downloads to `.tmp` paths, checkpoint after each file and at least every 64 MiB within a large file, and atomically promote completed files only after final SHA-256 verification.

Checkpoint fields: selection ID, code commit, source URLs, target paths, completed files, bytes downloaded, partial SHA-256, final SHA-256, next file, and resume command. A resume run must validate the checkpoint against the signed source URLs and target paths before skipping completed files.

## PI Long-Run Notice Text

```text
LONG-RUN NOTICE
Task: E2.S4 / D-004 concrete PVGIS/KNMI weather-PV retrieval and checksum recording
Process: PI-approved PVGIS JSON retrieval plus KNMI Open Data API file-list, temporary-URL, and NetCDF downloads for <D004_SELECTION_ID>
Estimated wall time: unknown until the PI-selected station/year/file list is enumerated; PVGIS JSON is expected to be small, but KNMI multi-year 10-minute NetCDF retrieval may exceed 15 minutes depending on file count and network. Stop for PI approval if the enumerated plan estimates more than 15 minutes.
Resource impact: network transfer of PVGIS JSON plus selected KNMI NetCDF files; light CPU for SHA-256 hashing; raw files under data/raw/weather_pv remain ignored; metadata/checkpoints under data/metadata/weather_pv remain committed only after review.
Checkpoint plan: before raw download, write data/metadata/weather_pv/d004_download_checkpoint_<D004_SELECTION_ID>.json with source URLs, target paths, expected files, completed files, bytes downloaded, partial/final SHA-256 values, and next file. For bulk/slow KNMI retrieval, checkpoint after each file and at least every 64 MiB within a large file, writing to .tmp and atomically promoting only after final checksum.
Resume procedure: rerun the PI-approved retrieval command for <D004_SELECTION_ID>; validate the checkpoint source URLs, target paths, partial SHA-256, and completed-file list; skip files with matching final checksum metadata; resume or restart the next .tmp file; after completion update D-004 only as proposed and do not mark D-004 PI-signed.
```

## Acceptance Boundary

This plan does not approve concrete PVGIS or KNMI source selections, does not download raw data, does not record concrete D-004 checksums, does not make PVGIS TMY a realized weather member, and does not resolve Q-8/shared-weather implementation ownership. D-004 remains proposed until concrete source files, versions, checksums, completeness checks, and PI acceptance are recorded.
