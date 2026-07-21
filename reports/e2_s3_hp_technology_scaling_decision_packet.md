# E2.S3 HP Technology And Scaling Decision Packet

Decision packet ID: `E2-S3-HP-TECH-SCALING-DECISION-PACKET`

Status: PI decision packet only. D-003 and D-004 remain proposed and unsigned.
This packet prepares the remaining heat-pump modeling choices before real HP
integration. It does not select final scientific inputs, set numerical
tolerances, run paired-weather acceptance, run net-load integration, run event
analysis, estimate `P(E)`, produce capacity-screen evidence, or create
manuscript results.

## Purpose

The E2.S3 HP scaffold can parse the retrieved OPSD When2Heat CSV, preserve
shared-weather identity fields, and build synthetic or parser-level HP profiles.
The next PI decision is which source-use and technology/scaling assumptions are
acceptable enough to turn that scaffold into a real HP component.

This packet consolidates the earlier D-003 parser/source-use, annual-scaling,
and cold-spell design packets into one review checklist. All options below are
proposed only.

## Source Context

- D-003 source: When2Heat Heating Profiles, Open Power System Data.
- Package version: `2023-07-27`.
- File: `when2heat.csv`.
- DOI: `https://doi.org/10.25832/when2heat/2023-07-27`.
- URL:
  `https://data.open-power-system-data.org/when2heat/2023-07-27/when2heat.csv`.
- License recorded for PI review: Creative Commons Attribution 4.0.
- Raw ignored path: `data/raw/when2heat/when2heat.csv`.
- Metadata:
  `data/metadata/when2heat/d003_when2heat_csv_metadata.json`.
- Byte size: `328400976`.
- SHA-256:
  `f1f71790158d1de08403eea32dea7a2732050870c499938135606d9d7faac0fa`.
- CSV dialect: semicolon delimiter, comma decimals.
- Time columns: `utc_timestamp` and `cet_cest_timestamp`.

The current D-003 evidence proves retrieval/checksum and parser readiness. It
does not prove source acceptance, local representativeness, technology
scenario validity, annual volume validity, or ALEA-001 paired-weather
acceptance.

## Proposed Shape Columns

Proposed Dutch normalized heat-profile columns for HP shape:

| Component | Proposed column | Interpretation in HP scaffold |
|---|---|---|
| Space heat, single-family houses | `NL_heat_profile_space_SFH` | Average thermal MW per annual TWh |
| Space heat, multi-family houses | `NL_heat_profile_space_MFH` | Average thermal MW per annual TWh |
| Space heat, commercial buildings | `NL_heat_profile_space_COM` | Average thermal MW per annual TWh |
| Water heat, single-family houses | `NL_heat_profile_water_SFH` | Average thermal MW per annual TWh if water heating is included |
| Water heat, multi-family houses | `NL_heat_profile_water_MFH` | Average thermal MW per annual TWh if water heating is included |
| Water heat, commercial buildings | `NL_heat_profile_water_COM` | Average thermal MW per annual TWh if water heating is included |

Proposed handling:

- Keep SFH, MFH, and COM as separate components until the PI signs an
  aggregation or omission rule.
- Use space-heat shape columns for any space-heating HP layer.
- Include water-heat shape columns only if the PI signs water heating into the
  HP boundary.
- Treat all selected heat-profile columns as normalized shapes; annual thermal
  TWh must be supplied explicitly and recorded with provenance.

## Proposed COP And Technology Choices

Current scaffold default proposed for review:

| End use | Proposed COP column | Proposed technology/sink interpretation |
|---|---|---|
| Space heat | `NL_COP_ASHP_radiator` | Air-source heat pump with radiator sink |
| Water heat | `NL_COP_ASHP_water` | Air-source heat pump water-heating COP |

Available alternatives requiring explicit PI selection before scientific use:

- `NL_COP_ASHP_floor`
- `NL_COP_GSHP_floor`
- `NL_COP_GSHP_radiator`
- `NL_COP_GSHP_water`
- `NL_COP_WSHP_floor`
- `NL_COP_WSHP_radiator`
- `NL_COP_WSHP_water`

Proposed review framing:

- ASHP radiator is a transparent scaffold default, not an approved future Dutch
  technology scenario.
- Floor heating may represent lower-temperature buildings but requires a
  separate building-stock or scenario justification.
- GSHP and WSHP options should be treated as distinct technology scenarios or a
  signed weighted mix, not silently substituted for ASHP.
- COP columns are dimensionless; HP electric kW is computed as thermal kW
  divided by the selected COP at each timestamp.

## Annual Scaling Decision

The HP scaffold needs annual thermal TWh inputs because normalized When2Heat
`heat_profile_*` columns provide shape rather than an approved project volume.
The PI must decide whether annual scaling comes from When2Heat itself or from a
separate registered source.

### Option A: When2Heat Space-Only Scaling

Use the 2008-2015 local-year mean Dutch `heat_demand_space_*` values from the
retrieved file:

| Component | Column | Candidate mean TWh/year |
|---|---|---:|
| Space SFH | `NL_heat_demand_space_SFH` | 38.585 |
| Space MFH | `NL_heat_demand_space_MFH` | 16.537 |
| Space COM | `NL_heat_demand_space_COM` | 31.780 |
| Space total | `NL_heat_demand_space` | 86.900 |

This is the conservative When2Heat-only volume option if the PI wants D-003 to
supply both shape and annual space-heat scaling. It excludes water heating.

### Option B: When2Heat Space Plus Water Scaling

Add the 2008-2015 local-year mean Dutch `heat_demand_water_*` values:

| Component | Column | Candidate mean TWh/year |
|---|---|---:|
| Water SFH | `NL_heat_demand_water_SFH` | 9.624 |
| Water MFH | `NL_heat_demand_water_MFH` | 4.124 |
| Water COM | `NL_heat_demand_water_COM` | 6.204 |
| Water total | `NL_heat_demand_water` | 19.952 |
| Space plus water total | `NL_heat_demand_total` | 106.852 |

This option is more complete for building heat but must be a deliberate PI
scenario because water heating changes the HP boundary, COP route, seasonal
shape, and electric load.

### Option C: External Annual Scaling Source

Use When2Heat only for normalized shape and COP, and source annual useful heat,
heat-pump-served heat, or electrified 2035 heat from another registered source.
This may better match a future adoption scenario or local service-area scaling,
but the source, license, values, units, geography, and PI signoff must be added
before use.

### Boundary Choices Still Needed

For any option, the PI must state whether annual TWh represents:

- total Dutch thermal demand;
- useful heat served by heat pumps;
- final thermal demand after an adoption/electrification fraction;
- a local SimBench-equivalent or service-area downscaled value; or
- another explicitly registered boundary.

The packet does not approve a local downscaling denominator or any 2035
electrified HP adoption volume.

## Water Heating Decision

Proposed options:

- Space-only primary HP layer: simpler, avoids domestic-hot-water boundary and
  COP ambiguity, and uses only the space profile/COP path.
- Space plus water HP layer: more complete building heat representation, but
  requires signed annual water-heat scaling, selected water COP, and a clear
  statement that water heating is in scope.
- Sensitivity-only water heating: primary remains space-only while a later
  signed sensitivity includes water heat.

Agent C review recommendation: do not include water heating by default. Treat
it as a PI-selected primary boundary or a later signed sensitivity.

## SFH/MFH/COM Class Split

Proposed default before final integration:

- Preserve SFH, MFH, and COM as separate HP components.
- Record each selected class, annual TWh value, shape column, COP column, and
  resulting component provenance.
- Allow aggregation only after component construction, so omitted classes or
  class-specific assumptions remain auditable.

Open PI choices:

- Whether COM belongs in the study's HP layer for the selected grid/service
  area.
- Whether SFH/MFH/COM should be scaled by Dutch country shares, local building
  stock, SimBench load classes, or another registered denominator.
- Whether class-specific adoption fractions are needed before real integration.

## Weather And Acceptance Blockers

Q-8 remains open. HP must consume the approved shared weather contract once it
exists, not a separate temperature-only structure. Before real E2.S3 HP
integration or D-003 signoff, the project still needs:

- an authorized shared weather contract preserving `member_id`,
  `shared_weather_driver_id`, source/provenance, UTC/local calendar,
  temperature, and irradiance/PV weather fields;
- concrete D-004 weather members with checksums and completeness evidence;
- HP and PV profile outputs proving they used the same weather realization;
- PI-signed numerical tolerances for the cold-spell and temperature-response
  acceptance design before the first real acceptance run;
- a real paired-weather acceptance report generated from committed code and
  source metadata.

When2Heat heat profiles and COPs are already weather-derived by the OPSD
workflow. The future acceptance check should therefore verify directional
consistency with the shared D-004 member, not claim the D-004 temperature
mechanically regenerated the D-003 HP profile.

## Recommended PI Decision Sequence

1. Resolve Q-8 so HP and PV share one weather-member contract.
2. Decide whether D-003 can be used for shape/COP after reviewing OPSD
   citation/license wording.
3. Select technology/COP route: ASHP radiator, ASHP floor, GSHP/WSHP, or a
   signed mix.
4. Decide whether water heating is primary, sensitivity-only, or out of scope.
5. Decide whether annual scaling uses When2Heat `heat_demand_*` evidence or an
   external registered source.
6. Decide class handling and any local/downscaled service-area denominator.
7. Sign cold-spell/paired-weather numerical tolerances before running the real
   acceptance check.
8. Review the real acceptance report before considering D-003/D-004 signoff for
   HP integration.

## What This Packet Does Not Decide

- It does not sign D-003 or D-004.
- It does not approve any final annual TWh value.
- It does not approve any final HP technology scenario.
- It does not include water heating by default.
- It does not approve a local downscaling denominator.
- It does not set numerical acceptance tolerances.
- It does not run paired-weather acceptance.
- It does not run net-load integration, event analysis, `P(E)`, capacity
  screens, probability analysis, or manuscript-result analysis.

## Suggested STATUS Update

`E2.S3 HP model | C | in-progress | HP technology/scaling decision packet prepared; D-003/D-004 unsigned; Q-8 and real paired-weather acceptance pending | PR: <this PR>`
