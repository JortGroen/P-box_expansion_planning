# E2.S4 D-004 Paired-Weather Acceptance Scaffold

Status: scaffold proposed; D-004 remains unsigned.

This follow-up turns the D-004 source/member acceptance packet into the next actionable layer. It separates source/member evidence that appears ready for PI review from gates that still require signed tolerances or later integrated inputs.

## Acceptable now if PI agrees

The scaffold records the four-file D-004 source bundle, checksum/size continuity, KNMI station 249 completeness for 2014-2023, constructed WEATHER-001 member identity records, UTC/local 15-minute calendar checks, KNMI `T / 10` temperature, KNMI `Q`-derived GHI, energy preservation, and PVGIS provenance-only boundaries. These are still PI-review evidence, not Agent C signoff.

## Still blocked

Final D-004 acceptance remains blocked by PI decisions on source/member acceptance sequencing, PVGIS seasonal/peak sanity criteria, paired HP/PV validation, cold-spell tolerances, and later integrated analysis gates. No net-load, event detection, `P(E)`, capacity screen, or manuscript result is produced here.

## HP/PV readiness scaffold

PV generation identity records now include canonical WEATHER-001 aliases: `member_id`, `source`, and `content_sha256`, while keeping the existing PV-prefixed fields. This lets later HP and PV outputs prove common use of the same `shared_weather_driver_id` and weather content identity. The included HP/PV regression uses synthetic profiles only; it is not real D-003/D-004 paired acceptance.

## Artifacts

- Metadata scaffold: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_paired_weather_acceptance_scaffold.json`
- Source/member acceptance packet: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_acceptance_packet.json`
- Member readiness diagnostics: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_member_readiness_diagnostics.json`
