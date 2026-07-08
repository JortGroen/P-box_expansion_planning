# ASSUMPTIONS.md

Assumptions proposed by agents remain unsigned until the PI signs them.

| ID | Date | Statement | Rationale | Source/evidence | Owner | Status | PI sign-off |
|---|---|---|---|---|---|---|---|
| A-001 | 2026-07-08 | Candidate primary P_crit is 1e-2 with 1e-3 sensitivity. | Matches the project plan, but must be frozen at G0. | `project_plan_v3_when_can_grid_reinforcement_wait.md` section 8E | HUMAN | proposed | -- |
| A-002 | 2026-07-08 | Candidate alpha grid is {0, 0.25, 0.5, 0.75, 1.0}. | Matches the project plan and agent guardrails, but must be frozen at G0/G1. | `project_plan_v3_when_can_grid_reinforcement_wait.md` section 3 | HUMAN | proposed | -- |
| A-003 | 2026-07-08 | Primary grid candidates are SimBench MV semi-urban and urban, with CIGRE MV as cross-check. | Matches the resolved design plan; final selection belongs to G0. | `project_plan_v3_when_can_grid_reinforcement_wait.md` section 8A | HUMAN | proposed | -- |
| A-004 | 2026-07-08 | Report alpha-indexed lower/upper probability bounds and MC CIs; never defuzzify to one scalar. | Hard reporting rule in the project plan and agent instructions. | `project_plan_v3_when_can_grid_reinforcement_wait.md` section 3; `agent_instructions.md` section 1 | all | proposed | -- |

