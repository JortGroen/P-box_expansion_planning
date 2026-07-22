# E2.S3 HP-001 Local Scaling Source-Use Proposal

Decision packet ID: `E2-S3-HP-LOCAL-SCALING-SOURCE-USE-PROPOSAL`

Status: PI-facing proposal only. D-013 retrieval/checksum route is approved for evidence use, and HP-001 approves the When2Heat Dutch residential shape/COP boundary. This packet proposes how the retrieved CBS/PBL evidence could become annual local HP-001 thermal scaling inputs after PI approval. It does not make any annual TWh value executable, sign 2035 heat-pump adoption, sign PBL columns or unit conversions, sign D-004, run paired-weather/cold-spell acceptance, run net-load/event/`P(E)`/threshold/capacity-screen analysis, or produce manuscript numbers.

## Decision Requested

Agent C asks the PI to decide whether the following local scaling route is scientifically acceptable for HP-001:

1. Use PBL Startanalyse 2025 Alkmaar `Alkmaar_strategie.csv` residential heat-demand indicators as local useful-thermal intensity evidence.
2. Use the PBL neighbourhood `I11_woningequivalenten [Woning]` column as the denominator for converting `[GJ/weq/jaar]` intensities to local annual residential thermal demand.
3. Use CBS StatLine `85035NED` Alkmaar `2026JJ00` dwelling stock as the SFH/MFH class crosswalk and class split.
4. Keep 2035 HP adoption/electrification as a separate multiplier that still needs a signed source or scenario.

Agent C recommendation: approve the route structure only after confirming the PBL indicator definitions, and keep the first executable value PR behind a separate PI approval of exact indicators, the split rule, and 2035 adoption assumptions.

## Exact Candidate PBL Fields

Source: D-013 PBL Startanalyse 2025 Alkmaar ZIP, `data/raw/hp_scaling/pbl_startanalyse_2025_alkmaar.zip`, file `Alkmaar_strategie.csv`. The schema inspection found `Code_Indicator`/`Eenheid` pairs and value columns including `Referentie_2023`, `Referentie_2030`, `Laagste_Nationale_Kosten`, `Strategie_1`, and technology/pathway variants such as `Variant_s1a_B_LuchtWP`.

Recommended candidate for local residential heat demand, subject to PI approval:

| End use | Candidate indicator | Unit | Candidate value column | Interpretation proposed for review |
|---|---|---|---|---|
| Space heat | `H23_Vraag_RV_w` | `[GJ/weq/jaar]` | `Referentie_2030` | Residential space-heating useful-thermal intensity per residential dwelling equivalent. |
| Domestic hot water | `H24_Vraag_TW_w` | `[GJ/weq/jaar]` | `Referentie_2030` | Residential tap-water/DHW useful-thermal intensity per residential dwelling equivalent. |
| Residential total heat diagnostic | `H22_Vraag_totaal_w` | `[GJ/weq/jaar]` | `Referentie_2030` | Diagnostic check on residential total heat demand; not a substitute for preserving space and DHW separately. |

Context indicators, not recommended as the HP-001 primary split unless the PI chooses a broader building boundary:

| Indicator | Unit | Why it is context only |
|---|---|---|
| `H01_Vraag_totaal` | `[GJ/weq/jaar]` | Appears to be total heat-demand intensity and may include more than the residential HP-001 boundary. |
| `H02_Vraag_RV` | `[GJ/weq/jaar]` | Space-heating context without the residential `_w` suffix. |
| `H03_Vraag_TW` | `[GJ/weq/jaar]` | Tap-water/DHW context without the residential `_w` suffix. |
| `A02_Aansl_eWP` | `[aantal]` | Electric-heat-pump connection/pathway output, not signed as 2035 adoption. |
| `A07_Aandeel_eWP_WEQ` | `[%]` | Electric-heat-pump share/pathway output, not signed as 2035 adoption. |
| `A08_Aandeel_eWP_GJ` | `[%]` | Electric-heat-pump heat-share/pathway output, not signed as 2035 adoption. |

The recommended value column is `Referentie_2030` because it is a reference heat-demand column rather than a pathway optimization result. `Variant_s1a_B_LuchtWP` is useful sensitivity/context if the PI wants an all-air-heat-pump pathway comparison, but it should not become the 2035 adoption assumption by implication.

## Candidate CBS Denominator And Crosswalk

Source: D-013 CBS StatLine `85035NED`, Alkmaar `GM0361`, period `2026JJ00`, `Woningkenmerk = T001727` (`Totaal woningen`), topic `BeginstandWoningvoorraad_1` with unit `aantal`.

| HP class | CBS key | CBS title | 2026 count | Mean area column available |
|---|---|---|---:|---:|
| SFH | `ZW10290` | `Eengezinswoningen totaal` | 33,684 | 124 m2 |
| MFH | `ZW10340` | `Meergezinswoningen totaal` | 21,461 | 74 m2 |
| Total | `T001100` | `Totaal woningen` | 55,145 | 104 m2 |

Detailed SFH audit keys available in the same table are `ZW10320` (`Vrijstaande woning`), `ZW10300` (`2-onder-1-kapwoning`), `ZW25806` (`Hoekwoning`), `ZW25805` (`Tussenwoning`), and `ZW25809` (`Onbekend woningtype eengezinswoning`). These sum to the CBS SFH total for `2026JJ00` and can be retained as crosswalk diagnostics.

## Proposed Formula

Let `b` index PBL neighbourhood rows, `u` be `space` or `water`, and `c` be `SFH` or `MFH`.

Candidate PBL-to-local thermal demand:

```text
H_local_TWh[u] =
    sum_b intensity_GJ_per_weq_year[b,u] * WEQ_woning[b]
  / 3,600,000
```

where:

- `intensity_GJ_per_weq_year[b,"space"] = H23_Vraag_RV_w[b, Referentie_2030]`;
- `intensity_GJ_per_weq_year[b,"water"] = H24_Vraag_TW_w[b, Referentie_2030]`;
- `WEQ_woning[b] = I11_woningequivalenten [Woning]` from `Alkmaar_strategie.csv`;
- `3,600,000` converts GJ to TWh.

Candidate SFH/MFH allocation, pending PI choice:

```text
H_local_TWh[c,u] = H_local_TWh[u] * w_class[c]
```

where the cleanest denominator is CBS `85035NED` stock by class. Two possible class weights are exposed for PI review:

| Split option | Formula | Role |
|---|---|---|
| Count-share split | `w_class[c] = N_c / (N_SFH + N_MFH)` | Minimal use of CBS dwelling counts; does not assume area drives heat demand. |
| Area-weighted split | `w_class[c] = N_c * A_c / sum_k N_k * A_k` | Uses CBS average area as a heat-demand proxy; more physical, but a scientific assumption requiring PI signoff. |

Then 2035 HP-served annual thermal demand remains a separate adoption/service multiplier:

```text
H_HP_TWh[c,u,s] = H_local_TWh[c,u] * f_HP_service[c,u,s]
```

where `f_HP_service[c,u,s]` must come from a signed 2035 adoption/electrification scenario or source. For HP-001, domestic hot water can share the space-heating adoption fraction only if the signed scenario represents full-electric/all-heat residential HP service. Hybrid-only scenarios require a separate DHW service fraction or must remain sensitivity-only.

## Unsigned Candidate Values For Review

The following numbers are mechanically computed from the retrieved D-013 files to make the PI decision concrete. They are unsigned, not executable, and not used in any integrated analysis.

Using `Referentie_2030`, `H23_Vraag_RV_w`, `H24_Vraag_TW_w`, and PBL `I11_woningequivalenten [Woning]` over 66 neighbourhood rows:

| End use | PBL indicator | WEQ summed | Candidate local thermal demand |
|---|---|---:|---:|
| Space heat | `H23_Vraag_RV_w` | 67,422 | 0.362059444 TWh/year |
| Domestic hot water | `H24_Vraag_TW_w` | 67,422 | 0.097897778 TWh/year |
| Residential total diagnostic | `H22_Vraag_totaal_w` | 67,422 | 0.634250556 TWh/year |

The difference between `H22` and `H23 + H24` indicates other residential heat/end-use categories in PBL. HP-001 should preserve only the signed space and DHW components unless the PI approves a broader interpretation.

Candidate class allocations before any 2035 HP adoption multiplier:

| Split option | Class | Space heat | Domestic hot water |
|---|---|---:|---:|
| Count-share | SFH | 0.221155323 TWh/year | 0.059798509 TWh/year |
| Count-share | MFH | 0.140904121 TWh/year | 0.038099269 TWh/year |
| Area-weighted | SFH | 0.262319868 TWh/year | 0.070929050 TWh/year |
| Area-weighted | MFH | 0.099739576 TWh/year | 0.026968728 TWh/year |

Recommended packet position: treat these as value-proposal evidence only. If the PI signs exact columns and split rule, a follow-up can record the selected values in machine-readable metadata with approval IDs, but HP loads should still remain non-executable until the 2035 HP adoption/electrification multiplier is signed.

## Space/DHW Separation

The proposed route keeps HP-001 end uses separate at every stage:

1. PBL `H23_Vraag_RV_w` feeds only `space` demand.
2. PBL `H24_Vraag_TW_w` feeds only `water` demand.
3. CBS SFH/MFH weights allocate each end use independently.
4. The future HP component metadata records four annual thermal values: `SFH-space`, `MFH-space`, `SFH-water`, and `MFH-water`.
5. The HP model then maps those values to the already approved When2Heat shape/COP pairs: `NL_heat_profile_space_SFH` and `NL_heat_profile_space_MFH` with `NL_COP_ASHP_radiator`; `NL_heat_profile_water_SFH` and `NL_heat_profile_water_MFH` with `NL_COP_ASHP_water`.

No commercial heat enters the HP-001 primary route.

## Remaining 2035 Adoption Need

This packet does not identify a signed 2035 HP adoption/electrification assumption. The PI still needs to choose one of these before any HP annual component values become executable:

| Adoption route | What would need signing | Boundary risk |
|---|---|---|
| External 2035 residential HP scenario | Source, scenario branch, class split, full-electric versus hybrid boundary, and whether DHW is served. | Best separation between heat demand and adoption, but requires another source. |
| PBL pathway-as-adoption sensitivity | Exact PBL strategy/variant columns such as `A02_Aansl_eWP`, `A07_Aandeel_eWP_WEQ`, or `A08_Aandeel_eWP_GJ`, plus interpretation as 2035 service fraction/count. | Startanalyse pathway outputs may not be a time-specific adoption forecast. |
| Author-specified adoption scenario | Low/middle/high fractions with explicit approval IDs and sensitivity labels. | Scientifically transparent but not source-estimated. |

Agent C recommendation: keep local annual heat demand and 2035 HP adoption separate. Use PBL H-series indicators for candidate heat demand only if PI confirms their interpretation; use an external or explicitly author-specified 2035 adoption scenario for `f_HP_service`.

## What Becomes Executable After PI Approval

After PI signs exact PBL indicators, the reference/pathway column, the PBL WEQ denominator, the CBS class split rule, unit conversion, and 2035 HP adoption multipliers, a follow-up implementation can:

1. write a guarded HP scaling metadata file with selected `H_HP_TWh[c,u,s]` values and approval IDs;
2. pass `space_heat_twh_by_class` and `water_heat_twh_by_class` into `hp001_residential_when2heat_components`;
3. preserve SFH/MFH and space/DHW provenance through HP component outputs; and
4. keep D-004 paired-weather/cold-spell acceptance as a separate gate before integrated use.

This does not authorize net-load/event/`P(E)`/threshold/capacity-screen analysis or manuscript results.

## Suggested STATUS Update

`E2.S3 HP model | C | in-progress | D-013 local HP scaling source-use proposal prepared with exact PBL/CBS candidate fields and unsigned value examples; 2035 HP adoption, D-004 acceptance, cold-spell tolerances, and integrated analysis pending | PR: <this PR>`