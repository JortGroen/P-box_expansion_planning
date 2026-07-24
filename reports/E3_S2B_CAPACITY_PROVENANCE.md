# E3.S2b Capacity Provenance

Task: E3.S2b future-layer capacity/domain screen prerequisite.
Status: metadata/provenance packet only. This report records decision-transformer capacity facts for PI review and later E3.S2b pre-run readiness. It does not choose total versus firm capacity.

## Boundary

This packet does not load component trajectories, aggregate real net load, execute IC-2, detect events, compute `P(E)`, use A-013/G2 numerical values, classify capacity/domain cases, choose a denominator, or produce manuscript numbers. The values below are grid input/provenance facts needed before a later capacity/domain screen can report raw MVA under both conventions.

## Evidence

- Versioned input: `reports/e3_s2b_capacity_provenance_input.json`
- Machine-readable capacity packet: `reports/e3_s2b_capacity_provenance_packet.json`
- Claim-source manifest: `reports/e3_s2b_capacity_provenance_manifest.json`
- Generated from git commit: `0595b829b560a9850d06224546f2cdff80143c5a`
- Command: `.\.venv\Scripts\python.exe reports\e3_s2b_generate_capacity_provenance.py`

## Capacity Packet Summary

| Field | Value |
| --- | --- |
| Field-complete for PI review / later E3.S2b use | `true` |
| Status | `ready_for_pi_capacity_provenance_review` |
| Grid | `1-MV-semiurb--0-sw` |
| Decision asset | `g0_decision_transformer` |
| Transformer indices | `0, 1` |
| Unit nameplates | `40000, 40000` kVA |
| Total aggregate nameplate | `80000` kVA |
| Firm `(n-1)` aggregate nameplate | `40000` kVA |
| Firm outage convention | firm (n-1) aggregate nameplate equals total selected decision-transformer nameplate minus the largest in-service selected unit nameplate |
| Capacity convention status | `pending_g1_a2_e3_s2b` |
| Busbar/tie status | Closed busbar-parallel transformer bank: busbar/tie switches [0, 5] closed=True; associated transformer circuit-breaker switches [1, 2, 3, 4] closed=True; equal tap positions=True; selected transformer units in service=True. |
| Firm primary follow-up | Actual one-transformer-out AC validation required before firm primary use |

## Transformer Records

| trafo_index | name | hv_bus | lv_bus | sn_mva | sn_kva | parallel | tap_pos | in_service |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | HV1-MV2.101-Trafo1 | 0 | 2 | 40 | 40000 | 1 | 0 | True |
| 1 | HV1-MV2.101-Trafo2 | 1 | 3 | 40 | 40000 | 1 | 0 | True |

## Switch Records

| switch_index | role | bus | element | et | closed | type | name |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | busbar_tie | 0 | 1 | b | True | CB | HV1 Switch 316 |
| 5 | busbar_tie | 2 | 3 | b | True | CB | MV2.101 MV Sectionalizer1 |
| 1 | transformer_circuit_breaker | 0 | 0 | t | True | CB | HV1-MV2.101-Trafo1 CB HV-Side |
| 2 | transformer_circuit_breaker | 2 | 0 | t | True | CB | HV1-MV2.101-Trafo1 CB MV-Side |
| 3 | transformer_circuit_breaker | 1 | 1 | t | True | CB | HV1-MV2.101-Trafo2 CB HV-Side |
| 4 | transformer_circuit_breaker | 3 | 1 | t | True | CB | HV1-MV2.101-Trafo2 CB MV-Side |

## Future E3.S2b Raw-MVA Reporting Fields

| field | unit | denominator_field | meaning |
| --- | --- | --- | --- |
| raw_import_mva | MVA | -- | un-normalized import-direction apparent power at the decision transformer |
| raw_export_mva | MVA | -- | un-normalized export-direction apparent power at the decision transformer, reported separately from the primary import event |
| loading_total_nameplate_pu | -- | total_nameplate_kva | raw MVA divided by aggregate installed selected-unit nameplate |
| loading_firm_n_minus_1_pu | -- | firm_n_minus_1_nameplate_kva | raw MVA divided by largest-unit-out firm nameplate; diagnostic until PI selects and AC-validates firm use |

The future E3.S2b screen must report raw import/export MVA and both loading ratios for every predeclared case. These fields are reporting obligations only; they do not select a denominator or classify a case.

## Blocker Manifest

| code | blocker IDs | message |
| --- | --- | --- |
| none | -- | -- |

## Supporting Evidence Checksums

| Path | SHA-256 |
| --- | --- |
| reports/G1_A2_GRID_ERROR_AND_CAPACITY_PROTOCOL.md | ae03e2081b4e2275d8dbfd6711ac4dd1a08c94ec2b256be107138b2d9c3f6de5 |
| reports/grid_inventory.md | db609911f413bf0a30cbfc0a6d502d773b4d139277976296c3d0af28ad0ec128 |
| reports/transformer_headroom_diagnostic.md | bb9a73d3ed61b8d16d01495a0a9aa6362047fab23b2cef2fc0190b995be07d25 |
| reports/transformer_headroom_evidence.json | e68dc9331b709e583e6502744a242e3004f7e6b273ab9e3aa18c3814a54118ae |

## Interpretation

The selected primary-grid decision transformer is a two-unit 40 MVA + 40 MVA bank with the configured busbar/tie and transformer circuit-breaker switches closed. The candidate total-nameplate denominator is 80 MVA. The candidate firm diagnostic denominator records largest-unit-out `(n-1)` nameplate as 40 MVA. G1-A2 keeps both conventions open until the later manifested E3.S2b screen reports raw MVA and both ratios before probabilistic-result inspection.

Firm 40 MVA use here remains a provenance and diagnostic convention. If the PI later selects firm capacity as the primary criterion, E3.S3 must validate the actual one-transformer-out AC topology before paper-use results.
