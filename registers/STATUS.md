# STATUS.md

Format: `Story | Owner | status | tasks | blocked-by | PR`

| Story | Owner | Status | Tasks | Blocked-by | PR |
|---|---|---|---|---|---|
| E0.S1 Repo & environment | C | done | 4/4 | -- | -- |
| E0.S2 Control registers | C | done | 2/2 | -- | -- |
| E0.S3 Run-manifest utility | C | done | 2/2 | -- | -- |
| E0.S3b ExperimentRunner compliance retrofit | C/A | review | 4/4 | before G2/G6 | #31 |
| E0.S4 Agent working agreement | C | done | 1/1 | -- | -- |
| E1.S1 Grid loading | A | done | 3/3 | -- | #2 |
| E1.S2 Laptop micro-benchmark | A | done | 2/2 | -- | #7 |
| E1.S2b TimeSeriesCPP AC benchmark | A | done | 3/3 | -- | #23 |
| E1.S1b Transformer headroom diagnostic | A | done | 4/4 | -- | #19 |
| E1.S3b G0-A1 import-window diagnostic | A | done | 4/4 | -- | #15 |
| E1.S4 Tier-1 evaluator | A | review | 6/6 | -- | #25 |
| E2.S1 Data acquisition | C | done | 3/3 | -- | #14, #18 follow-up |
| E2.S2 EV model | C | in-progress | 4/5 | EV-004 Set A candidate M=1000, quarantined diagnostic Q=200, and fresh held-out H=200 archived locally; M sufficiency, held-out adequacy use, and within-realization replacement remain blocked by E2.S6 and EV-005/E3.S2a criteria | #35 |
| E2.S3 HP model | C | todo | 0/4 | E2.S1, ALEA-001 | -- |
| E2.S4 PV model | C | todo | 0/3 | E2.S1, G0, ALEA-001 | -- |
| E2.S5 Baseline & diversity | C | todo | 0/2 | E1.S3, ALEA-001 | -- |
| E2.S6 Adoption scenarios | C | todo | 0/3 | E2.S1, EV-004 | -- |
| E3.S1 Flexibility aggregator | A | review | scaffold/3 | E2 models for integration; Q-5 before event-based use | stacked on #42; #45 draft |
| E3.S2 IC-1 NetLoadProvider | A | todo | 0/4 | E3.S1, ALEA-001 | -- |
| E3.S2a Integrated library adequacy | C | todo | 0/5 | E2.S2-E2.S6, E3.S2, ALEA-002, EV-005; resolve Q-5 before opening event-based held-out results | -- |
| E3.S2b Future-layer capacity and domain screen | A | todo | 0/5 | E0.S3b, E2.S2-E2.S6, E3.S1-E3.S2a; Q-5 before threshold-based run | -- |
| E3.S3 Tier-2 AC harness and Tier-1 enclosure | A | todo | 0/5 | E0.S3b, E1.S1, E1.S2b, E1.S4, E3.S2b; Q-5 before threshold-stratum run | -- |
| E3.S4 CRN harness | A | review | 3/3 | ALEA-001; RNG-001 PI approval | #34 |
| E4.S1 Dense rho sweep | B | todo | 0/3 | E3.S2, E3.S4, resolved Q-5 | -- |
| E4.S2 Fallback stub | B | todo | 0/1 | E5 invariant skeleton | -- |
| E5.S1 Fuzzy number class | B | done | 2/2 | -- | #1 |
| E5.S2 Vertex propagation scaffold | B | done | 3/3 | G3 before scientific use | #6 |
| E5.S3 Output-domain model-error propagation | B | in-progress | 1/4 + Agent A contract in review | T2-T4: signed A-013, G2 envelope, resolved Q-5, and total-versus-firm capacity decision/provenance before paper use | #36; #13 closed; Agent A contract #42 |
| E5.S4 Independent cross-check | B | todo | 0/2 | E5.S1-E5.S3 | -- |
| E6.S1 alpha_star | B | review | 1/1 | E5.S2 | #33 |
| E6.S2 rho_star and membership | B | todo | 0/3 | E6.S1, G3 | -- |
| E6.S3 Deferral horizon | B | todo | 0/1 | E6.S1 | -- |
| E6.S4 VoI | B | todo | 0/2 | signed econ assumptions | -- |
| E6.S5 Decision engine | B | todo | 0/2 | E6.S1-E6.S4 | -- |
| E7.S1 DFMP transform | B | todo | 0/2 | -- | -- |
| E7.S2 Factor worksheet | B/C | todo | 0/3 | signed data rows | -- |
| E7.S3 GATE G4 | HUMAN | todo | 0/1 | E7.S2 | -- |
| E7.S4 Shape sensitivity | B | todo | 0/1 | G4, E6 | -- |
| E8.S1 Case sweep | C | todo | 0/2 | E5, E6 | -- |
| E8.S2 Treatments i-iv | C | todo | 0/4 | G5 candidate spec | -- |
| E8.S3 Run & figure | C | todo | 0/2 | G5, E8.S2 | -- |
| E8.S4 Narrative | C | todo | 0/1 | E8.S3 | -- |
| E9.S1 P_crit sensitivity | C | todo | 0/1 | E8 results | -- |
| E9.S2 CIGRE cross-check | C | todo | 0/1 | E8 pipeline | -- |
| E9.S3 Full-year screen | C | todo | 0/1 | E1.S3, E3.S3 | -- |
| E9.S4 Convergence | C | todo | 0/1 | E8 pipeline | -- |
| E9.S5 Grid-model error sensitivity | C | todo | 0/1 | signed A-013, E5.S3, E8 pipeline | -- |
| E9.S5a Grid-model error evidence review | C/HUMAN | todo | 0/3 | -- | -- |
| E10.S1 Figure factory | C | todo | 0/1 | manifests | -- |
| E10.S2 Manuscript | all | todo | 0/4 | G6 inputs | -- |
| E10.S3 Repro package | C | todo | 0/3 | figures/results | -- |
| E10.S4 Red team | all | todo | 0/1 | manuscript draft | -- |
| E10.S5 Gates G6/G7 | HUMAN | todo | 0/1 | E10.S1-E10.S4 | -- |
