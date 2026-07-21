## 2026-07-21 12:35 — E2.S4 D-004 — in-progress
DID: Prepared a metadata-only PI packet proposing `d004_alkmaar_berkhout_2014_2023_v1` as the first D-004 source-selection bundle. The packet proposes Alkmaar PVGIS coordinates, KNMI station 249 Berkhout, 2014-2023 validated hourly KNMI ZIPs, PVGIS-SARAH3 reference requests, target paths, approval questions, and a long-run notice draft.
VERIFIED: Header-only source checks for the two KNMI ZIP URLs and PVGIS HEAD checks; no raw D-004 data downloaded. Ownership/test validation pending.
OPEN: PI must approve or reject the source route, especially the switch from 10-minute in-situ bulk files to validated hourly station ZIPs. Q-8 shared-weather ownership remains open.
NEXT: Run ownership and full test gate, then open PR for PI review.
