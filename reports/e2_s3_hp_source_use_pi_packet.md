# E2.S3 HP Source-Use PI Packet

Status: PI decision packet only. D-003 remains proposed and unsigned. This
packet narrows the proposed When2Heat source-use assumptions needed before the
parser-ready CSV can become a scientifically usable heat-pump input. It does not
run net-load integration, event analysis, probabilities, threshold studies, or
manuscript results.

## Purpose

PR #68 made the retrieved OPSD When2Heat `2023-07-27` CSV parser-ready for the
E2.S3 HP scaffold. The next PI decision is not whether the file can be read, but
which Dutch source columns, heat-pump technology defaults, and scaling inputs
are acceptable for the study.

This packet records the proposed source-use mapping for PI review. All choices
below remain proposed until the PI signs the relevant data/assumption record.

## D-003 Source Context

- Dataset: When2Heat Heating Profiles, Open Power System Data.
- Package version: `2023-07-27`.
- Proposed file: `when2heat.csv`.
- DOI: `https://doi.org/10.25832/when2heat/2023-07-27`.
- Source URL:
  `https://data.open-power-system-data.org/when2heat/2023-07-27/when2heat.csv`.
- License recorded for PI review: Creative Commons Attribution 4.0.
- Raw path: `data/raw/when2heat/when2heat.csv` (ignored, not committed).
- Metadata path:
  `data/metadata/when2heat/d003_when2heat_csv_metadata.json`.
- Recorded size: `328400976` bytes.
- Recorded SHA-256:
  `f1f71790158d1de08403eea32dea7a2732050870c499938135606d9d7faac0fa`.
- CSV dialect: semicolon delimiter with comma decimals.
- Time columns: `utc_timestamp` and `cet_cest_timestamp`.

## Proposed Dutch HP Columns

The proposed country prefix is `NL`. The current scaffold uses normalized heat
profile columns, not national heat-demand columns, so the annual heat volume
remains an explicit external input rather than an implicit D-003 choice.

Proposed space heat profile columns:

- `NL_heat_profile_space_SFH`
- `NL_heat_profile_space_MFH`
- `NL_heat_profile_space_COM`

Proposed water heat profile columns:

- `NL_heat_profile_water_SFH`
- `NL_heat_profile_water_MFH`
- `NL_heat_profile_water_COM`

Proposed matching COP columns for the current scaffold default:

- Space heat, air-source radiator sink: `NL_COP_ASHP_radiator`
- Water heat, air-source water service: `NL_COP_ASHP_water`

Available alternatives that require an explicit PI decision before scientific
use:

- Air-source floor sink: `NL_COP_ASHP_floor`
- Ground-source floor/radiator/water: `NL_COP_GSHP_floor`,
  `NL_COP_GSHP_radiator`, `NL_COP_GSHP_water`
- Groundwater-source floor/radiator/water: `NL_COP_WSHP_floor`,
  `NL_COP_WSHP_radiator`, `NL_COP_WSHP_water`

## Units And Interpretation

- `heat_profile_*` columns are interpreted by the scaffold as average thermal
  MW per annual TWh. The HP model multiplies by explicit annual TWh inputs and
  converts MW to kW before dividing by COP.
- `heat_demand_*` columns are interpreted as thermal MW. They are present in the
  file but are not the proposed primary scaffold route because they embed a
  national volume that is separate from the project's adoption/building-stock
  assumptions.
- `COP_*` columns are dimensionless coefficients of performance. The HP model
  divides component thermal load by the matching COP column before summing
  electric kW.
- Timestamps are hourly. E2.S3 downsampling to 15 minutes uses zero-order hold
  of average power values, which preserves energy.
- `utc_timestamp` is the canonical alignment timestamp. Local calendar
  information must be preserved through the shared weather member for audit and
  downstream calendar checks.

## Proposed Technology Defaults For PI Review

- Heat-pump source: propose ASHP for the first reviewable HP scaffold because it
  is the transparent default already wired through `src/hp_model.py` and matches
  the `NL_COP_ASHP_*` columns. This is not an approval of ASHP as the scientific
  scenario.
- Space-heating sink: propose radiator for the scaffold default via
  `NL_COP_ASHP_radiator`. The floor sink alternative may be appropriate for a
  lower-temperature building stock, but that would be a distinct assumption.
- Water heating: propose that domestic hot water can be included only when the
  PI approves explicit annual water-heat TWh scaling. Space-only and
  space-plus-water variants should not be mixed without a signed scenario
  definition.
- Building classes: propose keeping SFH, MFH, and COM separate so annual TWh
  scaling can be reviewed per class and so omission of any class is visible.
- Geography: propose Dutch `NL` columns for the HP source packet, while flagging
  the country-aggregation mismatch with the benchmark grid provenance as a PI
  decision item.

## Annual Scaling Inputs Still Needed

D-003 does not by itself provide the approved annual heat volume for this
project. Before D-003 can be used as scientific HP input, the PI must approve or
assign a source for:

- annual space-heating TWh for each selected class: `SFH`, `MFH`, `COM`;
- annual water-heating TWh for each selected class if water heating is included;
- whether those annual TWh values represent final thermal demand, useful heat,
  electrified heat-pump-served heat, or another boundary;
- whether scaling is fixed for the E2.S3 scaffold or varies by planning year,
  adoption scenario, or building class.

The HP model currently requires these TWh values explicitly and raises an error
when none are supplied. This is intentional: it prevents D-003 signoff from
silently approving an adoption volume.

## Shared Weather And Cold-Spell Blockers

ALEA-001 requires HP and PV to consume the same paired weather realization with
one canonical calendar. Q-8 remains the blocker for the neutral shared weather
contract path. The HP scaffold preserves `shared_weather_driver_id`,
`member_id`, UTC/local timestamps, source/provenance, and PV/irradiance field
names when a shared weather member is supplied, but it should consume the final
shared contract once that path is approved.

Important interpretation issue for PI review: When2Heat heat profiles and COPs
are already weather-derived from OPSD's reanalysis workflow. The current HP
pipeline aligns a selected When2Heat profile to the shared weather member for
calendar and audit identity, but it does not rederive the hourly heat demand or
COP from the PV/weather member temperature. Final acceptance therefore still
needs a real paired-weather cold-spell sanity check and a PI decision on whether
this source-use relationship is scientifically adequate.

## Remaining Ambiguities

- Country/geography: whether Dutch country-aggregated profiles are acceptable
  for the intended benchmark grid and local weather pairing.
- Temperature basis: whether OPSD reanalysis-driven heat/COP series can be used
  alongside the future shared PV/weather realization, and what consistency
  criterion the cold-spell check must satisfy.
- Technology mix: whether ASHP radiator is a scenario default, a scaffold-only
  placeholder, or replaced by floor, GSHP, WSHP, or a weighted mix.
- Water heating: whether to include water heating in the primary HP layer and
  how to source its annual TWh scaling.
- Citation wording: OPSD citation recommendations still need PI confirmation
  before manuscript use.

## Decision Request For PI

This packet asks the PI to decide later, not here:

- whether D-003 can be signed for HP source use;
- which exact Dutch heat profile and COP columns are approved;
- which annual TWh scaling source and boundary are approved;
- whether the real paired-weather cold-spell acceptance criterion is sufficient
  once Q-8 is resolved.

Until those decisions are signed, E2.S3 remains source-ready/scaffolded rather
than accepted.
