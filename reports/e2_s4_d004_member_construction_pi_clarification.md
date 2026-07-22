# E2.S4 D-004 Member-Construction PI Clarification

Date: 2026-07-22  
Agent: C.PV/weather  
Status: clarification only; D-004 and `D004-MC-001` remain unsigned.

## Current Blocker

PR #106 merged the `D004-MC-001` decision packet, but latest `origin/main` does not contain a signed `DECISIONS.md` row approving or amending that rule. Agent C should not implement accepted D-004 weather members until the rule is signed, because the hourly-to-15-minute transformation is a scientific/protocol choice.

Question filed: `registers/QUESTIONS.md` Q-9.

## Exact Approval Needed

Approve one of:

- `A`: approve `D004-MC-001` as proposed;
- `B`: amend `D004-MC-001` before implementation.

Recommended approval text for `A`:

```text
D004-MC-001 approved: construct D-004 WEATHER-001 members for `d004_alkmaar_berkhout_2014_2023_v1` as UTC calendar-year 15-minute members for 2014-2023. Derive Europe/Amsterdam local timestamps from the UTC axis. Interpret KNMI `HH` as UT hour-ending slots, with `HH=24` mapped to 00:00 UTC on the following date. Convert KNMI station 249 `T` to `temperature_c = T / 10` and repeat over the four represented quarter-hour timestamps. Convert KNMI `Q` to hourly-average `ghi_w_per_m2 = Q * 10000 / 3600` and repeat over the four quarter-hour sub-intervals so source hourly radiation energy is preserved. Use KNMI as the realized temperature/GHI weather path. Copy PVGIS-SARAH3 seriescalc/TMY URLs, checksums, and normalized PV configuration as calibration/validation provenance only; do not use PVGIS TMY as a realized sampled weather path. Use member IDs `d004_alkmaar_berkhout_<YEAR>_v1` and shared weather-driver IDs `d004_alkmaar_berkhout_2014_2023_v1:<YEAR>`. This approval does not sign final D-004 source acceptance, PVGIS seasonal/peak tolerances, HP/PV paired acceptance, net-load/event analysis, `P(E)`, capacity screens, or manuscript results.
```

## If Amending

The PI should specify any changes to:

- UTC-year versus Europe/Amsterdam local-year member boundaries;
- temperature handling: zero-order hold versus interpolation;
- irradiance handling: KNMI `Q` as realized GHI versus PVGIS field use;
- whether additional boundary-year PVGIS retrieval is authorized;
- required provenance fields or member-ID templates;
- whether processed arrays may be materialized under ignored `data/processed/weather_pv/`.

## Implementation To Start After Approval

After approval, Agent C should implement the member-construction scaffold/tests only:

- parse KNMI station 249 hourly ZIPs for approved 2014-2023 years;
- emit validated `src.weather_model.WeatherMember` objects;
- write per-member metadata and a library manifest under `data/metadata/weather_pv/`;
- preserve raw-file SHA-256/file-size/source URL provenance;
- test row counts, UTC/local calendar consistency, finite fields, nonnegative GHI, hourly radiation-energy preservation, identity records, and HP/PV common-driver compatibility.

No net-load, event, congestion, threshold, `P(E)`, capacity-screen, or manuscript-result analysis is part of this step.
