# RISKS.md

| ID | Risk | Trigger | Response | Owner | Status |
|---|---|---|---|---|---|
| R-001 | Monotonicity fails broadly | G3 evidence | Use interior-sampling fallback; restrict claim to demand-driven regime; shrink N or grid if needed. | B | open |
| R-002 | Tiers disagree or Tier-1 enclosure is too wide | G2 held-out enclosure fails or `epsilon_Tier1` materially widens decisions | Fit and independently validate a simple correction, use predeclared selective AC on threshold-straddling states, or reject Tier-1; never omit a material approximation error. | A/B | open |
| R-003 | Decision-reversal treatments all agree | E8.S3 results | Re-pick a case nearer P_crit; benchmark without divergence is not the money figure. | C | open |
| R-004 | Runtime blowout | Runtime exceeds G1 budget by more than 2x | Use TimeSerie, fewer alpha levels if approved, smaller grid, or HPC fallback. | A/C | open |
| R-005 | Data license blocks redistribution | E2.S1 license check | Ship retrieval scripts and citations instead of data; document availability. | C | open |
| R-006 | Agent fabrication or drift | Unsigned number, uncited claim, or missing manifest | Reject PR; audit registers; enforce T4/T7. | all | open |
| R-007 | Elicitation attacked as arbitrary | Internal review or reviewer critique | Use DFMP protocol, shape sensitivity, and signed provenance. | B/C | open |
| R-008 | Scope creep | New idea mid-sprint | Park in `BACKLOG.md`; PI promotes only if needed. | all | open |
| R-009 | Author-specified `epsilon_grid` dominates the p-box or decision | E9.S5 sensitivity changes alpha-indexed decisions across approved envelope values | Report the dependence transparently, prioritize empirical validation as VoI, and do not present a single scenario value as measured fact. | B/C | open |
| R-010 | Capacity convention is selected post hoc to manufacture congestion | Total and firm results are not reported together, or the denominator changes after p-box inspection | Run E3.S2b once under a predeclared manifest; report raw MVA and both ratios; require PI sign-off and use G0 fallback/escalation for any later case adjustment. | A/HUMAN | open |
| R-011 | Grid-error envelope is extrapolated beyond its asserted operating domain | A stochastic sample exceeds the E3.S2b-frozen input or output span | Flag and escalate the sample; do not clip, silently extend the domain, or refit A-013 after result inspection. | A/B/C | open |
| R-012 | Early gate diagnostics used custom evidence JSON rather than IC-5 ExperimentRunner manifests | A legacy gate artifact is cited as final manuscript evidence or reused as a G2/G6 input without runner reproduction | Implement E0.S3b, rerun the legacy E1 diagnostics from versioned configs through ExperimentRunner, compare the reproduced outputs with the retained historical evidence, and use only the standard `manifest.json` artifacts for final claims. | C/A | open |
| R-013 | EV, HP, and PV 2035 inputs tell inconsistent scenario stories | Integrated input readiness or E3.S2b shows mismatched source years, labels, adoption branches, or growth assumptions across ElaadNL, PBL/CBS, CBS PV, and II3050 | Stop before real event analysis; produce a scenario-lineage/consistency memo; either align the branch with a signed amendment or carry the mismatch as an explicit limitation in manifests and methods. | all | open |
