# E2.S3 D-003 When2Heat Retrieval Execution Plan

Status: concrete retrieval/checksum completed after PI approval. D-003 remains
proposed pending PI review/sign-off, and this report does not claim final E2.S3
acceptance.

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

## Retrieval Result

After the PI approved the long-run notice, Agent C ran:

```powershell
.\.venv\Scripts\python.exe data/get_when2heat.py --download csv --resume
```

The run completed successfully without needing to resume from an existing
partial file.

- Raw path: `data/raw/when2heat/when2heat.csv`.
- Retrieved URL:
  https://data.open-power-system-data.org/when2heat/2023-07-27/when2heat.csv.
- Retrieved UTC timestamp: `2026-07-21T09:12:33.006594Z`.
- Byte size: `328400976`.
- SHA-256:
  `f1f71790158d1de08403eea32dea7a2732050870c499938135606d9d7faac0fa`.
- Metadata path:
  `data/metadata/when2heat/d003_when2heat_csv_metadata.json`.
- Checkpoint path:
  `data/metadata/when2heat/d003_when2heat_csv_download_checkpoint.json`.
- Resume status: enabled, resumed from `0` bytes; checkpoint status `complete`.
- Raw-file policy: `data/raw/when2heat/when2heat.csv` remains ignored by
  `.gitignore` and must not be committed.

## Validation After Retrieval

- Focused tests:
  `.\.venv\Scripts\python.exe -m pytest tests\test_hp_model.py tests\test_data_sources.py::test_data_entrypoints_run_directly`
  passed 14 tests.
- Ownership:
  `.\scripts\task.ps1 ownership` passed with 5 changed paths authorized.
- Raw-file ignore check:
  `git check-ignore -v data/raw/when2heat/when2heat.csv data/raw/when2heat/when2heat.csv.tmp`
  confirmed both raw paths are ignored by `.gitignore`.

## Acceptance Boundary

This retrieval does not prove final D-003 or E2.S3 acceptance. Final HP
acceptance still requires PI review/sign-off where applicable and a real
paired-weather cold-spell sanity check using the same weather realization as
PV. No event, probability, net-load, or manuscript result is claimed here.
