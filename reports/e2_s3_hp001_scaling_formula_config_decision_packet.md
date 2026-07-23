# E2.S3 HP-001 Scaling Formula/Config Decision Packet

Decision packet ID: `E2-S3-HP001-SCALING-FORMULA-CONFIG`

Status: proposed remaining-choice packet. D013-PBL-MAPPING/A-015 approves only the PBL indicator mapping assumption. This packet does not make annual HP TWh values executable, sign 2035 HP adoption/electrification, sign D-004 or cold-spell acceptance, run net-load/event/`P(E)`, produce capacity-screen conclusions, threshold runs, manuscript numbers, or probability results.

## Decision Requested

Approve or amend the remaining HP-001 local-scaling choices before a later value-binding PR:

| Choice | Agent C recommendation | Why this is still a PI decision |
| --- | --- | --- |
| PBL value column | Use `Referentie_2030` from `Alkmaar_strategie.csv`. | A-015 approves row meaning only; it does not decide which PBL scenario/reference column becomes the heat-demand value. |
| PBL denominator | Use `I11_woningequivalenten [Woning]`. | The candidate heat rows are `[GJ/weq/jaar]`; using the PBL residential WEQ denominator must be signed before values are executable. |
| Unit conversion | Convert summed GJ/year to TWh/year by dividing by `3,600,000`. | The conversion is straightforward, but it becomes part of the scientific formula and should be signed with the value route. |
| SFH/MFH split | Use CBS 85035NED count-share split between `Eengezinswoningen totaal` and `Meergezinswoningen totaal`. | This allocates local heat over HP-001 classes without measured class-specific heat demand. Area-weighting remains an optional signed sensitivity. |
| 2035 adoption/electrification | Require a separate signed 2035 HP service fraction/count scenario. | Local heat demand is not the same thing as HP-served 2035 demand; DHW service must be explicit. |

## Formula Under Review

For PBL neighbourhood row `b` and end use `u`:

```text
H_local_TWh[u] =
    sum_b intensity_GJ_per_weq_year[b,u] * WEQ_woning[b]
  / 3,600,000
```

where the candidate intensity fields are:

- `space`: `H23_Vraag_RV_w[b, Referentie_2030]`
- `water`: `H24_Vraag_TW_w[b, Referentie_2030]`
- diagnostic total only: `H22_Vraag_totaal_w[b, Referentie_2030]`
- denominator: `I11_woningequivalenten [Woning]`

Then allocate each end use separately:

```text
H_local_TWh[c,u] = H_local_TWh[u] * w_class[c]
```

The recommended primary class weight is count share:

```text
w_class[c] = N_c / (N_SFH + N_MFH)
```

with `N_SFH` from CBS 85035NED `Eengezinswoningen totaal` and `N_MFH` from `Meergezinswoningen totaal` for Alkmaar `GM0361`. Area-weighted allocation can remain a sensitivity if the PI signs area as a heat-demand proxy.

Finally, executable HP-served thermal demand still needs a signed 2035 service multiplier:

```text
H_HP_TWh[c,u,s] = H_local_TWh[c,u] * f_HP_service[c,u,s]
```

For HP-001, domestic hot water may share the same adoption/electrification fraction as space heat only if the signed scenario represents full residential HP service for both end uses.

## Guarded Config Scaffold

This PR adds `src.hp_model.HP001LocalScalingConfig` and a guarded builder:

- `require_signed_hp001_local_scaling_config(config)`
- `hp001_components_from_local_scaling_config(config)`

The builder fails closed until the config records non-empty approval IDs for:

1. `value_column`
2. `denominator`
3. `unit_conversion`
4. `sfh_mfh_split`
5. `adoption_electrification`

The already-approved A-015/D013-PBL-MAPPING indicator mapping is recorded separately as `indicator_mapping_approval_id`; it does not satisfy any of the remaining five approvals.

## What Becomes Executable Later

After PI approval of the remaining five choices, a follow-up PR can bind signed component values into a guarded metadata/config artifact and pass the four HP-001 annual thermal inputs into `hp001_components_from_local_scaling_config`:

- `SFH` space
- `MFH` space
- `SFH` domestic hot water
- `MFH` domestic hot water

That later value-binding still would not by itself run D-004/cold-spell acceptance, net-load, event analysis, `P(E)`, capacity screens, threshold results, manuscript results, or probability analysis.

## Suggested STATUS Update

`E2.S3 HP model | C | in-progress | HP-001 local-scaling formula/config guard and PI decision packet prepared; remaining value-column, denominator, conversion, split, 2035 adoption/electrification, D-004/cold-spell acceptance, and integrated analysis pending | PR: <this PR>`
