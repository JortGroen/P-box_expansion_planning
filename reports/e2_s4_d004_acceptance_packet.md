# E2.S4 D-004 Source/Member Acceptance Packet

Date: 2026-07-22  
Agent: C.PV/weather  
Status: PI packet proposed; D-004 remains unsigned.

## Scope

This packet packages the current D-004 source and WEATHER-001 member evidence for PI review. It does not sign D-004, approve seasonal/peak tolerances, run final paired HP/PV acceptance, run cold-spell acceptance, run net-load/event/P(E), produce capacity screens, or create manuscript results.

## Evidence Reviewed

- Retrieval manifest: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_retrieval_manifest.json`
- Source evidence: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_source_acceptance_evidence.json`
- Member manifest: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_members_manifest.json`
- Member readiness diagnostics: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_member_readiness_diagnostics.json`
- Acceptance packet metadata: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_acceptance_packet.json`

## Current Evidence Summary

The four approved raw source files are recorded with URLs, sizes, and SHA-256 checksums. The local ignored raw files matched those records when the readiness diagnostics were generated. KNMI station 249 Berkhout supplies the realized temperature and GHI source through complete hourly `T` and `Q` coverage for 2014-2023. PVGIS-SARAH3 supplies only calibration/validation provenance through the Alkmaar reference point and is not used as a realized sampled weather path.

The constructed member library contains ten WEATHER-001 members for UTC calendar years 2014-2023. Each member has the expected 15-minute cadence and row count, Europe/Amsterdam local timestamps derived from the UTC instants, finite `temperature_c = T / 10`, nonnegative `ghi_w_per_m2 = Q * 10000 / 3600`, energy preservation after repeating hourly Q-derived GHI across four quarter-hours, a stable member ID, a shared weather-driver ID, and a content hash.

PV readiness was tightened so generated PV profiles now retain the WEATHER-001 identity record they consumed. This gives later HP/PV paired checks a direct `shared_weather_driver_id` and weather `content_sha256` comparison without using net-load or event outputs.

## Seasonal/Peak Diagnostics

The readiness diagnostics compare KNMI-Q-derived GHI summaries with PVGIS fixed-plane `G(i)` and normalized PVGIS `P` reference summaries. The annual KNMI GHI to PVGIS fixed-plane `G(i)` ratio spans 0.806128 to 0.848755 across 2014-2023, and KNMI peak GHI months occur in May or June. These are diagnostic values only. No numerical tolerance is signed by this packet, and KNMI GHI is not the same irradiance quantity as PVGIS fixed-plane `G(i)` or PV power `P`.

## PI Questions

1. Does the PI accept the four concrete D-004 source files, URLs, sizes, and SHA-256 checksums as the source bundle for 2014-2023 WEATHER-001 members?
2. Does the PI accept the constructed 2014-2023 UTC-year WEATHER-001 member library as complete and calendar-consistent under D004-MC-001?
3. What seasonal/peak sanity criterion should be signed before final D-004 acceptance? Agent C recommends a qualitative first-pass criterion for source/member acceptance, reserving numeric PVGIS relative-error tolerances for a later PV calibration decision because KNMI GHI and PVGIS fixed-plane fields are not identical quantities.
4. Should source/member acceptance be signed separately before the later paired HP/PV and cold-spell acceptance gates, or must all of those remain bundled into one final D-004 decision?

## Recommendation

Recommend PI consider signing source/member acceptance separately if the four questions above are resolved, while keeping seasonal/peak numerical tolerances, paired HP/PV acceptance, cold-spell acceptance, and all integrated analyses as later gates.
