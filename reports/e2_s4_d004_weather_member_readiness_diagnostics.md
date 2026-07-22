# E2.S4 D-004 Weather-Member Readiness Diagnostics

## Scope

This memo records D-004/WEATHER-001 readiness diagnostics after the approved D004-MC-001 weather-member builder. It does not sign D-004, run HP/PV paired acceptance, run cold-spell acceptance, run net-load/event/P(E), produce capacity screens, or create manuscript results.

## Evidence Artifacts

- Member manifest: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_members_manifest.json`
- Readiness diagnostics: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_member_readiness_diagnostics.json`
- Per-year member metadata: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_member_<YEAR>_metadata.json`
- Retrieval manifest: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_retrieval_manifest.json`

## Findings For PI Review

The committed member manifest contains exactly ten UTC-year WEATHER-001 members for 2014-2023. The diagnostics confirm the expected 35,040 quarter-hour rows in non-leap years and 35,136 rows in 2016 and 2020, with UTC timestamps from January 1 00:00 to December 31 23:45 and Europe/Amsterdam local timestamps derived from those same instants.

The ignored local raw files still match the recorded retrieval-manifest sizes and SHA-256 checksums for the two PVGIS JSON references and two KNMI station 249 validated hourly ZIPs. KNMI station 249 remains the realized source for temperature and GHI. PVGIS-SARAH3 remains calibration/validation provenance only, not a realized sampled weather path.

The per-member metadata records finite KNMI `T/10` temperatures, nonnegative KNMI-Q-derived `ghi_w_per_m2`, and zero or floating-roundoff-only hourly energy-preservation error after repeating each hourly-average Q-derived GHI value over four 15-minute steps.

Seasonal and peak diagnostics are now machine-recorded for PI inspection. They compare KNMI-Q-derived GHI annual/seasonal totals and peak GHI month against PVGIS fixed-plane `G(i)` and PVGIS normalized `P` reference summaries. These comparisons are diagnostic only because PVGIS seasonal/peak acceptance tolerances are not PI-signed, and because PVGIS `G(i)` is a fixed-plane reference field rather than the realized GHI channel.

HP/PV paired-weather readiness is present at the contract level: every member has a stable `member_id`, `shared_weather_driver_id`, WEATHER-001 `content_sha256`, one UTC/local calendar, `temperature_c`, and `pv_weather_fields.ghi_w_per_m2`. Identity roundtrip checks pass for the constructed members. This is readiness for later paired acceptance design, not a paired HP/PV acceptance run.

## Remaining Before D-004 Acceptance

- PI review/sign-off of the concrete D-004 source files, checksums, and source-use evidence.
- PI approval or amendment of seasonal/peak sanity-check tolerances.
- HP/PV paired-weather acceptance using the same WEATHER-001 member identities.
- Separate cold-spell acceptance, if required by the HP/weather gate.
- No integrated net-load, congestion, event, P(E), capacity-screen, or manuscript-result analysis has been run.
