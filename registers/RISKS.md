# RISKS.md

| ID | Risk | Trigger | Response | Owner | Status |
|---|---|---|---|---|---|
| R-001 | Monotonicity fails broadly | G3 evidence | Use interior-sampling fallback; restrict claim to demand-driven regime; shrink N or grid if needed. | B | open |
| R-002 | Tiers disagree | G2 transformer-loading delta exceeds PI tolerance | Make AC primary via lightsim2grid; demote summation to screening; reduce N if needed. | A | open |
| R-003 | Decision-reversal treatments all agree | E8.S3 results | Re-pick a case nearer P_crit; benchmark without divergence is not the money figure. | C | open |
| R-004 | Runtime blowout | Runtime exceeds G1 budget by more than 2x | Use TimeSerie, fewer alpha levels if approved, smaller grid, or HPC fallback. | A/C | open |
| R-005 | Data license blocks redistribution | E2.S1 license check | Ship retrieval scripts and citations instead of data; document availability. | C | open |
| R-006 | Agent fabrication or drift | Unsigned number, uncited claim, or missing manifest | Reject PR; audit registers; enforce T4/T7. | all | open |
| R-007 | Elicitation attacked as arbitrary | Internal review or reviewer critique | Use DFMP protocol, shape sensitivity, and signed provenance. | B/C | open |
| R-008 | Scope creep | New idea mid-sprint | Park in `BACKLOG.md`; PI promotes only if needed. | all | open |

