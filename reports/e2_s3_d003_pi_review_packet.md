# E2.S3 D-003 When2Heat PI Review Packet

Status: PI review packet only. D-003 remains proposed, unsigned, and not final
E2.S3 acceptance. This packet records cheap source/schema checks after the
concrete `when2heat.csv` retrieval; it does not run net-load integration, event
analysis, probabilities, or manuscript results.

## Retrieval Integrity

- Raw path: `data/raw/when2heat/when2heat.csv`.
- Raw path policy: ignored by `.gitignore` via `data/raw/*`; the raw CSV is not
  committed.
- Metadata path:
  `data/metadata/when2heat/d003_when2heat_csv_metadata.json`.
- Checkpoint path:
  `data/metadata/when2heat/d003_when2heat_csv_download_checkpoint.json`.
- Metadata-recorded URL:
  `https://data.open-power-system-data.org/when2heat/2023-07-27/when2heat.csv`.
- Metadata-recorded retrieval UTC timestamp: `2026-07-21T09:12:33.006594Z`.
- Metadata-recorded byte size: `328400976`.
- Local raw byte size verified on 2026-07-21: `328400976`.
- Metadata-recorded SHA-256:
  `f1f71790158d1de08403eea32dea7a2732050870c499938135606d9d7faac0fa`.
- Local raw SHA-256 verified on 2026-07-21:
  `f1f71790158d1de08403eea32dea7a2732050870c499938135606d9d7faac0fa`.
- Verification result: raw file size and SHA-256 match the committed metadata.

## Source Facts For PI Review

- Source: When2Heat Heating Profiles, Open Power System Data.
- Package version: `2023-07-27`.
- DOI: `https://doi.org/10.25832/when2heat/2023-07-27`.
- OPSD package page:
  `https://data.open-power-system-data.org/when2heat/2023-07-27`.
- OPSD-listed target file: `when2heat.csv`, 313 MB.
- OPSD-listed full archive: `opsd-when2heat-2023-07-27.zip`, 497 MB; not
  required for the current HP loader.
- License stated on OPSD page: Creative Commons Attribution 4.0.
- OPSD description: simulated hourly country-aggregated heat demand and COP time
  series for representing building heat pumps in power-system models.
- OPSD scope: 28 European countries, country resolution, years 2008-2022 at
  hourly resolution.
- OPSD notes: heat demand combines gas standard load profiles with spatial
  temperature and wind-speed reanalysis plus population geodata; COP series use
  reanalysis temperature data, heat-demand-weighted spatial aggregation, and
  field-measurement correction.
- Citation wording to review before signoff: OPSD asks users to consider/cite
  the Scientific Data descriptor, the 2023 working paper/update, and the OPSD
  package DOI. D-003 should not be called signed until the PI confirms the exact
  citation set and wording.

## Cheap CSV Schema And Coverage Checks

The checks below read the header, first data row, and final line only. They did
not count all rows or scan numeric completeness.

- Physical file: semicolon-delimited CSV with comma decimal notation.
- Header width: 656 columns.
- Timestamp columns:
  - `utc_timestamp`
  - `cet_cest_timestamp`
- First UTC timestamp: `2007-12-31T22:00:00Z`.
- First local timestamp: `2007-12-31T23:00:00+0100`.
- Last UTC timestamp: `2022-12-31T23:00:00Z`.
- Last local timestamp: `2023-01-01T00:00:00+0100`.
- Inferred inclusive hourly endpoint count from first/last UTC timestamps:
  `131498` rows. This is an endpoint inference only, not a full row count.
- Netherlands-specific columns found: 24.

## Netherlands Columns Present

- `NL_COP_ASHP_floor`
- `NL_COP_ASHP_radiator`
- `NL_COP_ASHP_water`
- `NL_COP_GSHP_floor`
- `NL_COP_GSHP_radiator`
- `NL_COP_GSHP_water`
- `NL_COP_WSHP_floor`
- `NL_COP_WSHP_radiator`
- `NL_COP_WSHP_water`
- `NL_heat_demand_space`
- `NL_heat_demand_space_COM`
- `NL_heat_demand_space_MFH`
- `NL_heat_demand_space_SFH`
- `NL_heat_demand_total`
- `NL_heat_demand_water`
- `NL_heat_demand_water_COM`
- `NL_heat_demand_water_MFH`
- `NL_heat_demand_water_SFH`
- `NL_heat_profile_space_COM`
- `NL_heat_profile_space_MFH`
- `NL_heat_profile_space_SFH`
- `NL_heat_profile_water_COM`
- `NL_heat_profile_water_MFH`
- `NL_heat_profile_water_SFH`

## HP Model Columns Needed

The current E2.S3 HP scaffold constructs components with:

- country prefix: default `NL`;
- source: default `ASHP`;
- space sink: default `radiator`;
- building classes: explicit caller-provided annual heat TWh scales for
  `SFH`, `MFH`, and/or `COM`.

For each selected building class, the loader needs:

- space heat profile: `NL_heat_profile_space_<class>`;
- water heat profile: `NL_heat_profile_water_<class>`;
- space COP: `NL_COP_ASHP_radiator`;
- water COP: `NL_COP_ASHP_water`.

All current default Dutch HP columns are present in the retrieved CSV. The
source also contains national heat-demand columns (`NL_heat_demand_*`), but the
current scaffold uses normalized `heat_profile_*` columns with explicit annual
TWh scaling so adoption/building-stock volume is not hidden in D-003.

## Ambiguities And Review Items

- Geography: the data are country-aggregated, and the HP scaffold selects the
  Netherlands (`NL`). PI review should decide whether country-level Dutch
  profiles are acceptable for the SimBench benchmark despite the grid's German
  topology provenance and the future KNMI/PV weather pairing.
- Temperature basis: When2Heat profiles and COPs are already derived from
  reanalysis weather inputs. The HP scaffold still consumes a future shared
  weather member for audit/calendar alignment, but it does not rederive
  When2Heat demand from that member's temperature. PI review should confirm
  whether this is acceptable, or whether the real cold-spell check must impose
  an additional consistency criterion.
- Time index: the file has both UTC and CET/CEST timestamp columns. The HP
  scaffold must use `utc_timestamp` for canonical alignment, while preserving
  local calendar information from the shared weather member. The first UTC
  endpoint begins at `2007-12-31T22:00:00Z` even though the package is described
  as 2008-2022; this is consistent with local-time coverage crossing UTC
  boundaries but should be acknowledged.
- CSV dialect: the real file is semicolon-delimited and uses comma decimals.
  The current `load_when2heat_hourly_csv` implementation uses pandas defaults,
  so it will not parse the real file correctly until the loader is updated or
  explicitly called with the real dialect. This is an implementation blocker
  before real D-003 parsing/cold-spell acceptance, not a source signoff blocker
  by itself.
- Heat demand units: OPSD field documentation defines `heat_demand_*` as MW and
  `heat_profile_*` as normalized MW/TWh. The scaffold's normalized-profile
  route is consistent with the latter, but annual TWh scaling remains a separate
  proposed input and is not supplied by D-003 signoff alone.
- COP columns: this packet assumes air-source heat pumps with radiators for
  space heating and ASHP water COP for water heating. The source also provides
  floor, ground-source, and groundwater-source alternatives. PI signoff should
  not silently choose among those technology/sink options without a separate
  approved assumption if the defaults become scientific inputs.
- License and citation: OPSD states CC BY 4.0 for the data and provides
  attribution recommendations. PI review should decide the exact citation
  wording before manuscript use.

## Decision Framing

Evidence that appears ready for PI review:

- The concrete `when2heat.csv` file was retrieved from the proposed OPSD URL.
- The recorded local byte size and SHA-256 match the committed metadata.
- The Dutch normalized heat-profile and COP columns needed by the scaffold are
  present.
- The raw file remains ignored and uncommitted.

Evidence still missing before final E2.S3 acceptance:

- Loader support or invocation for the real semicolon/comma CSV dialect.
- A real parse over the retrieved file using the intended Dutch columns.
- A real paired-weather cold-spell sanity check using the same weather
  realization as PV.
- PI decision on geography, technology/COP defaults, citation wording, and
  whether D-003 can be signed for the intended HP use.

## Validation

- `.\scripts\task.ps1 ownership`: passed with 1 changed path authorized.
- No code changes were made in this packet branch; focused HP/data-source tests
  are not required unless code changes are added.
