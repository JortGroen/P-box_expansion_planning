# E2.S3 HP-001 Value-Binding Readiness Packet

Decision packet ID: `E2-S3-HP001-VALUE-BINDING-READINESS`

Status: proposed value-binding draft only. D013-PBL-MAPPING/A-015 approves the PBL indicator mapping, and PR #176 added the fail-closed formula/config guard. This packet prepares the next binding shape, but it does not approve annual HP TWh values, 2035 HP adoption/electrification, D-004 or cold-spell acceptance, net-load/event/`P(E)`, capacity-screen conclusions, threshold runs, manuscript numbers, or probability results.

## Decision Requested

Before any HP-001 annual values can become executable, the PI still needs to approve or amend all five remaining choices:

| Required approval key | Candidate in this draft | Why it remains unsigned |
| --- | --- | --- |
| `value_column` | `Referentie_2030` from PBL `Alkmaar_strategie.csv` | A-015 maps indicators, not the reference/scenario column. |
| `denominator` | `I11_woningequivalenten [Woning]` | The formula uses PBL residential WEQ as the multiplier for `[GJ/weq/jaar]` intensities. |
| `unit_conversion` | Divide GJ/year by `3,600,000` to obtain TWh/year | The conversion is simple, but becomes part of the signed scientific formula. |
| `sfh_mfh_split` | CBS 85035NED count-share split for Alkmaar `GM0361` | This allocates local heat to SFH/MFH without measured class-specific heat demand. |
| `adoption_electrification` | Separate signed 2035 HP service fraction or count scenario | Local heat demand is not the same as 2035 HP-served demand; DHW service must be explicit. |

## Draft Binding Artifact

`data.get_hp_scaling.build_hp001_value_binding_readiness_packet()` now returns a machine-readable draft with:

- `source_inputs_under_review` for the PBL/CBS fields, conversion divisor, and pending adoption scenario;
- `local_heat_demand_diagnostics_unsigned`, including the `H22` diagnostic gap against `H23 + H24`;
- four `component_value_drafts_unsigned_before_2035_adoption` records preserving `SFH/MFH` and `space/water` traceability;
- `approval_state` with empty `approval_ids`, all five missing approval keys, and `executable_binding_allowed = false`;
- `future_binding_contract` pointing to the guarded HP adapter.

The draft values are carried forward from the already reviewed source-use proposal so the PI can see the exact numbers that would be bound later if the route is approved. They remain unsigned local-heat diagnostics before any 2035 adoption/electrification multiplier.

## Fail-Closed Adapter

`src.hp_model.hp001_local_scaling_config_from_value_binding_record(...)` is the future handoff from a value-binding packet into `HP001LocalScalingConfig`.

It refuses to return a config unless:

1. packet `status` is exactly `approved_for_executable_value_binding`;
2. the packet carries all five required approval IDs;
3. the four HP-001 components are present as `SFH/MFH` by `space/water` annual values;
4. the resulting `HP001LocalScalingConfig` passes the existing signed-scaling guard.

The current packet deliberately fails this adapter because it is proposed and has no approval IDs. That is the intended state until PI approval.

## What This Enables Later

If the PI signs or amends the five remaining choices, a follow-up PR can update the value-binding packet status, record the approval IDs, and then use the adapter to create the signed `HP001LocalScalingConfig`. That follow-up would still not authorize D-004/cold-spell acceptance or integrated net-load/event/`P(E)` analysis by itself.

## Suggested STATUS Update

`E2.S3 HP model | C | in-progress | HP-001 value-binding readiness packet and guarded adapter prepared; remaining value-column, denominator, conversion, split, 2035 adoption/electrification, D-004/cold-spell acceptance, and integrated analysis pending | PR: <this PR>`
