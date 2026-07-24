# E2.S3 HP001 Value-Binding Decision Candidates

Status: proposed packet and fail-closed automation only. This does not approve annual HP TWh values, 2035 adoption/electrification/service fractions, D-004 final paired-weather acceptance, cold-spell tolerances, net-load/event/P(E), capacity screens, thresholds, manuscript numbers, or probability results.

## Why This Exists

HP-001 approves the residential When2Heat shape/COP boundary, and D013-PBL-MAPPING/A-015 approves only the transparent PBL indicator mapping assumption. The remaining PI decision is still the local annual value-binding route: which value column, denominator, conversion, SFH/MFH split, and 2035 service/adoption/electrification assumption can turn public D-013 evidence into later executable HP component annual TWh values.

This PR adds a deterministic packet builder so the next approval surface is reproducible instead of copied by hand.

## What Changed

`data/get_hp_scaling.py --write-value-binding-candidates` now builds `data/metadata/hp_scaling/hp001_alkmaar_gm0361_value_binding_decision_candidates_blocker.json`.

The builder first verifies the ignored D-013 source artifacts against the D-013 retrieval manifest:

- CBS 85035NED Alkmaar dwelling stock/type JSON;
- PBL Startanalyse 2025 Alkmaar ZIP containing `Alkmaar_strategie.csv`.

If either raw artifact is missing or fails byte-size/SHA-256 verification, the packet fails closed and emits no candidate values. In this Agent C worktree the ignored raw files are absent, so the committed packet records `source_artifact_missing:cbs_85035ned_dwelling_stock` and `source_artifact_missing:pbl_startanalyse_2025_alkmaar`.

Fixture tests cover the real intended extraction path. When verified raw sources are present, the builder computes unsigned candidates from:

- PBL indicators: `H23_Vraag_RV_w` for residential space heat, `H24_Vraag_TW_w` for residential domestic hot water, and `H22_Vraag_totaal_w` as a diagnostic total;
- proposed value column: `Referentie_2030`;
- proposed denominator: `I11_woningequivalenten [Woning]`;
- approved inferred unit: `[GJ/weq/jaar]`;
- proposed conversion: `GJ/year / 3,600,000 = TWh/year`;
- proposed SFH/MFH allocation: CBS 85035NED count share;
- unsigned 2035 service-fraction options: candidate-only scenario multipliers.

## PI Decision Requested

Approve or amend these exact choices before annual HP values can become executable:

1. Use PBL `Referentie_2030` as the value column.
2. Use PBL `I11_woningequivalenten [Woning]` as the denominator.
3. Convert GJ/year to TWh/year by division by `3,600,000`.
4. Allocate SFH/MFH with CBS 85035NED count shares, or choose an alternative split rule.
5. Provide/sign a 2035 HP service/adoption/electrification route for space heat and DHW.
6. Separately resolve A-016 scenario consistency, D-004 final paired-weather acceptance, and cold-spell tolerances before integrated use.

## Non-Claims

The generated binding record is deliberately non-executable and remains rejected by `hp001_local_scaling_config_from_value_binding_record`. The packet does not generate HP profiles or component outputs and does not use confidential thesis values as provenance.

## Suggested STATUS Update

`E2.S3 HP model | C | in-progress | HP-001 value-binding candidate extractor/blocker packet added; raw D-013 artifacts missing locally so committed packet emits no values; annual value choices, 2035 adoption/electrification, A-016, D-004 paired acceptance, and cold-spell tolerances remain unsigned | PR: <this PR>`
