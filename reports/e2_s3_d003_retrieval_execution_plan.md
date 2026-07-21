# E2.S3 D-003 When2Heat Retrieval Execution Plan

Status: execution plan only. No raw When2Heat file was downloaded for this
report, no concrete checksum is selected, and D-003 remains proposed.

## Verified Source Facts

- Data ID: D-003.
- Source: When2Heat Heating Profiles, Open Power System Data.
- Package version: `2023-07-27`.
- DOI: https://doi.org/10.25832/when2heat/2023-07-27.
- OPSD package page: https://data.open-power-system-data.org/when2heat/2023-07-27.
- Target file: `when2heat.csv`.
- Target URL: https://data.open-power-system-data.org/when2heat/2023-07-27/when2heat.csv.
- OPSD-listed target size: 313 MB.
- OPSD-listed full archive: `opsd-when2heat-2023-07-27.zip`, 497 MB; not
  required for the current HP loader.
- License: Creative Commons Attribution 4.0.
- Official page verification date: 2026-07-21. The OPSD page lists package
  version `2023-07-27`, identifies it as the latest package version, describes
  simulated hourly country-aggregated heat demand and COP time series, lists
  `when2heat.csv` as 313 MB, lists the zip archive as 497 MB, and states the
  data license as Creative Commons Attribution 4.0.

## Target Paths

- Raw file: `data/raw/when2heat/when2heat.csv`.
- Temporary file during retrieval: `data/raw/when2heat/when2heat.csv.tmp`.
- Download checkpoint:
  `data/metadata/when2heat/d003_when2heat_csv_download_checkpoint.json`.
- Concrete metadata after successful retrieval:
  `data/metadata/when2heat/d003_when2heat_csv_metadata.json`.
- Proposed source-selection metadata already committed:
  `data/metadata/when2heat/d003_when2heat_source_selection_plan.json`.
- D-003 register update after retrieval, still proposed unless PI signs:
  `registers/DATA_REGISTER.md`.

## Exact Command

Run only after PI approval of the notice below:

```powershell
.\.venv\Scripts\python.exe data/get_when2heat.py --download csv --resume
```

If the PI wants an explicit checkpoint path:

```powershell
.\.venv\Scripts\python.exe data/get_when2heat.py --download csv --resume --checkpoint-path data/metadata/when2heat/d003_when2heat_csv_download_checkpoint.json
```

The command streams the file, writes checkpoint metadata, computes SHA-256 from
the completed local file, atomically replaces the target raw file, and writes
concrete checksum metadata. The raw file remains uncommitted unless the PI
separately changes the data-redistribution policy.

## LONG-RUN NOTICE

```text
LONG-RUN NOTICE
Task: E2.S3 / D-003 concrete When2Heat retrieval and checksum recording
Process: .\.venv\Scripts\python.exe data/get_when2heat.py --download csv --resume
Estimated wall time: normally below 15 minutes on a stable connection above about 3 Mbit/s; treat as 15-30 minutes on slow, proxied, or unstable network conditions. The OPSD-listed target file is 313 MB.
Resource impact: network download of about 313 MB; light CPU for streaming and SHA-256 hashing; temporary disk use up to about 313 MB at data/raw/when2heat/when2heat.csv.tmp, then about 313 MB at data/raw/when2heat/when2heat.csv after atomic replace; small JSON metadata/checkpoint writes under data/metadata/when2heat.
Checkpoint plan: stream to data/raw/when2heat/when2heat.csv.tmp and update data/metadata/when2heat/d003_when2heat_csv_download_checkpoint.json at start, at least every 64 MiB, and at completion. The checkpoint records package version, selected file URL, temp/raw paths, bytes downloaded, partial SHA-256 of the temp file at checkpoint boundaries, resume byte offset, update time, and the exact resume command. The final metadata file records the concrete SHA-256 and byte size after successful atomic promotion.
Resume procedure: rerun .\.venv\Scripts\python.exe data/get_when2heat.py --download csv --resume. If data/raw/when2heat/when2heat.csv.tmp exists and the OPSD server honors HTTP Range, the script resumes from the existing byte count and appends the remaining bytes. If the server does not honor Range, the script restarts the temporary download from byte 0 rather than treating a partial file as complete. After completion, verify data/metadata/when2heat/d003_when2heat_csv_metadata.json, then update D-003 in DATA_REGISTER.md as proposed for PI review; do not mark D-003 signed.
```

## Checkpoint And Resume Behavior

The retrieval script now supports `--resume`. When enabled, it checks for an
existing `.tmp` file and requests the remaining byte range from the source URL.
If the server returns HTTP `206 Partial Content`, the script appends to the
existing temporary file. If the server returns a full response instead, the
script restarts the temporary file from zero bytes so a stale partial file
cannot silently contaminate the checksum.

The checkpoint JSON is durable audit state, not acceptance evidence by itself.
Only `d003_when2heat_csv_metadata.json` after a complete run records the
concrete file checksum. After retrieval, Agent C should compare:

- `selected_file.url` equals the target URL in this report;
- `package_version` equals `2023-07-27`;
- `download_performed` is `true`;
- `size_bytes` is consistent with the OPSD-listed 313 MB order of magnitude;
- `sha256_file` is nonempty and copied exactly into a proposed D-003 register
  update for PI review.

## Acceptance Boundary

This plan does not prove real D-003 acceptance. Final HP acceptance still
requires concrete checksum review, PI sign-off where applicable, and a real
paired-weather cold-spell sanity check using the same weather realization as
PV. No event, probability, net-load, or manuscript result is claimed here.
