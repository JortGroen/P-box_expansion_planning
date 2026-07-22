# E2.S4 D-004 Acceptance/Tolerance Packet

Status: PI packet proposed; D-004 remains unsigned.

This packet is the next D-004 readiness layer after the paired-weather scaffold. It does not sign D-004 and does not run final paired HP/PV, cold-spell, net-load, event, `P(E)`, capacity-screen, or manuscript-result analysis.

## Evidence Already Satisfied for PI Review

The committed metadata supports PI review of the source/member layer. The four approved raw-source records have exact file-size and SHA-256 evidence; KNMI station 249 Berkhout has complete hourly `T` and `Q` coverage for 2014-2023; the WEATHER-001 member manifest contains ten UTC-year members with complete 15-minute UTC/local calendars; KNMI `T / 10` temperature is finite; KNMI `Q`-derived GHI is nonnegative and preserves hourly radiation energy; PVGIS-SARAH3 remains provenance/calibration context only; and member/content identity is available for later HP/PV pairing checks.

## Unsigned Tolerance Decisions

The packet carries four PI decisions forward. First, whether exact audit checks are sufficient for source/member acceptance. Second, what PVGIS seasonal/peak sanity criterion should be signed, if any, before final D-004 acceptance or later PV calibration acceptance. Third, whether paired HP/PV validation should require exact WEATHER-001 identity/calendar equality before inspecting diagnostic outputs. Fourth, the numerical cold-spell tolerances, including the near-freezing band around 0 degrees C, remain unsigned under the E2-S3 design lineage.

## Must Wait for HP/PV Validation

Final paired-weather acceptance still requires accepted D-004 source/member status or explicit provisional-run authorization, accepted executable HP scaling inputs, pre-signed paired-weather/cold-spell tolerance criteria, and a manifested acceptance execution if it produces experimental evidence. The current artifact is governance/readiness evidence only.

## Artifacts

- Acceptance/tolerance packet: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_acceptance_tolerance_packet.json`
- Paired-weather scaffold: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_paired_weather_acceptance_scaffold.json`
- Source/member acceptance packet: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_acceptance_packet.json`
- Member readiness diagnostics: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_member_readiness_diagnostics.json`
