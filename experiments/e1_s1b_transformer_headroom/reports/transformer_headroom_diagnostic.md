# E1.S1b Transformer Headroom Diagnostic

Status: complete for E1.S1b review. This memo is the G1-C2 prerequisite
for the PI's total-versus-firm nameplate decision; it does not sign or
change G0, G1, or any denominator convention.

## Scope

This diagnostic uses SimBench scenario 0 full-year 15-minute profiles for
`1-MV-semiurb--0-sw` only. It reports deterministic headroom for the
existing baseline profiles and a linear multiplier to 0.95 p.u. under two
denominator conventions. The multiplier is a routing diagnostic only, not
a Dutch 2035 loading result, forecast, planning threshold, or scientific
claim; the E2/E3 technology layer does not yet exist.

## Evidence

- Input config: `experiments/e1_s1b_transformer_headroom/runner_config.json`
- Manifest: `experiments/e1_s1b_transformer_headroom/custom_evidence.json`
- Report: `experiments/e1_s1b_transformer_headroom/reports/transformer_headroom_diagnostic.md`
- Numeric table: `experiments/e1_s1b_transformer_headroom/data/transformer_headroom_diagnostic.csv`
- Prior inventory reference: `reports/grid_inventory.md`
- G1-A1 denominator/envelope reference:
  `reports/G1_A1_MODEL_ERROR_AMENDMENT_PROPOSAL.md`

## Decision Transformer And Parallel Operation

- Pandapower element table/indexes: `net.trafo` [0, 1]
- Unit count: 2
- Per-unit nameplate MVA: [40.0, 40.0]
- Busbar/tie status: Closed busbar-parallel transformer bank: busbar/tie switches [0, 5] closed=True; associated transformer circuit-breaker switches [1, 2, 3, 4] closed=True; equal tap positions=True; selected transformer units in service=True.

| trafo_index | name | hv_bus | lv_bus | sn_mva | parallel | tap_pos | in_service |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | HV1-MV2.101-Trafo1 | 0 | 2 | 40 | 1 | 0 | True |
| 1 | HV1-MV2.101-Trafo2 | 1 | 3 | 40 | 1 | 0 | True |

| switch_index | bus | element | et | closed | type | name |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 0 | 1 | b | True | CB | HV1 Switch 316 |
| 5 | 2 | 3 | b | True | CB | MV2.101 MV Sectionalizer1 |
| 1 | 0 | 0 | t | True | CB | HV1-MV2.101-Trafo1 CB HV-Side |
| 2 | 2 | 0 | t | True | CB | HV1-MV2.101-Trafo1 CB MV-Side |
| 3 | 1 | 1 | t | True | CB | HV1-MV2.101-Trafo2 CB HV-Side |
| 4 | 3 | 1 | t | True | CB | HV1-MV2.101-Trafo2 CB MV-Side |

## Total Versus Firm Headroom

| scenario | grid_code | transformer_indices | unit_count | unit_nameplate_mva | total_nameplate_mva | firm_n_minus_1_nameplate_mva | peak_import_mva | peak_import_timestamp | peak_import_loading_total_pu | peak_import_loading_firm_pu | multiplier_to_0_95_total | multiplier_to_0_95_firm | g0_total_nameplate_fallback_triggered | firm_capacity_fallback_triggered | firm_classifies_differently |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1-MV-semiurb--0-sw | [0, 1] | 2 | [40.0, 40.0] | 80 | 40 | 12.7316 | 2016-01-27T17:45:00+00:00 | 0.159145 | 0.31829 | 5.9694 | 2.9847 | False | False | False |

Firm convention used here: firm (n-1) is computed as total selected decision-transformer nameplate minus the single largest in-service unit nameplate. With two equal 40 MVA units, this leaves
one 40 MVA unit available.

The existing G0 fallback criterion for scenario-0 baseline loading is
`L_base > 0.85` under the currently
signed total-nameplate definition. Under that signed definition, the
criterion is triggered: `false`.

Firm capacity does not change the scenario-0 baseline fallback classification in this diagnostic, although it doubles the reported loading ratio for the two identical units.

## Implications For Model-Error Envelopes

- Additive p.u. envelopes depend on the selected nameplate denominator. A
  fixed MVA discrepancy divided by total nameplate is not the same p.u.
  value when divided by firm capacity.
- Relative envelopes are invariant to the nameplate convention because the
  same multiplicative factor applies to either denominator.

## Recommendation

Recommendation: keep the current total-nameplate convention for continuity with G0 unless the PI wants the study to represent firm `(n-1)` planning headroom. If firm capacity is selected later, update the denominator convention explicitly before freezing additive p.u. model-error envelopes.
