# DECISIONS.md

Signed PI decisions live here. Agents may append proposed rows, but they never
write a PI sign-off. Every row must have a same-ID standalone paragraph block
in `paper/methods_decisions_and_assumptions.md`; pending gates use an explicit
placeholder until the PI records a decision.

| ID | Date | Gate/topic | Decision | Rationale | Evidence | Status | PI sign-off |
|---|---|---|---|---|---|---|---|
| G0 | 2026-07-09 | Scope freeze | Approved: see detailed G0 entry below. | Required before gated scope-specific work; freezes overload event, P_crit handling, grid/fallback choice, weather scope, and primary alpha grid. | E0 registers; E1.S1 grid inventory PR #2; G0 scope-freeze text approved by PI. | approved | PI approved in chat, 2026-07-09 |
| G0-A1 | 2026-07-10 | Event direction and fixed-window rejection amendment | Primary overload event is consumption-driven import congestion: apparent-power magnitude conditioned on net import direction. Direction-agnostic `abs(S)` remains the screening metric, and export-direction exceedance is reported beside primary results. Fixed winter windows are rejected; G0-A2 later assigns primary Tier-1 `P(E)` to the full planning year and retains WindowSets only for AC validation and diagnostics. | E1.S3 showed direction-agnostic annual maxima in SimBench scenarios 1/2 are summer midday export/PV peaks, while scenario 0 winter windows miss much of the annual near-peak shoulder. The study's flexibility construct is demand-reduction, so feed-in congestion needs a distinct absorption/curtailment instrument and remains out of scope. | E1.S3 PR #10; `reports/critical_weeks_validation.md`; PI amendment text in chat, 2026-07-10. | approved | PI approved in chat, 2026-07-10 |
| G0-A2 | 2026-07-10 | Full-year primary event scope | Primary Tier-1 `P(E)` is annual: the probability that the full planning year contains at least one qualifying import-direction overload episode. WindowSet is retained only for IC-1/IC-2 AC-validation subset selection and diagnostics. | E1.S3b adaptive import windows span 19-25 weeks, or 36-48% of the year, defeating their compute purpose for the negligible-cost Tier-1 summation evaluator. Full-year Tier-1 removes window-transfer risk. | E1.S3b import-window diagnostic PR #15; `reports/import_window_diagnostic.md`; `reports/G1_DECISION_BRIEF.md`; PI approved in chat, 2026-07-10. | approved | PI approved in chat, 2026-07-10 |
| G0-A3 | 2026-07-22 | Primary overload threshold | Resolve Q-5: the primary event is strict `L_import > 1.0 p.u.` for at least four consecutive 15-minute import steps over the full planning year. The same persistent event at `1.1 p.u.` and `1.2 p.u.` is retained as predeclared sensitivity analysis. No separate cumulative-exposure rule is added for the 1.0-1.1 p.u. band in the primary analysis; values above 1.0 are already counted by the primary event. The single-step E9 sensitivity remains separate and uses the declared threshold of its run. Export-side exceedance diagnostics report the matching threshold beside primary results. | Treats nameplate exceedance as the clearest planning-congestion definition without claiming transformer failure or relying on an insufficiently verified 110% Dutch DSO rule. IEC 60076-7 remains background for time-dependent thermal loading, not a source for selecting 1.1 as primary. | `reports/Q5_OVERLOAD_CRITERION_EVIDENCE_TABLE.md`; `reports/METHODOLOGY_OVERLOAD_CRITERION_REVIEW.md`; PI approval in chat, 2026-07-22. | approved | PI approved in chat, 2026-07-22 |
| G0-A4 | 2026-07-17 | Primary planning year | Freeze 2035 as the primary planning year for the complete probabilistic analysis and decision-reversal benchmark. E3.S2b still screens 2030, 2033, and 2035 deterministically; 2030 and 2033 remain supporting horizon/context and later sensitivity layers. G5 may select the adoption/scenario branch and grid within 2035, but may not select the year after inspecting results. If the predeclared 2035 screen is congestion-free or not flexibility-resolvable, stop and escalate for a signed amendment rather than silently switching years or tuning inputs. EV-004 remains unchanged: the fixed ElaadNL residential behavior library uses generator year 2030 and is reused in the 2035 planning layer. | Selects a forward case-study horizon prospectively, before integrated probabilistic results, while preserving earlier years for trajectory checks and the eventual deferral horizon. Separating planning year from profile-generator year prevents double counting ElaadNL internal forecast growth and the project's external adoption layer. | PI direction in chat, 2026-07-17; EV-004; E3.S2b/G1-A2 capacity-screen protocol. | approved | PI approved in chat, 2026-07-17 |
| G1 | 2026-07-10 | Foundation validated | Approved two-tier architecture: Tier-1 radial summation with G0-A1/G0-A2 semantics is the Monte Carlo inner-loop evaluator; AC power flow serves deterministic checks and validation subsets. Fixed winter windows are rejected, and primary Tier-1 runs the full planning year. No manuscript claim may say "AC infeasible". E1.S2 established that repeated high-level `runpp` is too slow for the MC loop; E1.S2b subsequently established a fast lower-level TimeSeriesCPP path for deterministic AC batches while deferring complete adapter numerical validation to G2. C1 TimeSeriesCPP benchmarking and C2 transformer-headroom diagnostics are complete; Agent A may proceed to E1.S4. | Tier-1 is computationally negligible for the decision-transformer criterion, but its accuracy remains a G2 hypothesis. E1.S3 rejected fixed winter windows; E1.S3b showed adaptive windows are too large to justify a primary windowed probability. E1.S2b makes substantial AC validation practical without supporting an "AC infeasible" or "full AC MC" claim. | E1.S2 benchmark; E1.S2b PR #23 and `reports/BENCHMARK_TIMESERIESCPP.md`; E1.S1b PR #19; E1.S3b import-window diagnostic PR #15; `reports/G1_DECISION_BRIEF.md`; PI amended G1 text in chat, 2026-07-10. | approved | PI approved in chat, 2026-07-10 |
| G1-A1 | 2026-07-13 | Black-box model error and Tier-1 approximation | Grid-model error is an unprobabilized interval on black-box model output, propagated before event detection under arbitrary unknown dependence. Tier-1 approximation error is estimated empirically at G2. Post-hoc probability-margin widening is rejected. G1-A2 supersedes the provisional error-composition and domain wording. | Preserves the intended imprecise-probability story, separates physical-system/model discrepancy from Tier-1-to-pandapower approximation, and retains the compute benefit of Tier-1 without hiding surrogate error. | `reports/G1_A1_MODEL_ERROR_AMENDMENT_PROPOSAL.md`; PI approval in chat, 2026-07-13. | approved | PI approved in chat, 2026-07-13 |
| G1-A2 | 2026-07-14 | Grid-error and capacity-screen protocol | Use a symmetric relative `epsilon_grid` envelope with arbitrary unknown dependence and compose it exactly with the additive G2 Tier-1 envelope before event detection. Reject the fixed 16-104 MVA applicability claim. Derive and freeze the asserted future operating domain from one predeclared manifested E3.S2b screen before probabilistic-result inspection. Keep total 80 MVA and firm 40 MVA capacity conventions open until that screen reports raw MVA and both ratios; selecting firm capacity requires actual one-transformer-out AC validation. | The 104 MVA value was only 1.3 times the current 80 MVA denominator, not a validated boundary. Relative grid error survives a later capacity-convention choice. A single governed future-layer screen can expose whether the total or firm convention yields no congestion, decision-sensitive congestion, or irrecoverable congestion without silently tuning the network after seeing p-box results. | `reports/G1_A2_GRID_ERROR_AND_CAPACITY_PROTOCOL.md`; E1.S1b headroom evidence; PI approval in chat, 2026-07-14. | approved | PI approved in chat, 2026-07-14 |
| E5-S3-T1 | 2026-07-20 | IC-2/IC-3 output-error schema | Approved with conditions: IC-2 must pass validated loading trajectories to IC-3 rather than only a boolean congestion result. Agent A must provide the shared `LoadingTrajectoryResult` contract and validator before Agent B implements IC-3 propagation. The validator must cover array shapes, finite values, direction masks, time-domain consistency, threshold, persistence length, and any supplied import/export diagnostics. IC-3 adds an `OutputErrorEnvelope` with `epsilon_grid`, `epsilon_tier1_minus`, and `epsilon_tier1_plus`; composes Tier-1 and grid-model output-error endpoints conservatively by G1-A2 before event detection; gates import/export using unwidened `P_net`; and computes probabilities/CIs from lower/upper event counts. Timestep cadence and transformer capacity/denominator provenance must be recorded in runner configuration and manifests. Q-5 is resolved separately by G0-A3. This approval does not resolve total-versus-firm capacity, G2 error values, or numerical A-013 grid-error values. | This is the smallest approved schema route that avoids boolean-only sample evaluation, keeps Tier-1 diagnostics backward compatible, supports symmetric/asymmetric/one-sided Tier-1 envelopes, preserves CRN identity, and prevents post-hoc probability widening. Tier-1 error and grid-model error are both parts of total model-output error; their dependence on inputs, time, and each other is unknown, so they must not be sampled independently or assumed to cancel. | `reports/E5_S3_OUTPUT_ERROR_SCHEMA_PROPOSAL.md`; Q-6 PI decision in chat, 2026-07-20. | approved with conditions | PI approved with conditions in chat, 2026-07-20 |
| RNG-001 | 2026-07-20 | Seed-tree and CRN identity protocol | Approved: derive each whole-system sample seed from `(root_seed, sample_index)`, derive each component-stream seed from the sample seed and component name, and identify component streams by root-derived stream identity including the component seed. Alpha, endpoint, and treatment labels do not alter aleatory identity; branch manifests record root/sample seeds, component streams, source-member selections, and shared physical driver IDs. | This prevents stream-ID collisions across roots, makes source selections non-transferable between seed trees, preserves common random numbers across epistemic/treatment branches, and keeps CRN reuse separate from physical shared-driver assumptions such as paired weather. | PR #34; `src/rng.py`; `tests/test_rng.py`; PI approval in chat, 2026-07-20. | approved | PI approved in chat, 2026-07-20 |
| FLEX-001 | 2026-07-22 | Flexibility aggregation scaffold protocol | Approved scaffold protocol: the E3.S1 scaffold applies controllability `rho` only to positive import-side demand components explicitly marked as controllable, preserves complete aligned 15-minute trajectories, leaves PV/export and non-controllable components unchanged, and records per-component reduction/rebound metadata. Optional adjacent-step rebound is an implementation scaffold for later signed flexibility behavior, not a scientific claim about delivered response. This approval does not sign flexibility-factor values, fuzzy corners, smart-charging control parameters, final rebound behavior, event analysis, `P(E)`, capacity screens, or manuscript numbers. | Provides a deterministic Agent A-owned layer that E2 component models and later IC-1/IC-2 integration can call without allowing demand-response logic to modify PV/export or threshold/event semantics. | PR #45; `src/flex_aggregator.py`; `tests/test_flex_aggregator.py`; PI approval in chat, 2026-07-22. | approved scaffold protocol | PI approved in chat, 2026-07-22 |
| ALEA-001 | 2026-07-15 | Joint aleatory dependency protocol | Preserve known dependence through one canonical calendar, complete source trajectories, and one paired multivariate weather member per Monte Carlo realization. HP and PV consume the same aligned weather member; EV and baseline retain complete temporal paths and common weekday/season alignment. Copulas, latent factors, or multivariate block bootstrap are escalation paths only if validation shows the primary conditional construction is inadequate. | Keeps physically understood temperature/irradiance, calendar, serial, and common-driver dependence without inventing an unsupported full joint distribution. It also separates physical dependence from CRN reuse and from the arbitrary-unknown-dependence treatment of model error. | `reports/JOINT_ALEATORY_SAMPLING_PROTOCOL.md`; PI approval in chat, 2026-07-15. | approved | PI approved in chat, 2026-07-15 |
| ALEA-002 | 2026-07-15 | Downstream-only congestion evaluation | Component-level profile statistics are data-quality diagnostics only. Congestion and profile-library adequacy are evaluated after baseline, EV, HP, PV, adoption, and flexibility have been aligned and aggregated into net load and passed through the transformer evaluator. An EV-only sustained-load statistic and the ElaadNL UI p95 curve are not congestion measures. A p95 downstream result may be used provisionally for workflow and convergence checks while the PI reviews published congestion definitions; this does not amend the G0 `P_crit` decision. | Prevents an arbitrary component proxy from determining a system-level reinforcement conclusion and tests finite-library adequacy against the quantity the study ultimately uses. | `reports/JOINT_ALEATORY_SAMPLING_PROTOCOL.md`; PI approval in chat, 2026-07-15. | approved | PI approved in chat, 2026-07-15 |
| WEATHER-001 | 2026-07-21 | Shared HP/PV weather-member contract | Approved Q-8 Option A: HP and PV must consume one neutral shared weather-member contract rather than separate HP-local and PV-local weather objects. Agent C is authorized through the ownership policy to implement the shared contract in `src/weather_model.py` with tests in `tests/test_weather_model.py`. The contract must preserve one common UTC/local calendar, member/source/provenance identity, temperature fields for HP, irradiance/PV-weather fields for PV, and a shared weather-driver identity so downstream manifests can prove both component models used the same physical weather realization. This approval does not sign D-004 files, completeness checks, numerical cold-spell tolerances, HP/PV acceptance results, net-load/event analysis, `P(E)`, capacity screens, or manuscript results. | Makes the ALEA-001 weather dependency structural rather than convention-based. A neutral shared contract avoids duplicating timestamp, timezone, member-ID, and provenance logic inside `hp_model.py` and `pv_model.py`, and it prevents late-stage pairing by manifest from hiding incompatible trajectories. | Q-8 PI approval in chat, 2026-07-21; ALEA-001; D-004; HP-001; `configs/agent_ownership.json`. | approved | PI approved Q-8 Option A in chat, 2026-07-21 |
| D004-MC-001 | 2026-07-22 | D-004 weather-member construction rule | Approved: construct D-004 WEATHER-001 members for `d004_alkmaar_berkhout_2014_2023_v1` as UTC calendar-year 15-minute members for 2014-2023, with Europe/Amsterdam local timestamps derived from the UTC axis. Interpret KNMI `HH` as UT hour-ending slots, with `HH=24` mapped to 00:00 UTC on the following date. Convert KNMI station 249 `T` to `temperature_c = T / 10` and repeat it over the four represented quarter-hour timestamps. Convert KNMI `Q` to hourly-average `ghi_w_per_m2 = Q * 10000 / 3600` and repeat it over the four quarter-hour sub-intervals so source hourly radiation energy is preserved. Use KNMI as the realized temperature/GHI path. Copy PVGIS-SARAH3 seriescalc/TMY URLs, checksums, and normalized PV configuration as calibration/validation provenance only; do not use PVGIS TMY as a realized sampled weather path. Use member IDs `d004_alkmaar_berkhout_<YEAR>_v1` and shared weather-driver IDs `d004_alkmaar_berkhout_2014_2023_v1:<YEAR>`. Deferred improvement: a later sensitivity may use energy-preserving within-hour irradiance interpolation, but the primary first-pass rule remains hourly KNMI `Q` repeated across four quarter-hours. This approval authorizes Agent C to implement the D-004 member builder; it does not sign final D-004 source acceptance, completeness tolerances, HP/PV paired acceptance, net-load/event analysis, `P(E)`, capacity screens, or manuscript results. | Freezes the construction rule before Agent C implements D-004 members. The first-pass repeated-`Q` rule preserves KNMI hourly radiation energy without adding unobserved within-hour solar-shape assumptions, keeps KNMI as the realized paired temperature/irradiance source under ALEA-001 and WEATHER-001, and prevents PVGIS typical-year data from becoming an independently sampled realized weather member. | `reports/e2_s4_d004_member_construction_rule_packet.md`; `data/metadata/weather_pv/d004_member_construction_rule_packet.json`; Q-9 clarification packet; PI approval in chat, 2026-07-22. | approved | PI approved in chat, 2026-07-22 |
| D004-SOURCE-MEMBER-ACCEPTANCE | 2026-07-22 | D-004 source/member acceptance for internal first-screen use | Approved: accept source bundle `d004_alkmaar_berkhout_2014_2023_v1` for internal first-screen source/member use. KNMI station 249 Berkhout remains the realized weather path for 2014-2023 WEATHER-001 members, using KNMI `T` and `Q` under `D004-MC-001`; PVGIS-SARAH3 seriescalc/TMY remains qualitative seasonal/peak sanity and provenance/calibration context only, not a realized sampled weather member. Paired HP/PV use requires exact WEATHER-001 identity and calendar equality before diagnostics are judged: member ID, shared weather-driver ID, source, UTC span, timestep count, cadence, and content SHA-256 must match. Numerical cold-spell tolerances are deferred to the HP/cold-spell acceptance decision. This approval does not run final paired HP/PV validation, sign cold-spell tolerances, authorize net-load/event analysis, `P(E)`, capacity screens, or manuscript results. | Records the PI-approved recommendation from the D-004 recommendation packet while preserving separation between source/member readiness, qualitative PVGIS sanity, paired-weather identity prerequisites, and deferred HP cold-spell tolerances. | `reports/e2_s4_d004_pi_recommendation_packet.md`; `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_pi_recommendation_packet.json`; PI approval in chat, 2026-07-22. | approved for internal first-screen source/member use; final paired/cold-spell acceptance pending | PI approved in chat, 2026-07-22 |
| PV-PARAM-001 | 2026-07-23 | PV conversion parameter signoff | Proposed: sign the primary first-pass PV conversion template `pv_param_001_first_pass_statistical_geometry_ghi_pr086_no_temp_clipped_v1` before executable PV use, after `installed_capacity_kw` is supplied by a separate signed capacity route such as PV-CAP-001. Per PV-ORIENT-001, the proposed first-experiment route uses a typical/statistical orientation-and-tilt distribution only, not per-building, per-roof, or location-specific geometry. The exact distribution source, bin weights, and conversion treatment remain unsigned. The template otherwise uses WEATHER-001 KNMI `Q`-derived `ghi_w_per_m2` as the realized irradiance basis, maps the approved PVGIS reference request loss setting of 14% to `performance_ratio = 0.86`, disables PV temperature correction with `temperature_coefficient_per_c = 0.0` and `reference_temperature_c = 25.0` until a module-specific coefficient is signed, and clips nonnegative output at the supplied installed capacity. Until signed, `PVSystemConfig` remains an unsigned/fail-closed scaffold for tests and review only. | Makes the first executable PV conversion-parameter proposal auditable without deciding installed-capacity source, numeric capacity, capacity convention, 2035 scaling, per-node allocation, or final orientation/tilt distribution values. D-004 source/member acceptance and PVGIS normalized requests do not provide installed capacity or a signed plane-of-array/module model, so executable PV must remain blocked until the PI signs PV-PARAM-001 or an amended parameter set and a separate signed capacity artifact supplies `installed_capacity_kw`. | `data/metadata/weather_pv/d004_pv_parameter_decision_packet.json`; `reports/e2_s4_pv_param001_decision_packet.md`; `reports/e2_s4_pv_readiness_wording_and_parameters.md`; PV-ORIENT-001. | proposed | pending PI review |
| D014-PV-PARAM-CONVERSION-SOURCE-CHOICE-PACKET | 2026-07-24 | D-014 PV-PARAM conversion source-choice packet | Proposed: use `data/metadata/weather_pv/d014_pv_param_conversion_source_choice_packet.json` as the PI-facing packet for choosing or amending the PV-PARAM conversion route before executable PV generation. The packet compares a pvlib-style statistical-orientation/tilt plane-of-array candidate, PVGIS qualitative calibration/sanity context, and the disputed direct-GHI scalar fallback. It keeps KNMI WEATHER-001 `ghi_w_per_m2` as the realized irradiance path, PVGIS as reference/provenance only, PV-CAP-001/D-014 capacity separate, and PV-ORIENT-001 statistical-only scope intact. | Responds to the PI concern that the simple `PR = 0.86`/direct-GHI route is not yet satisfactory, while still allowing review of a realistic first-experiment conversion path without approving a formula or values. This row does not sign direct-GHI, `PR = 0.86`, pvlib/plane-of-array/decomposition/albedo/temperature/clipping treatment, capacity convention, D-014 capacity/growth values, orientation/tilt values, allocation, PV output, net-load/event analysis, `P(E)`, capacity screens, or manuscript results. | `data/get_pv_capacity.py`; `data/metadata/weather_pv/d014_pv_param_conversion_source_choice_packet.json`; `reports/e2_s4_d014_pv_param_conversion_source_choice_packet.md`; D-014; PV-PARAM-001; PV-ORIENT-001; PV-CAP-001; WEATHER-001. | proposed packet; formula and values unsigned | pending PI review |
| D014-PV-FIRST-EXPERIMENT-APPROVAL-PACKET | 2026-07-24 | D-014 first-experiment PV approval packet | Proposed: use `data/metadata/weather_pv/d014_pv_first_experiment_approval_packet.json` as the PI-facing approval checklist before executable first-experiment PV generation. The packet consumes checksummed proposed inputs for the D-014 capacity approval template, orientation/tilt source and value choices, PV-PARAM conversion source choice, and executable preflight guard, then separates the remaining decisions into installed capacity, statistical orientation/tilt distribution, irradiance-to-power conversion, and node allocation layers. | Provides one fail-closed approval surface for the lightweight PV-ORIENT-001 first-experiment route without merging capacity, orientation, conversion, and allocation decisions. It does not approve any PV capacity value, II3050 growth factor, DC/AC convention, orientation/tilt bin/weight, PR value, pvlib/POA/direct-GHI formula, efficiency, node allocation, PV output, net-load/event analysis, `P(E)`, capacity screen, manuscript number, or final paired HP/PV acceptance. | `data/get_pv_capacity.py`; `data/metadata/weather_pv/d014_pv_first_experiment_approval_packet.json`; `reports/e2_s4_d014_pv_first_experiment_approval_packet.md`; D-014; PV-CAP-001; PV-ORIENT-001; PV-PARAM-001; A-016; WEATHER-001. | proposed packet; executable PV blocked | pending PI review |
| PV-CAP-001 | 2026-07-23 | PV installed-capacity source route | Approved route: derive executable PV installed capacity from a local Alkmaar CBS photovoltaic-capacity anchor and scale it to the frozen 2035 planning layer with a signed Netbeheer Nederland II3050/scenario growth factor. DEGO, CBS building/geography data, Zonnedakje, and the PI-supplied Kostas thesis may guide spatial allocation/source discovery only when their concrete data, license, and provenance are registered. This decision does not itself approve any numeric capacity value, CBS row/year/field, II3050 scenario value, DC/AC capacity convention, per-node allocation, PV-PARAM-001 conversion parameters, net-load/event analysis, `P(E)`, capacity screens, or manuscript results. | Separates the capacity question from the irradiance-to-power conversion. CBS gives an auditable local observed installed-capacity anchor; II3050 supplies the DSO-planning scenario growth context; optional rooftop/building sources improve allocation only if accessible and traceable. | PI decision in chat, 2026-07-23; CBS StatLine photovoltaic-capacity dataset to be registered as D-014; D-011 II3050 scenario framing; DEGO/Zonnedakje/Kostas thesis as optional source-discovery context only. | approved route; executable values pending | PI approved in chat, 2026-07-23 |
| D014-PV-CAPACITY-SOURCE-VALUE-PACKET | 2026-07-24 | D-014 PV capacity source/value packet | Proposed: use `data/metadata/weather_pv/d014_pv_capacity_source_value_packet.json` as the PI review packet before retrieving or binding PV installed-capacity values. The packet names CBS 85005NED as the primary Alkmaar `GM0361` PV-capacity anchor, records CBS OData schema probes and row-filter templates, identifies II3050 edition 2 appendices as the 2035 PV growth-factor source, and lists required approval keys for source checksum, geography, source period, capacity field, DC/AC convention, II3050 scenario/growth factor, node allocation, statistical orientation/tilt source and weights, and PV-PARAM conversion. Per PV-ORIENT-001, building-level roof geometry sources are deferred until after the first real experiment; the immediate next PV-geometry work is a lightweight statistical orientation/tilt distribution packet. | Converts the PV-CAP-001 route into a concrete fail-closed review artifact without approving numeric capacity, capacity convention, growth factor, allocation, PV-PARAM-001, statistical orientation/tilt values, net-load/event analysis, `P(E)`, capacity screens, or manuscript results. It also prevents D-014 from pulling the first-experiment path into a heavy per-roof PV-map workflow. | `data/get_pv_capacity.py`; `data/metadata/weather_pv/d014_pv_capacity_source_value_packet.json`; `reports/e2_s4_d014_pv_capacity_source_value_packet.md`; D-014; PV-CAP-001; PV-PARAM-001; PV-ORIENT-001. | proposed packet; values unsigned | pending PI review |
| D014-CBS-PV-CAPACITY-ANCHOR-EVIDENCE | 2026-07-24 | D-014 CBS Alkmaar PV capacity anchor evidence | Proposed: use `data/metadata/weather_pv/d014_cbs_85005ned_alkmaar_gm0361_anchor_evidence.json` as the retrieved source-evidence packet for the PV-CAP-001 local Alkmaar CBS anchor. The packet downloads the small CBS OData `85005NED` evidence bundle for Alkmaar `GM0361`, records exact query URLs, raw bundle SHA-256 and size, table metadata, schema/topic fields, periods, sector/category keys, all retrieved Alkmaar rows, and exact row candidates for future PI value choice. It does not select the executable period, sector/category, panel-vs-inverter field, unit/DC/AC convention, II3050 growth factor, node allocation, statistical orientation/tilt values, PV-PARAM conversion treatment, or final PV output. | Converts the D-014 CBS route from metadata-only planning to auditable source evidence while preserving fail-closed governance for every numeric or executable PV capacity choice. | `data/get_pv_capacity.py`; `data/metadata/weather_pv/d014_cbs_85005ned_alkmaar_gm0361_anchor_evidence.json`; ignored raw bundle `data/raw/pv_capacity/d014_cbs_85005ned_alkmaar_gm0361_anchor_evidence.json`; `reports/e2_s4_d014_cbs_capacity_anchor_evidence.md`; D-014; PV-CAP-001; PV-PARAM-001; PV-ORIENT-001. | proposed evidence; values unsigned | pending PI review |
| D014-II3050-PV-GROWTH-EVIDENCE | 2026-07-24 | D-014 II3050 PV growth evidence | Proposed: use `data/metadata/weather_pv/d014_ii3050_pv_growth_evidence.json` as the retrieved source-evidence packet for the PV-CAP-001 scenario-growth side. The packet downloads the public Netbeheer Nederland `Bijlagen II3050 eindrapport` PDF, records the exact publication/PDF URLs, raw PDF SHA-256 and size, citation/license route, Table A.1 `Zon PV*` row candidates, 2035 scenario-column candidates `KA`, `ND`, and `IA`, denominator/formula candidates, and exact PI approval keys. It does not select an executable II3050 scenario column, denominator, growth-factor formula/value, CBS anchor row/value, DC/AC convention, allocation, PV-PARAM conversion treatment, statistical orientation/tilt values, or final PV output. | Completes the second concrete evidence side of the PV-CAP-001 route while keeping all scenario and numeric capacity choices fail-closed for PI review. | `data/get_pv_capacity.py`; `data/metadata/weather_pv/d014_ii3050_pv_growth_evidence.json`; ignored raw PDF `data/raw/pv_capacity/d014_ii3050_bijlagen_eindrapport_285.pdf`; `reports/e2_s4_d014_ii3050_growth_evidence.md`; D-014; PV-CAP-001; PV-PARAM-001; PV-ORIENT-001. | proposed evidence; values unsigned | pending PI review |
| D014-PV-CAPACITY-VALUE-CHOICE-PACKET | 2026-07-24 | D-014 PV capacity value-choice packet | Proposed: use `data/metadata/weather_pv/d014_pv_capacity_value_choice_packet.json` as the PI-facing recommendation packet that combines the retrieved CBS Alkmaar anchor evidence and II3050 PV growth evidence. The packet lists exact symbolic equations for local 2035 installed PV capacity, candidate CBS period/sector/field operands, II3050 2035 scenario and denominator operands, A-016 scenario-consistency blockers, DC-vs-AC capacity-convention choices, and approval keys. It recommends, for PI review only, a source-year-consistent DC panel-capacity route before PV-PARAM-001 maps capacity into executable PV conversion. It does not approve or compute a final PV capacity value, growth factor, scenario column, CBS row, capacity convention, allocation, orientation/tilt values, PV-PARAM conversion, PV output, net-load/event analysis, `P(E)`, capacity screens, or manuscript results. | Converts the two retrieved D-014 evidence packets into a concise PI decision layer while preserving fail-closed governance for all executable PV choices. | `data/get_pv_capacity.py`; `data/metadata/weather_pv/d014_pv_capacity_value_choice_packet.json`; `reports/e2_s4_d014_pv_capacity_value_choice_packet.md`; D-014; PV-CAP-001; A-016; PV-PARAM-001; PV-ORIENT-001. | proposed packet; values unsigned | pending PI review |
| D014-PV-CAPACITY-APPROVAL-TEMPLATE | 2026-07-24 | D-014 PV capacity approval-template packet | Proposed: use `data/metadata/weather_pv/d014_pv_capacity_approval_template.json` as the fail-closed template for the future PI-signed executable PV capacity artifact. The packet derives from the D014-PV-CAPACITY-VALUE-CHOICE-PACKET metadata checksum and enumerates the required signed fields for artifact identity, installed-capacity value and convention, CBS Alkmaar anchor operand, II3050 growth operand, A-016 scenario consistency, node allocation, statistical orientation/tilt dependency, PV-PARAM conversion dependency, and audit outputs. It does not approve any capacity value, CBS row, II3050 scenario/growth factor, DC/AC convention, allocation, orientation/tilt value, PV-PARAM conversion, PV output, net-load/event analysis, `P(E)`, capacity screens, or manuscript results. | Makes the post-PI capacity artifact contract explicit before any value is signed, so downstream executable-input gates can reject unsigned D-014 capacity templates rather than silently using proposed recommendations. | `data/get_pv_capacity.py`; `data/metadata/weather_pv/d014_pv_capacity_approval_template.json`; `reports/e2_s4_d014_pv_capacity_approval_template.md`; D-014; PV-CAP-001; A-016; PV-PARAM-001; PV-ORIENT-001. | proposed template; values unsigned | pending PI review |
| D014-PV-EXECUTABLE-READINESS-BLOCKERS | 2026-07-24 | D-014 PV executable readiness blockers | Proposed: use `data/metadata/weather_pv/d014_pv_executable_readiness_blockers.json` as a fail-closed manifest that combines the accepted D-004 WEATHER-001 source/member artifact with unsigned D-014 capacity, PV-ORIENT-001, PV-PARAM-001, A-016 scenario-consistency, node-allocation, and final paired/cold-spell blockers before executable first-experiment PV generation. It records that weather source/member input is available but executable PV generation is not authorized. | Gives Agent A and later integration gates a single auditable blocker list without approving capacity values, orientation/tilt weights, conversion parameters, allocation, paired HP/PV acceptance, cold-spell tolerances, net-load/event analysis, `P(E)`, capacity screens, or manuscript results. | `data/get_pv_capacity.py`; `data/metadata/weather_pv/d014_pv_executable_readiness_blockers.json`; `reports/e2_s4_d014_pv_executable_readiness_blockers.md`; D-004; D-014; PV-CAP-001; A-016; PV-ORIENT-001; PV-PARAM-001. | proposed blocker manifest; executable PV blocked | pending PI review |
| D014-PV-EXECUTABLE-PREFLIGHT-GUARD | 2026-07-24 | D-014 PV executable preflight guard | Proposed: use `data/metadata/weather_pv/d014_pv_executable_preflight_guard.json` as the metadata-only preflight result for any attempted executable PV generation before signed D-014/PV-PARAM/PV-ORIENT/A-016/allocation/paired-weather gates exist. The preflight consumes the D014-PV-EXECUTABLE-READINESS-BLOCKERS manifest, records its checksum, preserves the current blocker IDs, and specifies that invocation must abort with the blocker manifest rather than produce PV output. | Automates the fail-closed integration boundary required by the updated agent policy: future wiring can call a deterministic preflight and receive a blocker manifest, not a provisional PV number from unsigned inputs. | `data/get_pv_capacity.py`; `data/metadata/weather_pv/d014_pv_executable_preflight_guard.json`; `reports/e2_s4_d014_pv_executable_preflight_guard.md`; D-014; D014-PV-EXECUTABLE-READINESS-BLOCKERS; PV-CAP-001; A-016; PV-ORIENT-001; PV-PARAM-001. | proposed preflight guard; executable PV blocked | pending PI review |
| D014-PV-STATISTICAL-ORIENTATION-TILT-PACKET | 2026-07-24 | D-014 statistical PV orientation/tilt packet | Proposed: retire the heavy building-level PV-map/3DBAG roof-extraction workflow from the first real experiment and use only a lightweight statistical orientation/tilt class route if the PI later signs a source, class bins, class weights, weighting convention, D-014 capacity artifact, node allocation rule, and PV conversion model. The packet keeps PV-CAP-001 separate: installed capacity still comes from the CBS Alkmaar anchor scaled to 2035 with a signed II3050/scenario growth factor. It keeps PV-PARAM-001 proposed/fail-closed and does not approve `PR = 0.86`, direct-GHI conversion, class weights, capacity convention, per-node allocation, or final PV output. | Matches the PI direction that per-roof PV-map methodology is too intensive before the first real experiment while preserving a realistic path to orientation/tilt heterogeneity through auditable statistical classes. | `data/get_pv_capacity.py`; `data/metadata/weather_pv/d014_pv_statistical_orientation_tilt_packet.json`; `reports/e2_s4_d014_pv_statistical_orientation_tilt_packet.md`; D-014; PV-CAP-001; PV-PARAM-001; PV-ORIENT-001. | proposed packet; values unsigned | pending PI review |
| PV-ORIENT-001 | 2026-07-24 | First-experiment PV orientation/tilt scope | Approved scope: for the first real experiment, keep the lightweight PV-PARAM-001 first-pass route and represent panel orientation and tilt only through a typical/statistical distribution. Do not implement per-building, per-roof, or location-specific orientation/tilt extraction, allocation, or 3DBAG/PV-map geometry before the first real experiment. The full roof-level pvlib/PV-map workflow is a post-first-experiment improvement path. Exact distribution source, bin definitions, weights, and whether/how the distribution changes the PV conversion formula remain separate PI-gated inputs before executable PV generation. | Avoids a large roof-geometry workstream before the first go/no-go experiment while improving on a single fixed south/35-degree reference. The first experiment needs transparent PV diversity, not a building-specific PV cadastre. | PI decision in chat, 2026-07-24; external `PV-map/modelling_workflow.md` treated as future-work research context only; PV-PARAM-001; PV-CAP-001/D-014. | approved scope; values/formula pending | PI approved in chat, 2026-07-24 |
| D014-PV-ORIENTATION-TILT-SOURCE-CHOICE-PACKET | 2026-07-24 | D-014 PV orientation/tilt source-choice packet | Proposed: use `data/metadata/weather_pv/d014_pv_orientation_tilt_source_choice_packet.json` as the PI review packet for choosing the source of the first-experiment statistical orientation/tilt distribution. Candidate source order is Killinger et al. 2018 PV-system-characteristics distributions as the primary empirical candidate if the needed values are accessible/citable, a Utrecht rooftop-PV observed-systems study as Dutch plausibility context, Ramadhani et al. 2023 as an open method template if a transfer assumption is accepted, and a PI-declared simple prior only as an explicit assumption fallback. PVGIS and pvlib remain sanity/implementation candidates, not weight sources; JRC/DBSM, 3DBAG, and other building-level routes are deferred until after the first real experiment. This packet does not select a final source, class bins, class weights, capacity-weighting convention, conversion treatment, capacity value, node allocation, `PR = 0.86`, net-load/event analysis, `P(E)`, capacity screens, or manuscript results. | Turns PV-ORIENT-001 from a scope decision into a concrete fail-closed source-choice review packet while preserving the first-experiment constraint against heavy PV-map or per-roof geometry. | `data/get_pv_capacity.py`; `data/metadata/weather_pv/d014_pv_orientation_tilt_source_choice_packet.json`; `reports/e2_s4_d014_pv_orientation_tilt_source_choice_packet.md`; D-014; PV-ORIENT-001; PV-PARAM-001; PV-CAP-001. | proposed packet; source/values unsigned | pending PI review |
| D014-PV-ORIENTATION-TILT-VALUE-CHOICE-PACKET | 2026-07-24 | D-014 PV orientation/tilt value-choice packet | Proposed: use `data/metadata/weather_pv/d014_pv_orientation_tilt_value_choice_packet.json` as the PI review packet for first-experiment statistical orientation/tilt class values. The packet keeps Killinger et al. 2018 as the preferred empirical extraction route if the Netherlands-relevant distribution parameters can be accessed and cited, and offers `pi_prior_5_class_symmetric_rooftop_candidate_v1` only as an unsigned assumption fallback with candidate bins, representative angles, and capacity-weight fractions. The packet keeps PV-CAP-001/D-014 installed capacity separate and keeps PV-PARAM-001 fail-closed until conversion treatment, PR/losses, capacity convention, orientation/tilt values, allocation, and growth factor are signed. | Turns the PV-ORIENT-001 source-choice packet into a concrete value-choice review artifact while preserving the PI-approved lightweight first-experiment scope and avoiding building-level PV-map/3DBAG work. | `data/get_pv_capacity.py`; `data/metadata/weather_pv/d014_pv_orientation_tilt_value_choice_packet.json`; `reports/e2_s4_d014_pv_orientation_tilt_value_choice_packet.md`; D-014; PV-ORIENT-001; PV-PARAM-001; PV-CAP-001. | proposed packet; values unsigned | pending PI review |
| E2-S3-COLD-SPELL-ACCEPTANCE-DESIGN | 2026-07-21 | HP cold-spell and paired-weather acceptance design | Approved predeclared design: before final integrated HP/PV source acceptance, an acceptance report must verify that When2Heat-derived HP profiles and PV profiles preserve the same WEATHER-001 realization, canonical UTC/local calendar, source/provenance, and paired temperature/irradiance fields, then report coldest-window, near-freezing/defrost-risk, and temperature-response diagnostics. Numerical pass/fail tolerances, including the exact near-freezing band around 0 degrees C, remain unsigned and must be approved before the first real acceptance run. | Keeps the approved HP-001 source/technology boundary and WEATHER-001 contract separate from final paired-weather acceptance and prevents HP/PV weather consistency from being judged after integrated congestion results are inspected. The near-freezing diagnostic prevents the acceptance design from assuming that the coldest absolute temperature is always the hardest ASHP operating condition. This row does not set tolerances, run the check, approve D-004, approve local annual HP scaling, or authorize net-load, event, `P(E)`, capacity-screen, manuscript, or probability results. | `reports/e2_s3_cold_spell_acceptance_design.md`; HP-001 approved source/technology boundary; WEATHER-001 approved shared contract; PI near-freezing caveat in chat, 2026-07-21; D-004 remains proposed. | approved design; tolerances pending | PI approved design with near-freezing caveat in chat, 2026-07-21 |
| E2-S3-HP-TECH-SCALING-DECISION-PACKET | 2026-07-21 | HP technology and annual scaling decision packet | Proposed: the PI review packet frames the remaining E2.S3 choices before real heat-pump integration: Dutch When2Heat shape columns, COP/technology columns, SFH/MFH/COM class handling, and whether annual thermal scaling comes from When2Heat `heat_demand_*` evidence or from another registered source. HP-001 now approves the first-pass residential source/technology boundary for space heat plus domestic hot water while keeping commercial heat, annual local scaling, and paired-weather acceptance open. | Collects previously separate HP source-use, annual-scaling, and cold-spell blockers into one PI-facing decision map so D-003 source use is not silently conflated with annual volume, local downscaling, paired-weather acceptance, or final integrated input acceptance. This row does not approve D-004, set numerical tolerances, run paired-weather acceptance, authorize net-load/event/`P(E)`/capacity/manuscript/probability results, or approve any local annual HP scaling value. | `reports/e2_s3_hp_technology_scaling_decision_packet.md`; D-003 source/technology use approved by HP-001; D-004 remains proposed; HP annual local scaling remains pending. | proposed packet; HP-001 boundary approved | -- |
| E2-S3-HP-LOCAL-SCALING-ROUTE-PACKET | 2026-07-21 | HP-001 local annual scaling/adoption route packet | Proposed: derive executable HP-001 annual thermal TWh inputs through a signed local bottom-up route that keeps SFH/MFH and space/DHW components separate: select a PI-approved local service-area proxy, obtain source-backed local residential stock or heat-demand denominators, apply a signed 2035 HP adoption/electrification scenario, and pass the resulting four component annual TWh values explicitly into `hp001_residential_when2heat_components`. When2Heat national `heat_demand_*` columns remain diagnostic anchors, not the default local scaling source. | This separates the already-approved D-003 residential shape/COP boundary from the still-unsigned local annual heat volume. It avoids importing national historical When2Heat totals directly into the SimBench case, makes the local geography and adoption denominator auditable, and preserves HP-001's component traceability before aggregation. This row proposes formulas, source classes, and sensitivity options only; it does not sign any source, annual TWh value, adoption count, D-004 acceptance, cold-spell tolerance, net-load/event/`P(E)`/capacity-screen result, Q-5-dependent threshold analysis, or manuscript number. | `reports/e2_s3_hp_local_scaling_route_packet.md`; HP-001; D-003; WEATHER-001; `reports/e2_s3_hp_scaling_evidence_packet.md`; `reports/e2_s3_hp_model.md`. | proposed packet; values unsigned | -- |
| E2-S3-HP-SOURCE-PROXY-CLARIFICATION | 2026-07-22 | HP-001 local scaling source/proxy clarification packet | Proposed: before retrieving HP scaling values, ask the PI to choose the exact local proxy, source bundle, and adoption boundary for the HP-001 annual scaling route. Agent C recommends using Alkmaar municipality `GM0361` as the HP service-area proxy for consistency with EV-007A and D-004, pairing CBS StatLine dwelling-stock-by-type evidence with PBL Startanalyse 2025 Alkmaar heat-transition/heat-demand evidence as the first retrieval bundle, and treating national/current heat-pump statistics only as context unless a separate 2035 adoption source is signed. | The merged local-scaling route still leaves too many choices open for a value-retrieval PR: geography, SFH/MFH crosswalk, whether Startanalyse outputs represent heat demand, technical pathway, or adoption, and how HP-001 DHW is served. This clarification packet narrows those questions without turning any annual TWh or adoption count into executable input. It does not approve a source, value, adoption branch, D-004 acceptance, cold-spell tolerance, net-load/event/`P(E)`/capacity-screen result, Q-5-dependent threshold analysis, or manuscript number. | `reports/e2_s3_hp_local_scaling_source_proxy_clarification.md`; `reports/e2_s3_hp_local_scaling_route_packet.md`; HP-001; EV-007A; D-003; D-004; WEATHER-001. | proposed packet; route not yet approved | -- |
| E2-S3-HP-SOURCE-USE-DECISION-PACKET | 2026-07-22 | HP-001 D-013 source-use decision packet | Proposed: classify the retrieved D-013 CBS/PBL bundle for HP-001 annual-scaling use before any annual TWh values are calculated. CBS 85035NED is proposed as the Alkmaar `GM0361` SFH/MFH dwelling-stock denominator and crosswalk source; PBL Startanalyse 2025 Alkmaar is proposed as pathway/suitability and building-stock context unless the PI later signs exact heat-demand columns, units, and formulas; CBS 85523NED remains national/current heat-pump context only. Executable HP loads require signed annual-scaling provenance for every SFH/MFH and space/water component. | Keeps the approved D-013 retrieval/checksum evidence from becoming unsigned local heat demand or adoption by implication, while allowing guarded HP component-readiness code to preserve component traces and reject executable integrated loads without signed annual values. This row does not sign annual HP TWh values, 2035 adoption, D-004 acceptance, cold-spell tolerances, net-load/event/`P(E)`/capacity-screen analysis, threshold runs, manuscript numbers, or probability results. | `reports/e2_s3_hp_source_use_decision_packet.md`; `data/metadata/hp_scaling/hp001_alkmaar_gm0361_source_use_decision_packet.json`; D-013; HP-001; D-003; WEATHER-001. | proposed packet; values unsigned | -- |
| E2-S3-HP-SCALING-RETRIEVAL-ROUTE | 2026-07-22 | HP-001 Alkmaar public-source retrieval/checksum route | Approved: bind the HP-001 local scaling route to a public-source-only retrieval, checksum, and schema-inspection workflow for Alkmaar municipality `GM0361`. The route records CBS StatLine 85035NED as the SFH/MFH dwelling-stock denominator source, PBL Startanalyse aardgasvrije buurten 2025 Alkmaar as the local heat-demand/pathway/suitability evidence source after schema inspection, and CBS StatLine 85523NED as national/current heat-pump context only. Future retrievals must write raw public files under ignored `data/raw/hp_scaling/`, persist source-by-source checkpoints and SHA-256 metadata under `data/metadata/hp_scaling/`, and keep local heat demand, suitability/pathway evidence, and unsigned 2035 HP adoption separate before any value proposal. This approval authorizes retrieval/checksum/schema inspection for D-013; it does not calculate or approve annual TWh values, sign 2035 HP adoption, sign D-004, run paired-weather acceptance, run net-load/event/`P(E)`/threshold/capacity-screen analysis, or produce manuscript numbers. | This step converts the previous source/proxy clarification into an auditable execution route without using confidential thesis values or silently authorizing annual TWh inputs. It preserves SFH/MFH and space/DHW traceability for the four HP-001 components and keeps Startanalyse suitability/pathway evidence from becoming adoption evidence by implication. Public-source binding is approved now so raw evidence can be retrieved and inspected before any numerical HP scaling values are proposed. | `reports/e2_s3_hp_scaling_retrieval_route.md`; `data/get_hp_scaling.py`; D-013; HP-001; D-003; D-004; WEATHER-001; `reports/e2_s3_hp_local_scaling_source_proxy_clarification.md`; PI approval in chat, 2026-07-22. | approved retrieval/checksum route; values unsigned | PI approved in chat, 2026-07-22 |
| E2-S3-HP-SCALING-SCHEMA-INSPECTION | 2026-07-22 | D-013 PBL/CBS schema inspection evidence | Proposed: refresh D-013 schema metadata from already retrieved ignored CBS/PBL raw files without network access or value extraction. The PBL Startanalyse Alkmaar inspection records full small-file CSV row counts, column classifications, and `Code_Indicator`/`Eenheid` pairs, including heat-demand-like H-series indicators with unit `[GJ/weq/jaar]`, while preserving the boundary that exact source-use columns, conversions, space/DHW interpretation, and 2035 HP adoption remain PI decisions. | Deepens the evidence needed to decide whether PBL can support local HP heat-demand scaling or only pathway/suitability context, without turning schema candidates into executable annual TWh inputs. This row does not sign annual values, adoption, D-004 acceptance, cold-spell tolerances, net-load/event/`P(E)`/capacity-screen analysis, threshold runs, manuscript numbers, or probability results. | `reports/e2_s3_hp_scaling_schema_inspection.md`; `data/get_hp_scaling.py`; `data/metadata/hp_scaling/hp001_alkmaar_gm0361_schema_inspection_packet.json`; D-013; HP-001. | proposed evidence; values unsigned | -- |
| E2-S3-HP-LOCAL-SCALING-SOURCE-USE-PROPOSAL | 2026-07-22 | HP-001 D-013 local scaling source-use proposal | Proposed source-use route, partly resolved by D013-PBL-MAPPING: use the D-013 schema inspection to select PBL Startanalyse 2025 Alkmaar residential heat-demand indicators and CBS Alkmaar SFH/MFH denominator evidence for later HP-001 annual thermal scaling. The proposal identifies `H23_Vraag_RV_w` and `H24_Vraag_TW_w` in `Alkmaar_strategie.csv`, unit `[GJ/weq/jaar]`, with `Referentie_2030` as the candidate heat-demand value column; proposes PBL `I11_woningequivalenten [Woning]` as the intensity denominator; and proposes CBS 85035NED `2026JJ00` `Eengezinswoningen totaal`/`Meergezinswoningen totaal` as the SFH/MFH crosswalk. It records unsigned illustrative component values before any 2035 HP adoption multiplier. | This turns the D-013 schema evidence into a reviewable source-use route without making values executable. D013-PBL-MAPPING approves only the PBL suffix/indicator mapping as a transparent assumption; unit conversions, class split rules, annual TWh values, adoption/service fractions, D-004 acceptance, cold-spell tolerances, net-load/event/`P(E)`/threshold/capacity-screen analysis, manuscript numbers, and probability results remain unsigned. | `reports/e2_s3_hp_local_scaling_source_use_proposal.md`; `data/metadata/hp_scaling/hp001_alkmaar_gm0361_local_scaling_source_use_proposal.json`; D-013; HP-001; `reports/e2_s3_hp_scaling_schema_inspection.md`; D013-PBL-MAPPING. | partly resolved by D013-PBL-MAPPING; values unsigned | -- |
| E2-S3-HP001-SCALING-FORMULA-CONFIG | 2026-07-23 | HP-001 local scaling formula/config guard packet | Proposed: prepare a fail-closed formula/config route for HP-001 local annual scaling after A-015/D013-PBL-MAPPING. The packet recommends `Referentie_2030` as the PBL value column, `I11_woningequivalenten [Woning]` as the denominator, division by `3,600,000` for GJ/year to TWh/year, CBS 85035NED count-share allocation for SFH/MFH, and a separate signed 2035 HP service/adoption/electrification scenario. The code scaffold records these choices but refuses executable HP components until all remaining approval IDs are present. | Keeps the newly approved indicator mapping from silently authorizing annual values. The route separates local useful-thermal demand from 2035 HP-served demand and preserves HP-001 SFH/MFH plus space/DHW traceability before aggregation. This row does not approve annual TWh values, value-column use, denominator use, unit conversion, split rule, adoption/electrification, D-004/cold-spell acceptance, net-load/event/`P(E)`/capacity-screen analysis, threshold runs, manuscript numbers, or probability results. | `reports/e2_s3_hp001_scaling_formula_config_decision_packet.md`; `src/hp_model.py`; `data/get_hp_scaling.py`; D-013; A-015; HP-001. | proposed packet; executable annual values unsigned | -- |
| E2-S3-HP001-VALUE-BINDING-READINESS | 2026-07-23 | HP-001 value-binding readiness packet | Proposed: prepare a machine-readable value-binding draft and guarded adapter for the remaining HP-001 local scaling choices after A-015/D013-PBL-MAPPING and the formula/config guard. The packet carries the candidate `Referentie_2030`, `I11_woningequivalenten [Woning]`, GJ-to-TWh conversion, CBS 85035NED count-share split, and unsigned component value drafts before any 2035 HP adoption/electrification multiplier. The HP adapter refuses to create `HP001LocalScalingConfig` unless the packet is explicitly marked `approved_for_executable_value_binding` and all five required approval IDs are present. | Makes the next value-binding PR auditable without letting unsigned review diagnostics become executable HP load inputs. It preserves SFH/MFH plus space/DHW traceability and keeps local useful-thermal demand separate from 2035 HP-served demand. This row does not approve annual TWh values, value-column use, denominator use, unit conversion, split rule, adoption/electrification, D-004/cold-spell acceptance, net-load/event/`P(E)`/capacity-screen analysis, threshold runs, manuscript numbers, or probability results. | `reports/e2_s3_hp001_value_binding_readiness_packet.md`; `data/get_hp_scaling.py`; `src/hp_model.py`; D-013; A-015; HP-001; E2-S3-HP001-SCALING-FORMULA-CONFIG. | proposed packet; executable annual values unsigned | -- |
| E2-S3-HP001-READINESS-APPROVAL-CHECKLIST | 2026-07-23 | HP-001 final-readiness approval checklist | Proposed: use one explicit PI checklist for the remaining HP-001 blockers before integrated HP use. Annual value binding still requires signed approval for `value_column`, `denominator`, `unit_conversion`, `sfh_mfh_split`, and `adoption_electrification`; final HP/PV weather use still requires signed `d004_paired_weather_acceptance` evidence and `cold_spell_tolerances`. The code scaffold records these keys and fails closed until all required approval IDs are present. | Keeps the approved HP-001 shape/COP boundary and A-015/D013-PBL-MAPPING indicator mapping from being mistaken for executable annual values or final paired-weather acceptance. The checklist makes the next PI approval narrow, auditable, and separate from downstream analysis gates. This row does not approve annual TWh values, 2035 adoption/electrification, D-004 paired-weather acceptance, cold-spell tolerances, net-load/event/`P(E)`/capacity-screen analysis, threshold runs, manuscript numbers, or probability results. | `reports/e2_s3_hp001_readiness_approval_checklist.md`; `data/metadata/hp_scaling/hp001_alkmaar_gm0361_readiness_approval_checklist.json`; `src/hp_model.py`; `data/get_hp_scaling.py`; HP-001; D-003; D-004; D-013; WEATHER-001; D013-PBL-MAPPING. | proposed checklist; executable annual values and final paired acceptance unsigned | -- |
| E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET | 2026-07-23 | HP-001 executable value-binding decision packet | Proposed: ask the PI to approve or amend the exact choices that would later let HP-001 annual value binding become executable: PBL `Referentie_2030` value-column use, PBL `I11_woningequivalenten [Woning]` denominator use, GJ/year-to-TWh/year conversion by division by `3,600,000`, CBS 85035NED count-share SFH/MFH allocation, and a 2035 HP service/adoption/electrification scenario. The packet also keeps final HP use blocked on separate `d004_paired_weather_acceptance` evidence and `cold_spell_tolerances`. | Converts the existing source evidence and fail-closed readiness checklist into a concise approval template without treating unsigned candidate values as executable inputs. The generated candidate record deliberately has blank approval IDs and a non-approved status, so the existing HP adapter rejects it until a later signed record is committed. This row does not approve annual TWh values, 2035 adoption/electrification, D-004 paired-weather acceptance, cold-spell tolerances, net-load/event/`P(E)`/capacity-screen analysis, threshold runs, manuscript numbers, or probability results. | `reports/e2_s3_hp001_executable_value_binding_decision_packet.md`; `data/metadata/hp_scaling/hp001_alkmaar_gm0361_executable_value_binding_decision_packet.json`; `data/get_hp_scaling.py`; `tests/test_data_sources.py`; `tests/test_hp_model.py`; HP-001; D-003; D-004; D-013; WEATHER-001; D013-PBL-MAPPING; E2-S3-HP001-READINESS-APPROVAL-CHECKLIST. | proposed packet; executable annual values and final paired acceptance unsigned | -- |
| E2-S3-HP001-EXECUTABLE-VALUE-BINDING-BRIEF | 2026-07-23 | HP-001 executable value-binding decision brief | Proposed: translate the merged executable value-binding packet into a PI-facing approval brief with concrete choices for PBL `Referentie_2030`, PBL `I11_woningequivalenten [Woning]`, GJ/year-to-TWh/year conversion by division by `3,600,000`, CBS 85035NED count-share versus area-weighted SFH/MFH split, and 2035 HP service/adoption/electrification options. Candidate adoption options are explicit unsigned PI scenarios (`0.50` first-pass or `0.25`/`0.50`/`0.75` low/mid/high), a PBL pathway sensitivity using `A08_Aandeel_eWP_GJ` with `A07_Aandeel_eWP_WEQ`/`A02_Aansl_eWP` diagnostics, or a future external public adoption source. | Makes the remaining HP approval request easier for the PI to sign or amend while preserving fail-closed boundaries. The scenario fractions are proposed approval options only, not source-estimated adoption, not probabilities, and not executable annual HP TWh. D-004 paired-weather acceptance and cold-spell numerical tolerances remain separate blockers. This row does not approve annual TWh values, 2035 adoption/electrification, D-004 paired-weather acceptance, cold-spell tolerances, net-load/event/`P(E)`/capacity-screen analysis, threshold runs, manuscript numbers, or probability results. | `reports/e2_s3_hp001_executable_value_binding_decision_brief.md`; `reports/e2_s3_hp001_executable_value_binding_decision_packet.md`; `data/metadata/hp_scaling/hp001_alkmaar_gm0361_executable_value_binding_decision_packet.json`; D-003; D-004; D-013; WEATHER-001; D013-PBL-MAPPING; HP-001. | proposed brief; executable annual values and final paired acceptance unsigned | -- |
| E2-S3-HP001-COMPONENT-OUTPUT-READINESS-BLOCKER | 2026-07-24 | HP-001 component-output readiness blocker packet | Proposed: define a fail-closed HP-side preflight manifest for future IC-1 component-output consumption. The preflight requires signed final HP approval IDs, a real artifact path and SHA-256 checksum, exact WEATHER-001 HP/PV identity equality, 35,040 quarter-hour steps at 900-second cadence, four separate HP-001 SFH/MFH space/DHW component traces, and no unresolved blocker IDs before an HP component-output artifact can be consumed. | Keeps future integration from treating a generated HP file as usable before annual values, adoption/electrification, A-016 scenario consistency, D-004 paired-weather acceptance, cold-spell tolerances, artifact checksums, and component provenance are all present. This row does not approve annual HP TWh values, 2035 adoption/electrification/service fractions, final D-004 paired-weather or cold-spell acceptance, net-load/event/`P(E)`/capacity-screen analysis, threshold runs, manuscript numbers, or probability results. | `reports/e2_s3_hp001_component_output_readiness_blocker.md`; `data/metadata/hp_scaling/hp001_component_output_readiness_blocker_packet.json`; `src/hp_model.py`; HP-001; D-003; D-004; D-013; WEATHER-001; A-016. | proposed blocker packet; executable HP outputs unsigned | -- |
| E2-S3-HP001-PROFILE-REBUILD-PREFLIGHT | 2026-07-24 | HP-001 profile artifact rebuild/checksum preflight template | Proposed: define a fail-closed metadata preflight before any future HP-001 profile artifact rebuild/checksum run. The preflight requires signed final HP approval IDs, explicit D-003 When2Heat, D-004 WEATHER-001 member, and D-013 value-binding source artifact path/checksum/provenance records, HP/PV paired-weather identity equality, 35,040 quarter-hour output targets, checksum-manifest targets, and no unresolved blocker IDs before the rebuild can run. | Keeps future HP artifact generation from starting on unsigned annual values, unsigned 2035 adoption/electrification/service fractions, missing D-004 paired/cold-spell acceptance, missing source artifacts/checksums, or mismatched HP/PV weather identity. This row does not approve annual HP TWh values, 2035 adoption/electrification/service fractions, D-004 final paired-weather or cold-spell acceptance, a real profile rebuild, net-load/event/`P(E)`/capacity-screen analysis, threshold runs, manuscript numbers, or probability results. | `reports/e2_s3_hp001_profile_rebuild_preflight.md`; `data/metadata/hp_scaling/hp001_profile_artifact_rebuild_preflight_template.json`; `src/hp_model.py`; `data/get_hp_scaling.py`; HP-001; D-003; D-004; D-013; WEATHER-001; A-016. | proposed preflight template; executable HP artifacts unsigned | -- |
| D013-PBL-MAPPING | 2026-07-23 | D-013 PBL Startanalyse indicator mapping assumption | Approved: for HP-001 local scaling, treat `_w` as woningen/residential and `_u` as utiliteit/non-residential; treat `H23_Vraag_RV_w` as residential space-heating demand intensity, `H24_Vraag_TW_w` as residential domestic-hot-water demand intensity, and `H22_Vraag_totaal_w` as a residential total-demand diagnostic, all in `[GJ/weq/jaar]`. This approves the indicator mapping/source-use assumption only. | No explicit public PBL suffix or H22/H23/H24 raw-column dictionary was found, but the interpretation is supported by PBL's documented H01/H02/H03 heat-demand concepts, the documented 2025 woningen/utiliteit split, the official Alkmaar CSV schema, and ASA25 template context. Recording it as an explicit assumption is more honest than hiding the inference in code. | D-013 schema inspection; PBL Startanalyse 2025 documentation; official Alkmaar CSV schema; ASA25 template context; A-015; PI decision in chat, 2026-07-23. | approved transparent assumption; executable values/adoption unsigned | PI approved in chat, 2026-07-23 |
| HP-001 | 2026-07-21 | First-pass residential HP source and technology boundary | Approved: use D-003 When2Heat `2023-07-27` `when2heat.csv` as the internal source for Dutch normalized residential heat-pump shape and COP trajectories. The primary HP layer includes residential space heating and domestic hot water: `NL_heat_profile_space_SFH` and `NL_heat_profile_space_MFH` use `NL_COP_ASHP_radiator`; `NL_heat_profile_water_SFH` and `NL_heat_profile_water_MFH` use `NL_COP_ASHP_water`. Preserve SFH/MFH and space/water components separately until aggregation. Commercial (`COM`) heat is excluded from the primary run and may only enter later signed sensitivities. Do not use When2Heat national `heat_demand_*` values as the local 2035 annual scaling by default; retain them as diagnostic/source anchors only. Agent C must propose a separate local annual HP scaling/adoption route for both space heat and domestic hot water before real integrated HP load is used. WEATHER-001 implementation, D-004 acceptance, cold-spell acceptance tolerances, final local scaling, event analysis, `P(E)`, capacity screens, and manuscript results remain blocked until separately signed. | A full residential move away from gas normally also electrifies domestic hot water, so excluding it from the primary HP boundary would understate household electrification demand. The selected When2Heat water-profile and ASHP-water COP columns provide a transparent route for that end use without adding commercial heat, whose building stock, adoption, and service-area boundary are less aligned with the residential neighbourhood case. Separating shape/COP from annual volume prevents country-level historical heat totals from becoming unreviewed local 2035 adoption assumptions. | PI approval in chat, 2026-07-21; `reports/e2_s3_hp_technology_scaling_decision_packet.md`; `reports/e2_s3_hp_source_use_pi_packet.md`; `reports/e2_s3_hp_scaling_evidence_packet.md`; `reports/e2_s3_d003_pi_review_packet.md`; D-003 retrieval/checksum metadata. | approved | PI approved in chat, 2026-07-21 |
| G2 | TBD | Tier-1 enclosure and adequacy | Pending: empirical Tier-1 error envelope, held-out near/above-threshold enclosure test, decision impact, and evaluator verdict | Determines Tier-1 primary / corrected Tier-1 / selective AC / Tier-1 rejected | E1.S2b corrected AC budget; E1.S1b headroom brief; E3.S2b frozen future domain/capacity screen; E3.S3 manifested tier comparison | pending | -- |
| G3 | TBD | Monotonicity verdict | Pending: vertex shortcut vs interior sampling | Critical compute shortcut | E4.S1 monotonicity report | pending | -- |
| G4 | TBD | Elicitation sign-off | Pending: fuzzy controllability corners | Paper hinge assumption | E7.S2 worksheet | pending | -- |
| G5 | TBD | Case selection | Pending: 2035 decision-reversal benchmark adoption/scenario and grid case; year is fixed by G0-A4 | Money figure depends on divergent treatments, but the year may not be selected after inspecting results | E8.S1 case sweep | pending | -- |
| G6 | TBD | Results freeze | Pending: paper numbers locked to manifests | Required before manuscript finalization | E9 robustness; E10.S1 figure dry-run | pending | -- |
| G7 | TBD | Submission | Pending: approve Applied Energy submission | Final paper gate | Manuscript, repro package, red-team report | pending | -- |
| DEP-001 | 2026-07-09 | Dependency pin update | Use `simbench==1.6.2` and `pandapower>=3.4,<4` in the `.venv` requirements. | Upstream SimBench 1.6.2 declares `pandapower>=3.4.0`; avoids the older `simbench==1.6.1` / `pandapower==3.5.3` top-level `compare_arrays` import break. | PI review of upstream `simbench` `pyproject.toml`; `.venv` metadata check; `.\scripts\task.ps1 test`; direct import check for `pandapower`, `simbench`, and `lightsim2grid`. | approved | PI approved in chat, 2026-07-09 |
| OWN-001 | 2026-07-17 | Machine-enforced agent path ownership | Enforce role-owned source and test paths through an explicit planned-path preflight, a complete local-worktree check, and pull-request CI. Shared governance paths remain available, while every unassigned path is denied by default. A cross-boundary exception is valid only when an exact branch, role, task, and path entry was PI-approved and already exists on the PR base branch. | Human instructions did not prevent an Agent A edit to Agent B-owned `src/pbox.py`. Base-revision policy loading prevents an agent from authorizing its own exception and turns ownership review into a merge-blocking check. The exact initial policy PR has a one-time bootstrap only while both policy files are absent from its base. | PI instruction in chat, 2026-07-17; `configs/agent_ownership.json`; `scripts/check_agent_ownership.py`; ownership CI job. | approved | PI directed implementation in chat, 2026-07-17 |
| EV-001 | 2026-07-10 | D-002 EV charging data source | Use the ElaadNL Laadprofielengenerator generated-profile route in `reports/elaad_profile_generation_spec.md` for D-002 instead of the unavailable historical ElaadNL/EVnetNL transaction dataset. First implementation step is a one-profile API probe; bulk profile-library generation waits until API semantics and terms-of-use notes are recorded. | The current ElaadNL download page exposes a Charging Energy Hubs neighbourhood opportunity workbook, not session/profile behavior data. The generator provides accessible, seeded, 15-minute Dutch Outlook-based EV charging profiles suitable for a frozen profile library or calibration target. | PI-provided profile-generation spec; local inspection of `data_CEH_kansrijkheid_2026Q1.xlsx`; ElaadNL dashboard/API URLs in D-002. | approved | PI approved in chat, 2026-07-10 |
| EV-002 | 2026-07-14 | D-002 generated ElaadNL profile use and redistribution boundary | Generated ElaadNL profiles may be used for internal project computations through the publicly accessible Laadprofielengenerator API. Do not commit or redistribute raw API responses or generated profile libraries; keep generated files under ignored `data/raw/` or ignored processed-data paths. Commit only retrieval/generation code, request configurations, distinct seed schedules, metadata, checksums, and manifests. The data-availability statement must direct readers to regenerate profiles through the public API subject to terms applicable at retrieval time. Do not claim generated profiles are openly licensed or redistributable. Record unresolved redistribution terms as a limitation/risk, but they no longer block internal project use. If explicit terms later prohibit this research use, stop and escalate. | Resolves the D-002 terms blocker while preserving a conservative redistribution boundary and reproducibility through code/config/metadata rather than committed generated data. | PI decision in chat, 2026-07-14; D-002 one-profile probe metadata; `reports/elaad_profile_generation_spec.md`. | approved | PI approved in chat, 2026-07-14 |
| EV-003 | 2026-07-15 | Primary EV aleatory representation | Use direct empirical bootstrapping from the frozen, checksummed ElaadNL annual profile library as the primary EV aleatory model. Retain complete annual members and record the selected member IDs and seed metadata in manifests. The fallback calibrated stochastic sampler is not primary, but remains an escalation path if seed semantics, available library size, or held-out downstream adequacy make direct bootstrapping invalid. The within-realization replacement rule is resolved by EV-005B for candidate member-selection implementation only. | Uses the accessible Dutch generator output without introducing an additional fitted behavioral model, while keeping finite-library uncertainty visible and testable under ALEA-002. | EV-001; EV-002; ALEA-001; ALEA-002; `reports/elaad_profile_generation_spec.md`; PI approval in chat, 2026-07-15. | approved | PI approved in chat, 2026-07-15 |
| EV-004 | 2026-07-16 | Fixed residential charge-point distribution | Represent the residential EV layer by one frozen distribution of complete annual, uncontrolled ElaadNL `cp` profiles for `location_type = home`, `cp_capacity_kw = 11`, and `simulated_year = 2030`. Reuse this behavior distribution in the 2030, 2033, and 2035 planning layers; scenario growth changes the externally sourced number and nodal allocation of home charge points, not the profile-generator year. The sampling unit is one physical home charge point, and ElaadNL's native home charge-point car/van mix is retained without reweighting. Conditional on the common ALEA-001 calendar and scenario, home charge points are modeled as exchangeable independent draws from this distribution. Public charging remains a separate profile class and is not fixed by this decision. | Fixing the generator year prevents its internal vehicle-count, charge-point-count, and efficiency forecasts from being varied at the same time as the project's external adoption layer. A charge-point sampling unit also matches the physical quantity counted by the adoption scenario and lets one fixed behavior distribution be reused transparently across planning layers. | ElaadNL `Documentatie Laadprofielengenerator`, 10 November 2025, pp. 5-13; ALEA-001; EV-003; PI approval in chat, 2026-07-16. | approved | PI approved in chat, 2026-07-16 |
| EV-005 | 2026-07-16 | Finite profile-library uncertainty | Treat the frozen library as a finite random sample from an unknown ElaadNL generator distribution. Keep finite-library uncertainty from `M` distinct from conditional Monte Carlo estimation uncertainty from `N`: use independent distinct-seed API batches, nested candidate libraries, disjoint held-out batches, and downstream transformer-result comparisons under CRN. An initial candidate of `M = 1000` home charge-point profiles may be generated in batches, but it is not declared sufficient a priori; extend it if the predeclared downstream adequacy test fails. The numerical adequacy tolerance remains pending until E3.S2a predeclares a decision-relevant criterion; the within-realization replacement rule is resolved separately by EV-005B for candidate member-selection implementation only. | Increasing `N` can estimate the result under a fixed empirical library very precisely without correcting an unrepresentative library. Independent held-out generation and nested-library stability expose that separate error source while avoiding an unsupported universal formula linking `M`, `K`, and `N`. | `reports/EV_FINITE_LIBRARY_UNCERTAINTY_PROTOCOL.md`; ALEA-002; EV-003; E2.S6; E3.S2a; PI approval in chat, 2026-07-16. | approved | PI approved in chat, 2026-07-16 |
| EV-005A | 2026-07-17 | Low-cost held-out replacement after precriterion diagnostics | The current held-out batches `141001` and `141101` are not scientifically invalid merely because source-level summaries were viewed, but they are reclassified as `quarantined_precriterion_diagnostic` and may not certify held-out adequacy. Because replacement costs only two API calls, generate fresh disjoint held-out seeds `141201` and `141301`, committing only request/provenance, checksums, structural validation, calendar/shape integrity, finite/nonnegative checks, and distinct-member counts before E3.S2a freezes its criterion. This is not a general automatic-redo rule: if similar remediation would require substantial computation, time, API calls, discarded evidence, or other material cost, stop and consult the PI before invalidating or repeating work. | Conservatively restores a clean held-out archive at low cost while preserving diagnostic history transparently and avoiding a precedent that expensive evidence must be discarded automatically. | PR #35 review follow-up; EV-005; `reports/elaad_profile_generation_spec.md`; D-002 manifests. | approved narrow follow-up | PI decision in chat, 2026-07-17 |
| EV-005B | 2026-07-22 | Within-realization EV replacement policy | Approved: use charge-point-level sampling with replacement from the verified candidate EV profile libraries for each component and EV-008A public capacity class. Record duplicate selections as explicit bootstrap multiplicities with full member, batch-seed, returned-index, checksum, and RNG-001 component-stream provenance. Whole-grid no-replacement is rejected for the approved 2035 Alkmaar cohorts because home K and public per-class K exceed candidate M. | Resolves the previously pending EV-005 replacement rule for candidate member-selection implementation while keeping finite-library adequacy separate. This approval does not certify library adequacy, open held-out or quarantined batches, load profile arrays for integrated use, run net-load/event/`P(E)`, produce manuscript numbers, or claim M sufficiency. | PI approval in chat, 2026-07-22; `reports/e2_s2_ev005b_pi_approval_note.md`; `reports/e2_s2_ev005_replacement_policy_packet.md`; `data/metadata/ev_adoption/e2_s2_ev005_replacement_policy_packet.json`; EV-003; EV-005; EV-007A; EV-008A; EV-CAL-001; RNG-001. | approved for candidate member-selection implementation only | PI approved in chat, 2026-07-22 |
| EV-006 | 2026-07-17 | Matched ElaadNL smart-charging seed protocol | When an ElaadNL smart-charging profile is generated as a counterfactual to an uncontrolled profile, reuse the exact uncontrolled batch seed and pair members by returned profile index. Identify each potential-outcome pair by `(batch_seed, returned_profile_index, control_mode)`. Same-seed uncontrolled and controlled outputs represent the same underlying annual demand and charging sessions under different control; compare or substitute them as a pair, but never sum or resample them as independent physical charge points. Seeds remain distinct between unrelated stochastic source batches, including candidate and held-out libraries. Set D therefore matches uncontrolled Set A batch `140001` instead of using an independent seed. This decision fixes pairing semantics only: it does not approve smart charging as the primary flexibility model or approve its base-capacity, ramp-speed, pooling, or controllability mapping. | ElaadNL explicitly states that a common seed preserves annual mileage, energy demand, and sessions and is useful for studying smart-control impacts, while warning that same-seed profiles must not be added because their sessions are duplicated. Matched treatment/control runs remove behavioral sampling noise from the comparison without violating the independence required when profiles represent different chargers. | ElaadNL `Documentatie Laadprofielengenerator`, 10 November 2025, pp. 6-7 and 14; `reports/elaad_profile_generation_spec.md`; PI instruction in chat, 2026-07-17. | approved seed protocol; smart-control role and parameters pending | PI directed correction in chat, 2026-07-17 |
| EV-007 | 2026-07-21 | Local EV adoption scaling route | Approved Q-7 Option A: derive SimBench-grid home and public charge-point totals from predeclared representative CBS neighbourhood-cluster forecasts using ElaadNL local forecast outputs. The cluster must be selected by exogenous area and feeder-scale criteria before inspecting congestion results. National D-010 totals remain provenance and scenario context only and must not be used directly as SimBench physical counts. A-014 may be used only as the second-stage within-grid allocation rule after the local totals are established. Option B, national adoption rates times sourced local denominators, remains a fallback or sensitivity if local forecast retrieval or justification fails. | Resolves the missing bridge between national adoption projections and feeder-scale counts without manufacturing congestion from national totals or reverse-engineering weak local denominators. It keeps local count selection separate from within-grid nodal allocation. | Q-7 PI approval in chat, 2026-07-21; PR #39 E2.S6 adoption scenarios; D-010; A-014. | approved | PI approved in chat, 2026-07-21 |
| EV-007A | 2026-07-21 | Alkmaar local EV adoption counts | Approved: use Alkmaar municipality `GM0361` as the representative local EV adoption proxy for the SimBench case study and promote the retrieved 2035 ElaadNL Outlook local counts to executable declared scenario branches: low `7992` home / `4183` public charge points, middle `9386` home / `5127` public, and high `10343` home / `6138` public. The neighbourhood endpoint failure is accepted for this first-pass municipality-level proxy. Delft `GM0503` remains a checked fallback only. Low/middle/high are declared inputs for screening and later G5 case selection; no final paper branch is chosen by this decision. A-014 remains the within-grid allocation rule, but per-node allocation materialization remains a separate implementation step. | The counts come from the current ElaadNL Outlook local forecast API for the PI-selected municipality before integrated congestion results were inspected. Using all three declared branches preserves scenario uncertainty without tuning the case to overload, while still avoiding invalid national-total scaling. | `configs/scenarios.yaml`; `reports/e2_s6_local_adoption_counts.md`; `reports/e2_s6_a014_alkmaar_allocation_preview.md`; D-010; EV-007; A-014; PI approval in chat, 2026-07-21. | approved | PI approved in chat, 2026-07-21 |
| EV-008 | 2026-07-21 | Superseded public charge-point profile protocol | Superseded: the original single-class 22 kW public Set B proposal is not approved as the primary public EV behavior library. Public profiles still use the ElaadNL public `cp` route, native public car/van mix, fixed `simulated_year = 2030`, and charge-point rather than pole semantics, but capacity handling is replaced by EV-008A. | D-012 supports the charge-point/EVSE/connector-like unit but weakens the claim that 22 kW is uniquely representative of current Alkmaar public AC charging. A signed single 22 kW future/upper-capacity convention remains possible only as a later sensitivity. | `reports/e2_s2_public_profile_decision_packet.md`; `reports/e2_s2_ev008_public_profile_amendment_packet.md`; D-012; EV-008A. | superseded by EV-008A | PI approved EV-008A Option 2 in chat, 2026-07-21 |
| EV-008A | 2026-07-21 | Public Set B capacity-stratified profile protocol | Approved: replace EV-008 with an equal-mix capacity-stratified public Set B design. Generate uncontrolled ElaadNL public `cp` profiles with native public `["van", "car"]` mixing, fixed `simulated_year = 2030`, 15-minute calendar, ignored raw/processed storage, and per-seed checkpoints for four AC capacity classes: `public_11kw`, `public_13kw`, `public_15kw`, and `public_22kw`. For physical public capacity allocation among these AC classes, use a simple 25%/25%/25%/25% split; D-012 shows the observed Alkmaar groups are close enough that equal shares are the cleanest defensible simplification. Generate a balanced candidate source library with `M = 1200`: 300 members per class from seeds `152001`, `152101`, `152201`; `152301`, `152401`, `152501`; `152601`, `152701`, `152801`; and `152901`, `153001`, `153101`. Generate a balanced held-out public library with `H = 400`: 100 members per class from seeds `153201`, `153301`, `153401`, and `153501`. Member identity must include partition, capacity class, `cp_capacity_kw`, batch seed, returned profile index, request checksum, raw JSON/gzip checksums, processed checksum, and control mode. This authorizes only public Set B source generation and structural validation; public smart charging, DC/fast charging, held-out adequacy use, integrated analysis, manuscript results, and any claim that the generated `M` is sufficient remain blocked. | Capacity stratification avoids presenting a future/upper-capacity convention as if it were an observed-current-fleet fact. Because the current NDW/DOT-NL Alkmaar AC groups are all near one quarter after excluding DC, zero-power, and missing-power records, equal 25% shares are easier to explain than overfitting small snapshot differences. Balanced 100-profile calls also keep the generation and recovery plan simple while preserving EV-005 downstream adequacy testing. | `reports/e2_s2_ev008_public_profile_amendment_packet.md`; `data/metadata/elaad_profiles/B_public_vancar_cp_y2030_amendment_packet.json`; `reports/e2_s2_ndw_public_charging_inventory.md`; D-012; EV-002; EV-003; EV-005; EV-008; PI clarification in chat, 2026-07-21. | approved | PI approved equal 25% capacity mix in chat, 2026-07-21 |
| EV-CAL-001 | 2026-07-22 | EV source-to-planning calendar mapping | Approved Option A: map complete 2025 ElaadNL EV source profiles onto the 2035 planning-year calendar by ordinal timestep index, so target timestep `i` uses source timestep `i`. The rule preserves exactly 35,040 15-minute timesteps, complete member order, member IDs, batch seed and returned-index provenance, candidate/held-out separation, and annual energy. It explicitly does not preserve 2035 weekday/weekend labels; that limitation must be recorded in mapping provenance. This approval authorizes readiness/adapter mapping code only; held-out adequacy, M sufficiency, replacement policy, integrated net-load/event/`P(E)`, and manuscript numbers remain blocked. | Option A is the smallest deterministic mapping from the fixed ElaadNL source calendar to the G0-A4 2035 planning calendar. It preserves complete EV source trajectories and avoids inventing repeated/skipped source-day rules before IC-1 consumes candidate profiles. The weekday/weekend mismatch is accepted transparently rather than hidden. | PI approval in chat, 2026-07-22; `reports/e2_s2_ev_calendar_mapping_decision_packet.md`; `data/metadata/ev_adoption/e2_s2_ev_calendar_mapping_decision_route.json`; EV-003; EV-004; EV-005; G0-A4; ALEA-001. | approved | PI approved Option A in chat, 2026-07-22 |
| COST-001 | 2026-07-10 | D-008 Cicenas thesis unit-cost source | Use the PI-supplied local Cicenas 2025 thesis PDF as the D-008 source for unit-cost extraction. The PDF must not be committed or redistributed. Every extracted number must record value, unit, exact meaning/context, thesis page, table/appendix/section label if available, source status (Stedin-confirmed, thesis-derived, or interpreted), intended project use, and PI sign-off before manuscript use. | The professor of the thesis is involved in the project, and the PI confirmed that thesis-derived unit costs are acceptable if every number is exactly traceable and cited wherever used. | Local raw file `data/raw/cicenas_2025_thesis.pdf`, sha256 `96EF9625BA0AFEE2910189A61967943BA3BCD460AE3AC080B847C4D8DD7D99C0`; literature-review anchor line 133. | approved | PI approved in chat, 2026-07-10 |

## G0 - Scope Freeze - 2026-07-09 - signed: PI approved in chat

Authority: this entry supersedes all illustrative examples of the overload
event, P_crit handling, and grid choice in the project plan and the actionable
plan. G0-A1 amends the event direction rules below. G0-A2 amends the primary
event time domain to the full planning year and demotes WindowSet to AC
validation and diagnostics. G0-A3 resolves Q-5 by retaining the numerical `1.0 p.u.` event
threshold below as the primary threshold, demoting `1.1` and `1.2 p.u.`
to predeclared sensitivities, and removing the mandatory Q-5 blocker. G0-A4 freezes 2035 as
the primary planning year while retaining 2030 and 2033 as supporting layers.
Changes to any item below require a new signed entry.

### 1. Decision Asset And Terminology

Canonical term = "decision transformer" in all code, configs, registers, and
prose. In the SimBench case study this is the HV/MV transformer bank at the
external-grid substation of the primary grid; the motivating MV/LV
neighbourhood case maps onto the same construction because the method is
level-agnostic. Exact pandapower element index(es) must be recorded in the
E1.S1 inventory and appended to this entry.

If parallel units exist, loading is defined as:

```text
L(t) = abs(sum_i S_i(t)) / sum_i S_nom_i
```

where `S_i(t)` is complex apparent power through unit `i`. This is the raw
magnitude of the complex net substation exchange over summed nameplate. G0-A1
conditions the primary event on import direction, while retaining this
direction-agnostic magnitude as the screening metric and for export-side
reporting. Tier-1 computes the magnitude from aggregated downstream net P and
Q.

Validity condition (see `ASSUMPTIONS.md` `A-005`): busbar-parallel identical
units, closed bus-tie, equal taps, and no circulating-current modeling, under
which aggregate loading equals each unit's individual loading. G2 must confirm
per-unit versus aggregate loading agreement within the summation-vs-AC
tolerance using pandapower `res_trafo.loading_percent`.

If the station has an open tie or separate MV sections, escalate: the decision
asset becomes a single section's transformer and aggregate loading is not used.

### 2. Overload Event E

Historical G0 wording is retained below for traceability. G0-A3 resolves Q-5
by confirming `1.0 p.u.` as the primary numerical threshold; historical
runs keep the threshold recorded in their manifests.

As amended by G0-A1, let `S_net(t) = P_net(t) + jQ_net(t)` be the aggregate
complex power through the decision transformer, with `P_net(t) > 0` denoting
net import from the upstream grid into the MV area. The loading quantities are:

```text
L_import(t) = abs(S_net(t)) / S_nom,agg   if P_net(t) > 0
            = 0                           otherwise

L_export(t) = abs(S_net(t)) / S_nom,agg   if P_net(t) < 0
            = 0                           otherwise
```

`P_net(t) = 0` belongs to neither direction and is captured only by the
unconditioned screening metric `abs(S_net(t)) / S_nom,agg`.

Event `E` operates on `L_import`: at least 4 consecutive 15-minute steps with
`L_import(t) > 1.0` p.u., meaning at least 1 hour, over the full planning year
per G0-A2. A direction flip resets the episode counter. Every results table
reports export-direction exceedance of `L_export` alongside `P(E)`.

`P(E)` is the probability, over the aleatory ensemble, that the planning year
contains at least 1 qualifying episode.

Justification: DSO loading-percent language, with congestion defined at more
than 100% loading, plus IEC 60076-7 cyclic thermal tolerance, which makes a
lone 15-minute excursion thermally meaningless. The single-step variant, any
one 15-minute step above 1.0 p.u., is retained as an E9 sensitivity only.

Scope statement for the manuscript: this study addresses consumption-driven
(`afname`) congestion deferral. Feed-in (`invoeding`) congestion is a distinct
planning problem with a distinct flexibility instrument such as absorption or
curtailment, and is out of scope except for transparent reporting.

### 3. P_crit And Sensitivity Protocol

Primary: `P_crit = 1e-2`, `N = 1e4` aleatory samples, full alpha grid from
item 6, and Tier-2 AC validation applies to this analysis.

Sensitivity: `P_crit = 1e-3`, `N = 1e5`, reduced alpha set `{0, 0.5, 1.0}`,
Tier-1 summation only, no AC validation at `1e-3`, and common random numbers
shared with the primary run. Local refinement is pre-authorized: add
`alpha = 0.25` or `alpha = 0.75` only if alpha_star under `1e-3` falls in a
bracket whose endpoints yield different decisions.

`P_crit` is frozen. Per G0-A4, the primary planning year is also frozen at
2035. Case interestingness is achieved at G5 only by selecting the declared
adoption/scenario branch and feeder/grid within 2035. It is never achieved by
threshold adjustment or by switching the primary year after inspecting
results.

### 4. Grid And Fallback

Primary: SimBench `1-MV-semiurb--0-sw`, with LV aggregated at secondary
substations. Baseline topology and profiles are SimBench scenario 0.
Technology layers for 2030, 2033, and 2035 come from II3050/ElaadNL-derived
`scenarios.yaml`, meaning Dutch adoption on validated topology. SimBench
scenarios 1 and 2 are appendix cross-checks only. CIGRE MV is a robustness
cross-check.

Pre-authorized fallback to `1-MV-urban--0-sw` is allowed if and only if the
deterministic screen, computed at E1.S1/E3 before any Monte Carlo, shows either:

```text
L_base > 0.85 p.u.
```

where `L_base` is the max 15-minute loading of the decision transformer under
SimBench scenario-0 profiles, deterministic, full year, using the G0-A1 primary
import-direction loading, indicating the grid is already congested and no
deferral question exists; or:

```text
L_2035^(rho=0) < 0.95 p.u.
```

where `L_2035^(rho=0)` is the max import-direction loading under the 2035
adoption layer with zero flexibility over the full planning year using the
G0-A1/G0-A2 import-direction loading semantics, indicating electrification
never threatens the limit and no reinforcement question exists.

Screen thresholds are routing heuristics for grid selection, not scientific
claims (see `ASSUMPTIONS.md` `A-008`). If `1-MV-urban--0-sw` fails the same
screen, escalate to the PI. Pre-considered options are to rescale the adoption
layer within the documented II3050 bandwidth, or to move the decision asset.
No silent tuning is allowed.

### 5. Weather

KNMI historical winters, including at least one design-cold winter, form the
aleatory weather ensemble. Coherence is with the Dutch scenario/profile layer
II3050, ElaadNL, and MFFBAS, not with the topology's German provenance (see
`ASSUMPTIONS.md` `A-007`).

### 6. Alpha Grid, Primary

Primary alpha grid: `{0, 0.25, 0.5, 0.75, 1.0}`. Use five levels, endpoint
vertex propagation per level once G3 confirms monotonicity, and nested-cut
common-random-number sample reuse.

### Assumptions Spawned By G0

Create as proposed rows in `ASSUMPTIONS.md`, PI to sign:

- `A-005`: parallel-unit collinearity / equal split / equal taps, verified
  empirically at G2.
- `A-006`: constant nodal power factor supplies Q for `abs(S)` in Tier-1; the
  flexibility aggregator adjusts P with Q following the power factor. This
  feeds the event definition directly.
- `A-007`: Dutch KNMI weather drives German-measured SimBench baseline
  profiles, justified because heating load is modeled separately through the
  heat-pump layer, leaving baseline demand weakly weather-coupled.
- `A-008`: fallback screen thresholds 0.85 and 0.95 p.u. are routing
  heuristics, not scientific claims.

### Open Items To Append After E1.S1 Follow-Up

- Decision-transformer element index(es) and unit count.
- Bus-tie configuration: closed parallel confirmed, or open-tie escalation.
- Fallback screen results: `L_base`, `L_2035^(rho=0)`, and resulting grid
  choice.

## G0-A1 - Event Direction And Fixed-Window Rejection Amendment - 2026-07-10 - signed: PI approved in chat

Authority: this entry amends G0 item 2, the G0 fallback-screen loading
interpretation, and the critical-window examples in the project/actionable
plans. G0-A2 supersedes the adaptive critical-window language for the primary
Tier-1 probability metric. Where this entry conflicts with earlier text, and
G0-A2 does not further amend it, this entry wins.

G0-A3 later resolves the numerical overload threshold by retaining `1.0 p.u.` as primary; this entry's direction and persistence semantics remain unchanged.

### 2a. Event Direction And Loading Quantity

Let `S_net(t) = P_net(t) + jQ_net(t)` be the aggregate complex power through
the decision transformer. Tier-1 computes this as the sum of downstream nodal
net P and Q. `P_net(t) > 0` denotes net import from the upstream grid into the
MV area.

```text
L_import(t) = abs(S_net(t)) / S_nom,agg   if P_net(t) > 0
            = 0                           otherwise

L_export(t) = abs(S_net(t)) / S_nom,agg   if P_net(t) < 0
            = 0                           otherwise
```

Convention: `P_net(t) = 0` belongs to neither direction. It is captured by the
unconditioned screening metric `abs(S_net(t)) / S_nom,agg`, which is retained
for E1.S3/E9.S3 screens.

The overload event `E` operates on `L_import`: at least 4 consecutive
15-minute steps with `L_import(t) > 1.0` p.u. A direction flip resets the
episode counter; this is the intended semantics for consumption congestion.
Every results table reports the export-direction exceedance of `L_export`
alongside `P(E)`.

Thermal correctness note: `abs(S)` is the loading quantity in both directions;
`sign(P_net)` is only the direction gate.

Manuscript scope statement: this study addresses consumption-driven (`afname`)
congestion deferral. Feed-in (`invoeding`) congestion is a distinct problem
with a distinct flexibility instrument and is out of scope, evidenced by the
E1.S3 screen.

### 2. Critical Windows

The fixed-winter-window assumption is retired. G0-A2 records the G1 outcome:
adaptive import-ranked WindowSets are retained for IC-1/IC-2 AC-validation
subset selection and diagnostics only, not for the primary Tier-1 probability
metric.

For diagnostic WindowSets, select adaptively per `(scenario, year, technology
layer)` from the import-direction loading ranking: use top-K import-ranked
weeks plus 1 margin week, with K documented from the coverage-vs-K curve.
These WindowSets do not alter the full-year event definition.

### 3. G3 Linkage

Monotonicity of `P(E)` in controllable demand reduction `rho` is claimed and
tested for the import-direction event only. The E1.S3 direction-agnostic
screen confirmed that export/PV feed-in can bind in SimBench future scenarios.
If export congestion is ever brought into scope, it requires the interior
sampling path and a distinct fuzzy flexibility instrument for absorption or
curtailment.

## G0-A2 - Full-Year Primary Event Scope - 2026-07-10 - signed: PI approved in chat

Authority: this entry amends G0 item 2 and supersedes the G0-A1 adaptive
critical-window language for the primary probability metric. Where it conflicts
with earlier project-plan or actionable-plan text, this entry wins.

G0-A3 later resolves the numerical overload threshold by retaining `1.0 p.u.` as primary; this entry's direction and persistence semantics remain unchanged.

Primary `P(E)` is annual: the probability that the full planning year contains
at least one qualifying import-direction overload episode, defined as at least
4 consecutive 15-minute steps with `L_import(t) > 1.0` p.u. A direction flip
resets the episode counter.

Tier-1 Monte Carlo evaluates the full planning year. `WindowSet` remains in
IC-1 and IC-2 for AC-validation subset selection and diagnostics only. It is
not part of the primary Tier-1 event definition.

Rationale: E1.S3b adaptive import windows span 19-25 weeks, or 36-48% of the
year. At that size, they defeat their compute purpose for the vectorized
Tier-1 summation evaluator and introduce avoidable window-transfer risk.
Full-year Tier-1 removes that approximation layer.

## G0-A3 - Primary 1.0 P.U. Overload Threshold - 2026-07-22 - signed: PI approved in chat

### Authority And Primary Event

This entry resolves Q-5 and supersedes the provisional 2026-07-16 working
threshold. It does not alter the import direction gate, apparent-power loading
quantity, direction-flip reset, four-step persistence rule, full-year
probability domain, or `P_crit`.

The primary event is:

```text
E = the planning year contains at least 4 consecutive 15-minute steps
    with L_import(t) > 1.0 p.u.
```

The inequality is strict: a value exactly equal to `1.0 p.u.` does not qualify.
The rule is evaluated on `L_import`, so direction flips reset the consecutive
step counter per G0-A1.

### Sensitivities And Diagnostics

Predeclared threshold sensitivities use the same persistent-event definition at
`L_import > 1.1 p.u.` and `L_import > 1.2 p.u.`. The single-step E9 sensitivity
remains separate and uses the declared threshold of its run. Export-side
exceedance diagnostics report the matching threshold beside the primary result
for transparency.

No separate cumulative-exposure rule is added for the `1.0` through `1.1 p.u.`
band in the primary analysis. Because the primary event already counts sustained
loading above `1.0 p.u.`, a companion cumulative rule for that band would change
the estimand rather than clarify it. Such a cumulative-exposure metric may be
added later only as a separately approved diagnostic or sensitivity.

### Rationale

The project defines a planning-congestion event, not transformer failure.
Nameplate exceedance is the clearest defensible primary threshold for that
purpose: it avoids presenting an insufficiently verified 110% value as a Dutch
DSO planning standard, while the one-hour persistence rule still distinguishes a
sustained overload from a single 15-minute excursion. IEC 60076-7 remains useful
background evidence that transformer loading is time-dependent and thermally
contextual, but it is not used here to claim that 1.1 p.u. is the primary
planning criterion.

The Q-5 blocker is resolved. Integrated event-based analysis may proceed once
all other required gates, data acceptances, output-error values, capacity
conventions, manifests, and ownership conditions are satisfied.
## G0-A4 - Primary 2035 Planning Year - 2026-07-17 - signed: PI approved in chat

### Primary And Supporting Years

The complete primary probabilistic analysis and E8 decision-reversal benchmark
use planning year 2035. This year is frozen prospectively, before the integrated
probabilistic results are inspected. E3.S2b still runs the predeclared
deterministic screen for 2030, 2033, and 2035. The 2030 and 2033 layers remain
supporting trajectory checks and inputs to the later deferral-horizon analysis;
they are not alternative primary years available for post-hoc selection.

### Routing Rule

G5 may select the declared adoption/scenario branch and feeder/grid within
2035. If the predeclared screen classifies the 2035 layer as having no relevant
congestion or congestion that is not flexibility-resolvable under the
admissible capacity conventions, work must stop for a signed amendment. Agents
must not silently switch to another year, change a frozen threshold, or tune
network or adoption inputs after inspecting the probabilistic results.

### Profile-Generator Year

This decision does not change EV-004. The primary residential EV behavior
library remains generated with ElaadNL `simulated_year = 2030` and is reused in
the 2035 planning layer. The project's external adoption counts and nodal
allocation represent 2035 growth, avoiding double counting the generator's
internal year-dependent outlook assumptions.

## G1 - Foundation Validated - 2026-07-10 - signed: PI approved in chat

### Approved

Two-tier compute architecture. Tier-1 radial summation, per G0-A1 direction
semantics and G0-A2 full-year event scope, is the Monte Carlo inner-loop
evaluator because it is near-exact for the transformer criterion and
computationally negligible. AC power flow serves deterministic checks and
validation subsets.

The E1.S2 benchmark establishes only that the pandapower `runpp` path,
approximately 105 ms per solve on the 117-bus primary grid, cannot host the
Monte Carlo loop. It does not establish infeasibility of `lightsim2grid`'s
lower-level path, whose flag showed no speedup and likely never engaged. No
"AC infeasible" claim may appear in the manuscript.

### Approved With Change

Fixed winter windows are rejected, based on E1.S3 evidence. However, adaptive
windows spanning 19-25 weeks, or 36-48% of the year, defeat their compute
purpose in Tier-1. Tier-1 therefore runs the full planning year, and the event
definition drops the window clause per G0-A2: `P(E)` is the probability of at
least one qualifying episode in the planning year.

`WindowSet` is retained in IC-1 and IC-2 for AC-validation subset selection and
diagnostics only.

### Conditions Before G2

`C1`: Benchmark the `lightsim2grid` `TimeSeriesCPP` adapter properly and
diagnose the absent `runpp` speedup. Report the corrected AC validation budget.

`C2`: Produce a headroom diagnostic memo: substation transformer ratings; peak
import MVA versus total and firm `(n-1)` aggregate nameplate; implied 2035 load
multiplier under both definitions. The memo must flag the anticipated
G0-item-4 escalation and the firm-capacity redefinition option for PI decision.

`C3`: Agent A proceeds to E1.S4 with G0-A1 semantics
(`import`/`export`/`screening` series and direction-flip episode reset) and
G0-A2 full-year event scope.

### Unchanged From Draft

Export exceedance is reported alongside all primary results. No Dutch
2030/2033/2035 window or loading claims may be made before E2/E3. No vertex
shortcut may be used before G3. Agent C remains blocked on D-002 ElaadNL terms.

## G1-A1 - Black-Box Model Error And Tier-1 Approximation - 2026-07-13 - signed: PI approved in chat

### Authority And Scope

This entry amends G1, the G2 gate, E5.S3, and the behavioral boundary between
IC-2 and IC-3. It supersedes any wording that applies fixed margins directly
to an already estimated overload probability. At G1-A1, exact error values,
units, form, symmetry, the G2 numerical adequacy criterion, and the exact IC
schema change remained deferred; G1-A2 subsequently freezes relative symmetric
grid-error form while retaining the other stated dependencies.

G1's earlier description of Tier-1 as "near-exact" is a hypothesis pending the
G2 held-out enclosure result, not an established manuscript claim.

### Black-Box Grid-Model Error

The project has no field measurements that validate the DSO planning model
directly against physical loading. The grid-model discrepancy `delta_grid` is
therefore an author-specified interval assumption unless later evidence or a
human sign-off supplies stronger provenance; it is not an empirically
determined quantity within this project. Its numerical value, asserted domain,
units/form, and mandatory sensitivity sweep must be recorded in a signed
`ASSUMPTIONS.md` row before paper results use it. Any future empirical
validation must be recorded together with its validated domain.

No probability distribution is assigned to `delta_grid`. The analysis admits
every discrepancy function within the signed envelope, including arbitrary
unknown dependence on aleatory inputs `X`, flexibility controllability `rho`,
and time. This is neither probabilistic independence nor one constant bias.

### Tier-1 Approximation Error And Interval Composition

Tier-1 is a computational approximation to pandapower. G2 shall empirically
characterize

```text
delta_Tier1(X, rho, t) = L_PP(X, rho, t) - L_T1(X, rho, t)
```

over the operating domain used by the paper. G1-A2 later froze
`epsilon_grid` as relative and the Tier-1 enclosure as additive, so a simple
sum of their numerical values is not the current composition. Use the exact
G1-A2 endpoint formulas. If G2 supports asymmetric or one-sided Tier-1
endpoints, that tighter form is retained. No cancellation or root-sum-of-
squares combination is allowed without a later signed dependence model.

### Event And Probability Propagation

The applicable output-error interval is applied to each loading trajectory
before the G0-A1/G0-A2 four-consecutive-step event detector. Lower and upper
event indicators are evaluated from the lower and upper loading endpoints, and
Monte Carlo confidence intervals are computed from those resulting event
counts. Probability estimates or their confidence intervals are never shifted
after estimation to represent grid-model error.

The G0-A1 import/export gate is evaluated on the unwidened `P_net` sign. The
error envelope widens loading magnitude only. The rationale is that direction
ambiguity is confined to the zero crossing, where loading is expected to be
event-irrelevant; G2 must check this and escalate any counterexample.

The pure interval error has the same support at every alpha level and is never
probabilized or defuzzified. Before G3, `rho` still requires the approved
interior-sampling path. If G3 confirms monotonicity, the lower vertex combines
the favorable `rho` endpoint with the lower loading-error endpoint and the
upper vertex combines the adverse `rho` endpoint with the upper loading-error
endpoint.

### Revised G2 Gate

G2 shall use a manifested, domain-covering AC validation design spanning
ordinary, extreme, near-capacity, and overloaded import states; the current
G0-A3 primary `1.0 p.u.` threshold neighborhood plus the predeclared
`1.1` and `1.2 p.u.` sensitivity neighborhoods; relevant years, `rho` values, power
factors, and consecutive-step episodes. A held-out near/above-threshold stratum must not be
used to tune an envelope or correction.

A hard enclosure acceptance test on that held-out stratum is frozen in kind.
Its numerical strictness, including whether 100% bracketing is required, must
be signed before the held-out result is inspected. Failure prevents an
unqualified "Tier-1 adequate" verdict.

G2 must recommend exactly one of: Tier-1 adequate; Tier-1 adequate with a
validated correction; selective AC for predeclared threshold-straddling states
or episodes; or Tier-1 rejected. Selective AC must preserve CRN and manifest
discipline and record the promotion rule before execution.

### Envelope Form And Interface, As Amended By G1-A2

G1-A2 selects a relative symmetric grid-error envelope because it is invariant
to the total-versus-firm `(n-1)` `S_nom,agg` convention. The additive Tier-1
endpoints established at G2 remain expressed in the selected loading-p.u.
convention and use the exact mixed composition in G1-A2.

IC-2/IC-3 must retain enough information to apply the interval before episode
classification and to preserve the unwidened direction gate. A boolean-only
sample callback is noncompliant. Agents A and B must propose the smallest
compatible schema change for separate PI approval before E5.S3 implementation.

PR #13 requires revision: its useful configuration and invariant-test
structure may be retained, but probability-domain widening must be replaced by
output-domain trajectory propagation and four-step event tests.

## G1-A2 - Grid-Error And Capacity-Screen Protocol - 2026-07-14 - signed: PI approved in chat

### Authority And Scope

This entry amends G1-A1, A-013, G2, E3.S3, and E5.S3. It freezes the error
form, dependence treatment, composition rule, direction-gate order, and the
process for defining the operating domain and choosing the capacity
convention. It does not sign a numerical value for `epsilon_grid`; the draft
5% reference and 2%/10% sensitivities remain proposed pending evidence review
and a later PI sign-off of A-013.

### Grid-Error Form And Dependence

`epsilon_grid` is a symmetric relative envelope on the physical loading that
would be obtained at the DSO model boundary. Within this project it is an
author-specified scenario assumption, not an empirically measured bound,
confidence interval, or completed expert elicitation. No distribution is
assigned to it. Its dependence on inputs, controllability, time, and Tier-1
error is arbitrary within the envelope; independent sampling, root-sum-of-
squares combination, and a constant-bias interpretation are prohibited.

### Exact Composition

Let `L_T1(t)` be nonnegative Tier-1 loading. Let the G2 additive Tier-1
enclosure be `epsilon_Tier1_minus` and `epsilon_Tier1_plus`, expressed in the
same loading-p.u. convention as `L_T1`. For `0 <= epsilon_grid < 1`, define

```text
L_PP_lower(t) = max(0, L_T1(t) - epsilon_Tier1_minus)
L_PP_upper(t) =        L_T1(t) + epsilon_Tier1_plus

L_lower(t) = (1 - epsilon_grid) * L_PP_lower(t)
L_upper(t) = (1 + epsilon_grid) * L_PP_upper(t)
```

If G2 accepts a symmetric Tier-1 envelope, both Tier-1 endpoints equal
`epsilon_Tier1`. The lower and upper trajectories are passed through the
four-consecutive-step event detector. The import/export gate is evaluated on
the unwidened `P_net` sign before loading is widened. Event probabilities and
Monte Carlo confidence intervals are computed from the endpoint event counts;
probabilities are never widened afterwards.

### Operating Domain

The earlier illustrative `16-104 MVA` or `0.2-1.3 p.u.` applicability range is
rejected. In particular, 104 MVA was only `1.3 * 80 MVA`; no measurement,
simulation result, or primary source established it as a validity boundary.

After EV, heat-pump, PV, adoption, and net-load layers are integrated, E3.S2b
shall run one versioned and manifested deterministic screening experiment over
the predeclared 2030/2033/2035 cases and flexibility endpoints. Before any
probabilistic result is inspected, its input ranges and resulting physical-MVA
span shall define and freeze the asserted operating domain used by A-013 and
the G2 validation design. Later samples outside that domain are flagged and
escalated; they are not silently extrapolated, clipped, or used to refit the
domain.

### Total Versus Firm Capacity

For the present two-unit bank, the candidate denominators remain total
nameplate `80 MVA` and firm `(n-1)` nameplate `40 MVA`. E3.S2b shall report raw
transformer MVA and loading under both conventions for every screened case.
The PI shall then select the convention using planning meaning, Dutch-practice
evidence where available, and whether flexibility can materially change the
decision. A convention shall not be selected solely because it manufactures
an interesting congestion case. If neither convention supports a usable case,
the existing G0 fallback/escalation route applies and any load or network
adjustment must be explicit, sourced, and signed before use.

Dividing normal two-transformer flow by 40 MVA is a headroom diagnostic only.
If firm capacity becomes the primary criterion, E3.S3 must model and validate
the actual one-transformer-out topology with AC power flow; G0/A-005/A-013 and
the G2 domain must then be amended to cover that operating state.
## EV-CAL-001 - EV Source-To-Planning Calendar Mapping - 2026-07-22 - signed: PI approved Option A in chat

### Authority And Scope

EV-CAL-001 approves ordinal timestep mapping for EV readiness and later IC-1
adapter use. Each complete candidate EV source profile generated on the 2025
ElaadNL Europe/Amsterdam calendar is mapped to the G0-A4 2035 planning calendar
by index: target timestep `i` receives source timestep `i`.

### Preserved Quantities

The rule preserves all 35,040 15-minute demand values in their source order,
member IDs, batch seed, returned profile index, processed checksum provenance,
source-library identity, and candidate/held-out partition separation. Annual
energy is unchanged because the demand vector is neither sorted, repeated,
skipped, scaled, nor percentile-compressed.

### Explicit Limitation

Ordinal mapping does not preserve actual 2035 weekday/weekend or holiday labels
when they differ from the 2025 source calendar. Mapping provenance must record
`weekday_weekend_preserved = false` and the source-index policy
`target_index_i_uses_source_index_i`.

### Boundaries

This approval does not open or use held-out adequacy batches, certify home
`M = 1000` or public `M = 1200` sufficient, choose the within-realization
replacement policy, run net-load, congestion, event, `P(E)`, or capacity-screen
analysis, or authorize manuscript numbers.
## PV-CAP-001 - PV Installed-Capacity Source Route - 2026-07-23 - signed: PI approved in chat

### Approved Route

Executable PV installed capacity is sourced through a local-to-scenario route. The local anchor is Alkmaar photovoltaic capacity from a concrete CBS StatLine photovoltaic-capacity table, to be retrieved, checksummed, and registered under D-014. The planning-year value is derived by scaling that local anchor to the frozen 2035 planning layer with a signed Netbeheer Nederland II3050/scenario growth factor.

DEGO, CBS building/geography data, Zonnedakje, and the PI-supplied Kostas thesis may guide source discovery or spatial allocation only if the exact concrete data source, license, retrieval path, and provenance are registered before use. Zonnedakje is not a primary executable source unless accessible downloadable Alkmaar data are available and registered. Per PV-ORIENT-001, building-specific roof geometry is deferred until after the first real experiment; the first-experiment PV geometry route uses a signed typical/statistical orientation-and-tilt distribution instead.

### Boundary

This decision approves the capacity-source route only. It does not approve any numeric capacity value, exact CBS row/year/field, II3050 scenario value, DC-versus-AC capacity convention, per-node allocation, PV-PARAM-001 conversion parameters, final paired HP/PV acceptance, net-load/event analysis, `P(E)`, capacity screens, or manuscript results. Those must remain separate signed artifacts before executable PV input is allowed.

### Rationale

The route keeps the method close to the DSO story: start from auditable local observed installed capacity, then apply a transparent Dutch infrastructure-scenario growth layer for the 2035 case. It also keeps the capacity problem separate from the PV conversion formula, preventing the irradiance model from silently inventing how many panels exist or where they are connected.

## PV-ORIENT-001 - First-Experiment PV Orientation/Tilt Scope - 2026-07-24 - signed: PI approved in chat

### Approved Scope

For the first real experiment, PV orientation and tilt are represented only through a typical/statistical distribution. Agents must not implement per-building, per-roof, or location-specific orientation/tilt extraction, roof-plane allocation, or a 3DBAG/PV-map geometry pipeline in the first-experiment path.

The existing PV-PARAM-001 first-pass proposal remains the starting point, amended by this scope decision. It may use a signed statistical orientation/tilt distribution, but the exact source, bins, weights, and conversion treatment are still unsigned and must be recorded before executable PV generation.

### Deferred Improvement

The full roof-level workflow, including specific roof geometry, local surface matching, pvlib-style plane-of-array modelling, and PV-map project implementation, is explicitly deferred until after the first real experiment. It may be used later as a sensitivity, refinement, or separate implementation track once the first go/no-go run exists.

### Boundaries

This approval does not sign PV-PARAM-001 values, the statistical distribution itself, a GHI-to-plane transposition rule, installed PV capacity, node allocation, D-014 retrieval/value choices, final paired HP/PV acceptance, cold-spell tolerances, net-load/event analysis, `P(E)`, capacity screens, or manuscript results.

### Rationale

The first experiment needs a tractable and transparent PV component, not a building-specific PV cadastre. A typical orientation/tilt distribution captures more physical diversity than one fixed south-facing reference while avoiding a second, roof-level modelling workstream before the project has produced its first integrated result.
