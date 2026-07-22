# E2.S4 D-004 Source Acceptance Readiness Memo

Date: 2026-07-21  
Agent: C.PV/weather  
Status: PI-facing readiness memo only; D-004 remains proposed and unsigned.

## Recommendation

Recommend PI accept `d004_alkmaar_berkhout_2014_2023_v1` for source-file completeness and WEATHER-001-compatible member construction, while keeping final D-004 acceptance open until concrete shared `WeatherMember` records and PV sanity checks are produced.

## Evidence Summary

- The four approved raw D-004 files are present locally, remain ignored/uncommitted, and match the committed SHA-256 and file-size metadata.
- KNMI station 249 Berkhout has complete annual hourly rows for every primary year 2014-2023.
- Each primary KNMI year has the expected row count, no duplicate hour-ending UTC slots, and no missing `T` or `Q` fields.
- The PVGIS-SARAH3 Alkmaar hourly-series file contains 87,648 rows covering exactly 2014-2023, including leap years 2016 and 2020.
- WEATHER-001 is now implemented through `src/weather_model.py`, and PV generation now consumes the neutral `WeatherMember` contract rather than a PV-local weather class.

The detailed machine-readable evidence is in `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_source_acceptance_evidence.json`.

## Calendar And Timestamp Readiness

KNMI hourly files document `HH` as UT hour slots. For member construction, the intended interpretation is hour-ending UTC instants: for example, `HH=24` maps to 00:00 UTC on the following date. The shared WEATHER-001 member must then derive Europe/Amsterdam local timestamps from those same UTC instants.

That gives a clear bridge to the approved `WeatherMember` contract, but one implementation choice remains open: the approved raw sources are hourly, while the neutral project calendar is 15-minute. A later D-004 member-builder step still needs an approved hourly-to-15-minute construction rule before final D-004 acceptance.

## Source Window

The primary source window should remain 2014-2023.

This is the aligned ten-year window where:

- KNMI station 249 has complete hourly `T` and `Q` source rows;
- PVGIS-SARAH3 coverage is available for the Alkmaar point;
- the raw file checksums and sizes have already been recorded;
- ALEA-001 and WEATHER-001 can be preserved by constructing paired weather members from the same year/source identity.

The earlier coverage memo showed 2024 and 2025 are complete in KNMI station 249, but they remain KNMI-only diagnostics under this route because PVGIS-SARAH3 does not provide matching 2024/2025 coverage. Do not use 2026 as a full-year member.

## Remaining Before D-004 Acceptance

- PI reviews and accepts or rejects this source-completeness evidence.
- Agent C implements or runs the D-004 member-builder path that emits neutral `WeatherMember` records.
- The hourly-to-15-minute rule is approved and recorded before accepted members are generated.
- PV seasonal totals and peak timing are sanity-checked against PVGIS/reference expectations on the constructed members.
- HP and PV profile outputs prove they consumed the same `member_id`, `shared_weather_driver_id`, calendar record, source/provenance, and content identity.

## Boundaries

This memo does not sign D-004, create accepted weather members, change D-004 source files, download raw data, run net-load, event, congestion, threshold, `P(E)`, capacity-screen, or manuscript-result analysis.
