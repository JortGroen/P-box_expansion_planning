# E2.S3 HP Annual Scaling Evidence Packet

Status: PI decision packet only. D-003 remains proposed and unsigned. This
packet prepares source-backed annual Dutch heat-demand scaling evidence for the
heat-pump scaffold; it does not select a final scaling input, sign D-003, run
net-load integration, run event analysis, estimate probabilities, or produce
manuscript results.

## Purpose

The E2.S3 HP loader consumes When2Heat normalized `heat_profile_*` columns as
average thermal MW per annual TWh, so annual thermal TWh inputs must be supplied
explicitly. This packet identifies the annual Dutch heat-demand values available
inside the retrieved D-003 file and frames how they could be used if the PI later
approves the source boundary.

## Source And File Identity

- Source: When2Heat Heating Profiles, Open Power System Data.
- Package version: `2023-07-27`.
- File: `when2heat.csv`.
- DOI: `https://doi.org/10.25832/when2heat/2023-07-27`.
- URL: `https://data.open-power-system-data.org/when2heat/2023-07-27/when2heat.csv`.
- License recorded for review: Creative Commons Attribution 4.0.
- Local raw path: `data/raw/when2heat/when2heat.csv` (ignored, not committed).
- Metadata path:
  `data/metadata/when2heat/d003_when2heat_csv_metadata.json`.
- Recorded byte size: `328400976`.
- Recorded SHA-256:
  `f1f71790158d1de08403eea32dea7a2732050870c499938135606d9d7faac0fa`.

## Scan Method

The evidence scan read only the timestamp columns and Dutch heat-demand columns
from the ignored raw CSV using the known D-003 dialect: semicolon delimiter and
comma decimals. It summed hourly average MW over complete local years and
converted MWh to TWh by dividing by `1,000,000`.

Formula:

```text
annual_TWh = sum(hourly_MW over local-year rows) / 1,000,000
```

The scan used `cet_cest_timestamp` to assign local calendar years, matching the
source's local-calendar framing. `utc_timestamp` remains the canonical alignment
timestamp for HP/PV integration.

Cheap scan evidence:

- Rows read: `131483`.
- Nonzero Dutch `heat_demand_*` rows: `70122`.
- First nonzero row: UTC `2007-12-31T22:00:00Z`, local
  `2007-12-31T23:00:00+0100`.
- Last nonzero row: UTC `2015-12-31T23:00:00Z`, local
  `2016-01-01T00:00:00+0100`.
- Meaningful annual Dutch heat-demand coverage from these columns is therefore
  local years `2008` through `2015`. The tiny local-2016 value is the boundary
  timestamp and should not be treated as a full annual input.
- Local-year and UTC-year mean totals differed by at most about `0.0012 TWh`
  in this selected-column scan; the local-year convention is retained for
  source-use review.

No broad full-file completeness scan was run, and no external data were
downloaded.

## Proposed Candidate Scaling Values

If the PI approves using the When2Heat Dutch heat-demand volume columns as the
annual scaling source, the clearest candidate is the 2008-2015 local-year mean.
These values are thermal heat-demand TWh candidates, not electric HP TWh and not
approved adoption/electrified-share inputs.

| Candidate input | Column | 2008-2015 mean TWh/year | Min TWh/year | Max TWh/year |
|---|---:|---:|---:|---:|
| Space heat, single-family houses | `NL_heat_demand_space_SFH` | 38.585 | 30.122 | 48.050 |
| Space heat, multi-family houses | `NL_heat_demand_space_MFH` | 16.537 | 12.910 | 20.593 |
| Space heat, commercial buildings | `NL_heat_demand_space_COM` | 31.780 | 26.036 | 38.312 |
| Water heat, single-family houses | `NL_heat_demand_water_SFH` | 9.624 | 9.149 | 10.200 |
| Water heat, multi-family houses | `NL_heat_demand_water_MFH` | 4.124 | 3.921 | 4.371 |
| Water heat, commercial buildings | `NL_heat_demand_water_COM` | 6.204 | 6.118 | 6.356 |

Aggregate checks:

| Aggregate | Column | 2008-2015 mean TWh/year | Min TWh/year | Max TWh/year |
|---|---:|---:|---:|---:|
| Space heat total | `NL_heat_demand_space` | 86.900 | 69.066 | 106.953 |
| Water heat total | `NL_heat_demand_water` | 19.952 | 19.188 | 20.928 |
| Space plus water total | `NL_heat_demand_total` | 106.852 | 89.572 | 126.436 |

The class columns reproduce the aggregate columns to within small rounding
differences from the source file. Mean class shares over 2008-2015 are:

- Space heat: SFH `44.40%`, MFH `19.03%`, COM `36.57%`.
- Water heat: SFH `48.24%`, MFH `20.67%`, COM `31.09%`.
- Water heat share of total heat: `18.67%`.

## Boundary Interpretation

These candidate values come from When2Heat `heat_demand_*` columns and are
therefore country-level Dutch thermal heat-demand quantities as represented by
the OPSD/When2Heat method. They are not:

- approved HP electricity consumption;
- an approved 2035 electrified heat-pump adoption volume;
- a SimBench feeder-scale local heat-demand total;
- a building-stock forecast;
- a weather-member acceptance check; or
- a manuscript result.

The E2.S3 HP model would still convert thermal heat to electric kW by dividing
the matching normalized profile load by the selected COP column. For the current
source-use proposal, that means `NL_COP_ASHP_radiator` for space heat and
`NL_COP_ASHP_water` if water heating is included. Technology and sink choices
remain proposed and require PI approval before scientific use.

## Proposed Use Options For PI Review

Option A: space-only, class-specific Dutch annual scaling from When2Heat.
Use the three 2008-2015 mean space-heat values above with
`NL_heat_profile_space_SFH`, `NL_heat_profile_space_MFH`, and
`NL_heat_profile_space_COM`. This keeps water heating out of the primary HP
layer until the PI explicitly includes it.

Option B: space plus water, class-specific Dutch annual scaling from When2Heat.
Use all six 2008-2015 mean values above with the matching space and water
profile columns. This is more complete for building heat, but it requires a
clear PI decision that domestic hot water is in scope and that the water COP
route is acceptable.

Option C: do not use When2Heat volume columns as scaling inputs.
Use When2Heat only for shape/COP and obtain annual space/water TWh from a
separate Dutch building-energy/adoption source. This may better represent a
2035 electrified-heat scenario, but the separate source must be registered,
licensed, and signed before use.

Agent C recommendation for review: keep Option A or C as the conservative
primary route until the PI decides whether water heating and national
When2Heat-derived volumes match the paper's scenario boundary. Option B should
be a deliberate scenario, not an accidental consequence of source availability.

## Remaining PI Decisions

Before these values can become scientific HP inputs, the PI must decide:

- whether D-003 is signed for source use;
- whether the `heat_demand_*` volume columns may provide annual scaling, or
  whether annual TWh must come from a separate source;
- whether annual scaling represents total Dutch heat demand, heat-pump-served
  useful heat, final thermal demand, electrified 2035 heat, or another boundary;
- whether the country-level Dutch volume should be downscaled to a local
  SimBench-grid/service-area denominator before integration;
- whether water heating is included in the primary HP layer;
- whether SFH, MFH, and COM remain separate components or are aggregated; and
- how the Q-8 shared weather contract and real paired-weather cold-spell check
  affect final E2.S3 acceptance.

Until those decisions are signed, the HP layer remains source-ready and
review-limited rather than final accepted.

## Suggested STATUS Update

`E2.S3 HP model | C | in-progress | source-ready; annual scaling evidence packet prepared; D-003 unsigned and Q-8/cold-spell acceptance pending | PR: <this PR>`
