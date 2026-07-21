# E2.S4 D-004 Coverage Completeness Memo

Date: 2026-07-21  
Agent: C.PV/weather  
Status: D-004 remains proposed; this memo is not a PI sign-off.

## Question

Check whether KNMI station 249 has complete 2024 and 2025 hourly data, confirm the PVGIS/SARAH3 available year range for the Alkmaar PV point, and recommend whether the primary D-004 source window should remain 2014-2023 or be amended.

## Sources Checked

- Existing ignored KNMI raw ZIP: `data/raw/weather_pv/knmi/d004_alkmaar_berkhout_2014_2023_v1/uurgeg_249_2021-2030.zip`
  - D-004 manifest checksum: `f68e3797217a91a4121d7aab7146da7f989f96d561c92cb613b70a77d8ed9ef2`
  - D-004 manifest size: 838,086 bytes
- Existing ignored PVGIS raw JSON: `data/raw/weather_pv/pvgis/d004_alkmaar_berkhout_2014_2023_v1/pvgis_seriescalc_d004_alkmaar_berkhout_2014_2023_v1.json`
  - D-004 manifest checksum: `dca94839809cefd165edd964ddd269fbf6cc9fde7c5875905a84eb0ae830e2dc`
  - D-004 manifest size: 8,212,761 bytes
- KNMI hourly-data page: https://www.knmi.nl/nederland-nu/klimatologie/uurgegevens
- PVGIS user manual: https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/pvgis-5-user-manual_en
- PVGIS 5 overview/API page: https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5_en

No new raw D-004 data were downloaded for this memo.

## KNMI Station 249 Coverage

The local station-249 `2021-2030` hourly ZIP contains rows through 2026-07-20 hour 24. KNMI hourly files use 24 hourly slots per date; in the parser used for this check, `HH=24` is treated as the 00:00 instant on the next calendar date.

| Year | Expected hourly rows | Observed rows | Unique time slots | Duplicate slots | Missing T | Missing Q | Coverage verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2024 | 8,784 | 8,784 | 8,784 | 0 | 0 | 0 | Complete station-249 hourly year in this ZIP |
| 2025 | 8,760 | 8,760 | 8,760 | 0 | 0 | 0 | Complete station-249 hourly year in this ZIP |
| 2026 | 8,760 | 4,824 | 4,824 | 0 | 0 | 0 | Incomplete full-year member; exclude |

Interpretation: KNMI station 249 appears complete for 2024 and 2025 in the retrieved hourly ZIP, including nonblank temperature (`T`) and global radiation (`Q`) fields for every expected hourly slot. The 2026 slice is incomplete as of the local file and must not be used as a full-year member.

## PVGIS/SARAH3 Coverage

The official PVGIS user manual lists `PVGIS-SARAH3` with satellite-data coverage from 2005 through 2023. The PVGIS 5 overview likewise describes PVGIS 5.3 as extending current radiation and meteorological datasets up to 2023 and lists SARAH-3 as 2005-2023.

The existing approved Alkmaar PVGIS/SARAH3 retrieval contains 87,648 hourly records, exactly covering 2014-2023:

- First record: `20140101:0011`
- Last record: `20231231:2311`
- Years present: 2014-2023

Interpretation: for the approved Alkmaar point and PVGIS-SARAH3 route, 2024 and 2025 are not available as matching PVGIS/SARAH3 years without changing the source/database route. This memo does not propose or authorize such a source change.

## Recommendation

Keep `2014-2023` as the primary aligned KNMI+PVGIS D-004 source window.

Rationale:

- It is the approved and checksummed D-004 bundle window.
- It is aligned across KNMI station 249 and PVGIS/SARAH3.
- It preserves the ALEA-001 / WEATHER-001 direction that HP and PV ultimately consume the same paired weather realization on one calendar.
- Extending the primary window to 2024 or 2025 would currently create KNMI-only years for station 249, because PVGIS/SARAH3 coverage ends in 2023 for this route.

Treat 2024 and 2025, if scientifically useful and separately approved, only as optional KNMI-only diagnostic or sensitivity years. They should not be treated as primary aligned HP/PV weather members under the current D-004 source route.

Do not use 2026 as a full-year member because it is incomplete.

## Scope Boundaries

This memo does not:

- sign D-004;
- amend `registers/DATA_REGISTER.md`;
- implement Q-8 shared-weather code;
- run net-load, event, congestion, threshold, `P(E)`, or manuscript-result analysis;
- claim real-source acceptance beyond the coverage checks stated above.
