# E2.S4 D-004 Source-Selection PI Packet

Status: proposed for PI review. No raw D-004 data has been downloaded, no checksum has been recorded for a concrete file, and Q-8/shared-weather implementation ownership remains open.

## Recommendation

Approve source bundle `d004_alkmaar_berkhout_2014_2023_v1` for the next raw retrieval step.

- PVGIS site: Alkmaar representative point, latitude `52.63167`, longitude `4.74861`, aligned with the proposed EV-007 Alkmaar (`GM0361`) local cluster.
- KNMI station: station `249`, Berkhout, WIGOS station identifier `0-20000-0-06249`.
- Weather source route: KNMI validated hourly station ZIPs from the climatology page, not the bulk near-real-time 10-minute in-situ archive for the first retrieval.
- Year range: filter complete annual weather members for `2014` through `2023`.
- PVGIS radiation database: `PVGIS-SARAH3` through PVGIS 5.3.
- PV reference configuration: normalized `1.0 kWp`, fixed plane, `14%` losses, `35` degree tilt, `0` degree south-facing aspect, JSON output.

The hourly KNMI route is recommended because KNMI states these hourly station files combine temperature, sun, visibility, pressure, wind, and precipitation by station; the ZIPs are quality-checked, corrected, and supplemented where possible; and station 249 has decade ZIPs covering 2011-2020 and 2021-2030. The same page documents `T` as temperature and `Q` as global radiation, which are the minimum paired HP/PV weather channels needed before Q-8 integration.

## Proposed File List

PVGIS reference files:

- `data/raw/weather_pv/pvgis/d004_alkmaar_berkhout_2014_2023_v1/pvgis_seriescalc_d004_alkmaar_berkhout_2014_2023_v1.json`
- `data/raw/weather_pv/pvgis/d004_alkmaar_berkhout_2014_2023_v1/pvgis_tmy_d004_alkmaar_berkhout_2014_2023_v1.json`

KNMI raw ZIP files:

- `data/raw/weather_pv/knmi/d004_alkmaar_berkhout_2014_2023_v1/uurgeg_249_2011-2020.zip`
- `data/raw/weather_pv/knmi/d004_alkmaar_berkhout_2014_2023_v1/uurgeg_249_2021-2030.zip`

Metadata:

- Source-selection packet: `data/metadata/weather_pv/d004_source_selection_pi_packet.json`
- Future checksum records: `data/metadata/weather_pv/d004_pvgis_*_metadata.json` and `data/metadata/weather_pv/d004_knmi_*_metadata.json`
- Existing execution plan: `data/metadata/weather_pv/d004_weather_pv_execution_plan.json`

## Exact Requests After PI Approval

PVGIS seriescalc:

`https://re.jrc.ec.europa.eu/api/v5_3/seriescalc?lat=52.63167&lon=4.74861&startyear=2014&endyear=2023&pvcalculation=1&peakpower=1.0&loss=14.0&angle=35.0&aspect=0.0&fixed=1&outputformat=json&browser=0&raddatabase=PVGIS-SARAH3`

PVGIS TMY:

`https://re.jrc.ec.europa.eu/api/v5_3/tmy?lat=52.63167&lon=4.74861&outputformat=json&browser=0&raddatabase=PVGIS-SARAH3`

KNMI Berkhout hourly ZIPs:

- `https://cdn.knmi.nl/knmi/map/page/klimatologie/gegevens/uurgegevens/uurgeg_249_2011-2020.zip`
- `https://cdn.knmi.nl/knmi/map/page/klimatologie/gegevens/uurgegevens/uurgeg_249_2021-2030.zip`

Header-only checks on 2026-07-21 returned `200` for both KNMI ZIPs. Reported sizes were `1,536,802` bytes for `uurgeg_249_2011-2020.zip` and `838,086` bytes for `uurgeg_249_2021-2030.zip`. PVGIS `HEAD` returned `204` for both API requests, consistent with the PVGIS API documentation that `HEAD` confirms function existence rather than returning a computation payload.

## Approval Questions

- Approve `d004_alkmaar_berkhout_2014_2023_v1` as the source-selection bundle?
- Approve Alkmaar coordinates `52.63167, 4.74861` as the PVGIS representative site?
- Approve station 249 Berkhout as the primary temperature/global-radiation station?
- Approve switching the first retrieval route from KNMI 10-minute in-situ bulk files to validated hourly station ZIPs?
- Approve 2014-2023 as the historical annual-member window?
- Approve the normalized PVGIS/PV configuration above as calibration/validation reference only?

## Guardrails

PVGIS TMY remains calibration/validation reference material only and must not become an independently sampled realized weather path. Each accepted historical year must later become one complete chronological weather member with paired temperature and irradiance/global-radiation fields on the common UTC/local calendar. HP and PV must consume the same `member_id` and `shared_weather_driver_id` once Q-8 is resolved; this PR does not implement `src/weather_model.py` or `tests/test_weather_model.py`.

No D-004 DATA_REGISTER checksum update is made here because no raw file was downloaded and no concrete checksum exists. If the PI approves this packet, the next retrieval PR should download the four files, record SHA-256 metadata, validate completeness for 2014-2023, and update D-004 as proposed for PI acceptance.

## Long-Run Notice Draft

```text
LONG-RUN NOTICE
Task: E2.S4 / D-004 PI-approved weather/PV source retrieval and checksum recording
Process: Download two KNMI Berkhout validated hourly ZIP files plus two PVGIS JSON reference files for d004_alkmaar_berkhout_2014_2023_v1; compute SHA-256 metadata and do not use outputs until PI acceptance.
Estimated wall time: expected under 15 minutes based on KNMI HEAD sizes of 1,536,802 bytes and 838,086 bytes plus small PVGIS JSON responses; if PVGIS/KNMI response time or a revised 10-minute in-situ route pushes the estimate over 15 minutes, stop and use the checkpoint/resume plan from data/metadata/weather_pv/d004_weather_pv_execution_plan.json before launch.
Resource impact: small network transfer, light CPU for SHA-256 hashing, ignored raw files under data/raw/weather_pv, committed checksum metadata only after review.
Checkpoint plan: for this small four-file route, restart failed files from byte zero and accept only complete files with final SHA-256 metadata; if the PI requires 10-minute in-situ bulk retrieval, extend the downloader to .tmp streaming with per-file and 64 MiB checkpoints before launch.
Resume procedure: rerun the approved retrieval commands; skip only files with matching final checksum metadata; otherwise restart the incomplete target from byte zero.
```

## Source Notes

Official source checks used PVGIS API and usage-condition pages, the KNMI hourly climatology page, the KNMI 10-minute in-situ dataset page, the KNMI Berkhout station note, the KNMI station-renaming WIGOS table, and GeoNames for the Alkmaar representative coordinate. These checks support proposal review only; they are not real-source acceptance evidence.
