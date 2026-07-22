# E2.S4 D-004 PI Recommendation Packet

Status: recommendation proposed; D-004 remains unsigned.

This packet distills the D-004 acceptance/tolerance packet into four PI decisions. It does not sign D-004, run paired HP/PV validation, run cold-spell acceptance, run net-load/event/`P(E)`, produce capacity screens, or create manuscript numbers.

## Recommendations

1. Source/member acceptance: sign the D-004 source/member layer separately if the PI accepts the exact audit evidence. The evidence covers the four approved source files, checksums, KNMI 2014-2023 completeness, WEATHER-001 member metadata, UTC/local 15-minute calendars, KNMI `T / 10`, KNMI `Q`-derived GHI, and PVGIS provenance-only use.
2. PVGIS sanity: use qualitative PVGIS seasonal/peak sanity for the source/member gate and defer numerical tolerances to later PV calibration if needed. KNMI GHI is the realized weather field; PVGIS fixed-plane `G(i)`/`P` is not the same physical quantity.
3. HP/PV prerequisite: require exact WEATHER-001 identity/calendar equality before any paired HP/PV diagnostics are judged. The required equality fields are `member_id`, `shared_weather_driver_id`, `source`, UTC span, timestep count, cadence, and `content_sha256`.
4. Cold-spell tolerances: leave HP cold-spell numerical tolerances unsigned in the HP lineage. Remaining PI choices include coldest-window tolerance, near-freezing/defrost-risk band around 0 degrees C, temperature-response tolerance, and whether cold-spell acceptance is bundled with final D-004 or D-003/D-004 acceptance.

## Recommended Sequence

1. PI signs or amends D-004 source/member acceptance criteria.
2. If signed, source/member status may advance while final paired acceptance remains blocked.
3. PI signs exact paired-weather prerequisite and HP cold-spell numerical tolerances before real paired validation.
4. After accepted HP scaling and signed tolerances, prepare a manifested paired HP/PV acceptance run.

## Artifacts

- Recommendation packet: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_pi_recommendation_packet.json`
- Acceptance/tolerance packet: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_acceptance_tolerance_packet.json`
- Source/member packet: `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_acceptance_packet.json`
