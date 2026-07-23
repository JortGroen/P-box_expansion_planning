# E2.S3 HP-001 Readiness Approval Checklist

Decision packet ID: `E2-S3-HP001-READINESS-APPROVAL-CHECKLIST`

Status: proposed approval checklist only. This packet does not approve annual HP TWh values, 2035 HP adoption/electrification, D-004 paired-weather acceptance, cold-spell tolerances, net-load/event/`P(E)`, capacity-screen conclusions, threshold runs, manuscript numbers, or probability results.

## Why This Exists

The HP-001 shape/COP boundary and D013-PBL-MAPPING/A-015 indicator mapping are now approved, and the value-binding scaffold is fail-closed. The remaining blockers are spread across annual value binding and weather/cold-spell acceptance. This packet collects those blockers into one PI-facing checklist so a future approval can be precise and auditable.

## Current Signed Foundation

- HP-001 approves residential SFH/MFH space heat plus domestic hot water using D-003 When2Heat shape/COP columns; commercial heat remains outside the primary run.
- D013-PBL-MAPPING/A-015 approves only the PBL indicator mapping for `_w`, `_u`, `H22`, `H23`, and `H24`; it does not approve values or formulas.
- WEATHER-001 requires HP and PV to consume the same shared weather member identity and calendar.
- D004-SOURCE-MEMBER-ACCEPTANCE approves D-004 source/member use for internal first-screen work only; final paired/cold-spell acceptance remains pending.
- E2-S3-COLD-SPELL-ACCEPTANCE-DESIGN approves the diagnostic design, but not numerical tolerances.

## Approval Checklist

| Approval key | Candidate | Why it is still a blocker |
|---|---|---|
| `value_column` | PBL `Referentie_2030` | Needed before using PBL values as local annual heat-demand input. |
| `denominator` | PBL `I11_woningequivalenten [Woning]` | Needed before multiplying PBL intensities by dwelling-equivalent counts. |
| `unit_conversion` | Divide GJ/year by `3,600,000` to obtain TWh/year | Needed before converting candidate thermal demand into annual TWh scales. |
| `sfh_mfh_split` | CBS 85035NED count-share allocation | Needed before assigning local space/DHW heat demand to SFH and MFH classes. |
| `adoption_electrification` | Separate signed 2035 HP service/adoption/electrification scenario | Needed before local heat demand becomes 2035 HP-served demand. |
| `d004_paired_weather_acceptance` | Exact WEATHER-001 identity/calendar equality before HP/PV paired diagnostics | Needed before treating HP and PV profiles as driven by an accepted same-weather realization. |
| `cold_spell_tolerances` | Future signed numerical coldest-window and near-freezing diagnostic tolerances | Needed before accepting When2Heat-derived HP behavior under selected D-004 cold-weather members. |

## Fail-Closed Implementation

The existing value-binding path remains guarded by `src.hp_model.hp001_local_scaling_config_from_value_binding_record(...)` and `src.hp_model.require_signed_hp001_local_scaling_config(...)`. This PR adds `src.hp_model.require_hp001_final_readiness_approvals(...)` for the broader final-readiness gate: annual value-binding approvals alone are insufficient because D-004 paired-weather acceptance and cold-spell tolerances also remain required.

The generated metadata packet is `data/metadata/hp_scaling/hp001_alkmaar_gm0361_readiness_approval_checklist.json`.

## What Approval Would Unlock

If the PI approves or amends the five annual value-binding choices, a later PR can update the value-binding packet status and approval IDs so the guarded adapter can build signed HP-001 components. That would still not authorize integrated HP use until D-004 paired-weather acceptance evidence and cold-spell tolerances are separately signed.

## Suggested STATUS Update

E2.S3 HP remains scaffold/readiness. HP-001 shape/COP and D013-PBL-MAPPING are approved, but annual value binding, 2035 adoption/electrification, D-004 paired-weather acceptance, and cold-spell tolerances remain unsigned; no integrated analysis or manuscript results have been produced.
