# E2.S4 D-004 Member-Construction Rule Packet

Date: 2026-07-22  
Agent: C.PV/weather  
Status: PI decision packet only; D-004 remains proposed and unsigned.

## Decision Needed

The approved D-004 raw source bundle is hourly, while downstream HP/PV/weather consumers need a 15-minute `WeatherMember` under WEATHER-001. This packet proposes the member-construction rule to approve before Agent C builds real D-004 members.

Machine-readable packet: `data/metadata/weather_pv/d004_member_construction_rule_packet.json`.

## Recommended Rule

Approve `D004-MC-001`:

- Build one `src.weather_model.WeatherMember` per source year, 2014-2023.
- Use a UTC calendar-year 15-minute axis, with Europe/Amsterdam local timestamps derived from those UTC instants.
- Treat KNMI `HH` as a UT hour-ending timestamp; `HH=24` maps to 00:00 UTC on the following date.
- Convert KNMI `T` from 0.1 degrees Celsius to `temperature_c = T / 10`.
- Convert KNMI `Q` from J/cm2 per hour to hourly-average `ghi_w_per_m2 = Q * 10000 / 3600`.
- Repeat each hourly temperature and hourly-average GHI value over the four quarter-hour timestamps in the represented hour.
- Use KNMI station 249 `T` and `Q` as the realized temperature/GHI weather fields.
- Keep PVGIS-SARAH3 seriescalc and TMY files as calibration/validation provenance only, not as independently sampled realized weather paths.

## Why UTC Calendar Year

The approved PVGIS request did not set `localtime`, so the PVGIS series is UTC-oriented. KNMI hourly files document `HH` as UT. A UTC calendar-year member therefore matches the approved source-window framing without requiring extra boundary-year PVGIS retrieval.

The member still preserves local calendar identity because every UTC timestamp is paired with its Europe/Amsterdam timestamp in the WEATHER-001 object.

An alternative Europe/Amsterdam local-calendar-year member would be defensible, but it would require a separate PI decision about boundary-hour handling and may require additional PVGIS source retrieval outside the approved four-file route.

## Member Identity And Metadata

For each year:

- `member_id`: `d004_alkmaar_berkhout_<YEAR>_v1`
- `shared_weather_driver_id`: `d004_alkmaar_berkhout_2014_2023_v1:<YEAR>`
- `source`: `knmi_station_249_hourly_q_t_plus_pvgis_sarah3_reference`
- `pv_weather_fields`: at minimum `ghi_w_per_m2`
- provenance: KNMI station/source ZIP/source URL/checksum, PVGIS source URLs/checksums/configuration, source unit conversions, construction rule ID, builder command, and git commit
- metadata: selection ID, year, calendar basis, cadence, timezone, row counts, completeness status, and output/checksum paths

The later builder should write one metadata JSON per member plus a library manifest under `data/metadata/weather_pv/`. Raw files stay ignored. Processed member arrays should remain metadata-only unless the PI approves ignored processed storage under `data/processed/weather_pv/`.

## Acceptance Tests To Implement After Approval

- Emitted members are `src.weather_model.WeatherMember` objects.
- Non-leap years have 35,040 quarter-hour rows; leap years 2016 and 2020 have 35,136.
- UTC timestamps are timezone-aware, strictly chronological, and exactly 900 seconds apart.
- Europe/Amsterdam local timestamps represent the same instants as the UTC timestamps.
- `temperature_c` and `pv_weather_fields["ghi_w_per_m2"]` align exactly with timestamps and are finite.
- `ghi_w_per_m2` is nonnegative.
- For every KNMI source hour, four quarter-hour GHI slices preserve the original hourly `Q` energy within floating tolerance.
- `identity_record()` includes member/source/provenance/content identity sufficient for HP and PV to prove common-driver use.
- HP and PV profiles from the same member pass `assert_same_weather_realization`.
- PV seasonal totals and peak timing are checked against PVGIS/reference expectations before integration.
- PVGIS TMY cannot be used as a realized sampled weather member.

## Deferred Improvement

The primary `D004-MC-001` rule deliberately keeps KNMI hourly `Q` as a
block-constant, energy-preserving 15-minute GHI value. A later improvement or
sensitivity may replace this with an energy-preserving solar-shape
redistribution: use solar-position, clear-sky, or PVGIS-derived within-hour
weights to split each hourly KNMI `Q` value over four quarter-hour steps, then
renormalize the four values so their hourly integral exactly matches the KNMI
source energy. This is not part of the first-pass rule because it adds
assumptions about unobserved within-hour irradiance shape. Revisit it if PV
timing, export peaks, or PV/HP simultaneity becomes decision-relevant.

## Approval Questions

1. Approve UTC calendar-year members for D-004, with Europe/Amsterdam local timestamps derived from UTC?
2. Approve zero-order hourly-to-15-minute expansion for KNMI temperature?
3. Approve energy-preserving hourly-to-15-minute expansion for KNMI `Q` to realized GHI?
4. Approve PVGIS-SARAH3 seriescalc/TMY as calibration/validation provenance only?
5. Approve the proposed member IDs and shared weather-driver IDs?

## Boundaries

This packet does not sign D-004, create accepted members, download raw data, approve PVGIS seasonal/peak tolerances, run HP/PV paired acceptance, or run net-load, event, congestion, threshold, `P(E)`, capacity-screen, or manuscript-result analysis.
