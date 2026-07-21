# E2.S3 D-003 When2Heat Source Readiness

Status: proposed source-selection workflow only. No When2Heat raw file was
downloaded, no checksum was selected, and this stacked branch is not final
E2.S3 acceptance.

## Proposed Source

- Data ID: D-003.
- Source: When2Heat, Open Power System Data.
- DOI: https://doi.org/10.25832/when2heat/2023-07-27.
- OPSD package page: https://data.open-power-system-data.org/when2heat/2023-07-27.
- Proposed file: `when2heat.csv`.
- Package version: `2023-07-27`.
- Listed size: 313 MB.
- License: Creative Commons Attribution 4.0.
- Reason: the single-index CSV is directly compatible with the E2.S3 loader
  and contains the hourly NL heat-profile, heat-demand, and COP columns needed
  by the HP scaffold. The full package zip is listed as 497 MB and is not
  required for the current loader path.

## Retrieval And Checksum Workflow

1. Request normal network approval before any real download.
2. If expected runtime exceeds 15 minutes, send the mandatory long-run notice
   before launch.
3. Run `data/get_when2heat.py --download csv`.
4. The script streams to `data/raw/when2heat/when2heat.csv.tmp`, computes
   SHA-256 while streaming, and atomically replaces
   `data/raw/when2heat/when2heat.csv` only after completion.
5. The script writes concrete checksum metadata to
   `data/metadata/when2heat/d003_when2heat_csv_metadata.json`.
6. Update `registers/DATA_REGISTER.md` D-003 with the concrete checksum only
   after the file/version/checksum is selected for PI review; keep status
   `proposed` unless the PI signs it.

## Runtime Assessment

The primary CSV is listed as 313 MB. It is not inherently a >15 minute process:
it needs roughly 2.78 Mbit/s sustained throughput to finish within 15 minutes,
excluding setup and server latency. On a normal stable connection this is likely
below the long-run threshold. On a slow/proxied connection, or if the 497 MB zip
is retrieved instead, Agent C must treat the download as potentially >15
minutes and issue the long-run notice with a checkpoint/resume plan before
launch.

## Acceptance Boundary

This branch prepares the source-selection and checksum workflow only. It does
not prove:

- concrete D-003 checksum acceptance;
- real When2Heat parsing over a downloaded file;
- real paired-weather cold-spell sanity;
- final HP/PV shared-weather contract convergence.

The PV/weather branch `agent-c/E2.S4-shared-weather-contract-plan` records Q-7:
a neutral shared weather contract path such as `src/weather_model.py` is still
unassigned. Until the PI/maintainer resolves that path, HP remains structurally
compatible with the shared weather fields from PR #44 but does not import a
neutral shared weather module.
