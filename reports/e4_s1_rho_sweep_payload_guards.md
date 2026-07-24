# E4.S1 Synthetic Rho-Sweep Payload Guards

Status: scaffold-only guard tightening; no G3 verdict and no paper-facing result.

This packet tightens the serialized boundary for the existing synthetic dense-rho sweep. The estimator still uses toy callbacks and canonical CRN sample seeds across rho values. The change is only at the manifest/report edge: a valid payload must now identify `e4s1-synthetic-rho-sweep-v1`, keep `use_status = synthetic-only`, keep `g3_status = pending-no-paper-facing-vertex-claim`, and retain the declared non-claims.

The validator rejects tampered payloads that try to carry paper-facing or collapsed-result fields such as `defuzzified_probability`, `p_hat`, `paper_facing_result`, `capacity_screen_result`, `vertex_shortcut_claim`, or `manuscript_number`. The per-rho synthetic probability estimate remains allowed inside each diagnostic point; it is not a p-box answer and cannot be presented as a paper-facing result before G3 and the downstream E4/E5 gates are resolved.

No real trajectories, real `P(E)`, real rho sweep, capacity convention, A-013/G2 value, G3 claim, decision-engine result, or manuscript number were produced.