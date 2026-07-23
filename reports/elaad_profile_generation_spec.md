# ElaadNL Laadprofielengenerator — Profile Generation Specification

**Project:** "When can grid reinforcement wait? Bounding overload probability under deeply uncertain demand-side flexibility"
**Feeds:** work-breakdown story E2.S2 (EV model) and E2.S1 (data acquisition); Track 1 of the three-track EV data strategy.
**Source of truth for the tool:** *Documentatie Laadprofielengenerator*, ElaadNL, 10 November 2025 (uploaded PDF). Dashboard: https://charging.elaad.nl/ · API: HTTP POST to https://api.charging.data.elaad.nl (endpoint `profile/simulate`) · API docs: https://api.charging.data.elaad.nl/docs#
**Status of this document:** generation specification and archive record — every batch below can be executed either manually via the dashboard or programmatically via the API using the exact JSON bodies given. Set A and approved public Set B source-generation batches have been generated locally, checksummed, and structurally validated; raw and processed profile files remain ignored and unredistributed.

---

## 1. Purpose and role in the project

The generator is ElaadNL's dashboard + API that produces charging profiles based on the assumptions of the ElaadNL Outlooks (current version largely based on **Outlook Personenauto's 2024** and **Outlook Logistiek 2025**). For this project it serves three purposes:

1. **P1 — NL calibration/fallback target (Track 1, E2.S2 T2).** Aggregate charging shapes per location type remain available to calibrate and validate the UK-DfT-fitted stochastic sampler if the direct-library route fails its seed, cohort-size, or downstream-adequacy conditions.
2. **P2 — Frozen NL profile library (primary per EV-003).** Because the generator is seeded, session-based, future-year-aware, and 15-min native, the frozen library serves directly as the EV aleatory layer. Complete annual members are bootstrap-resampled per Monte Carlo draw and traced by `(batch seed, returned profile index)`. The exact replacement rule inside one system realization remains open until the same-seed warning and scenario cohort sizes are resolved; the fallback sampler must not be substituted silently.
3. **P3 — Smart-charging cross-check (optional).** One same-seed matched batch with the generator's own "Smart charging (17h–23h)" mode, to isolate and sanity-check the direction and magnitude of the control effect against our flexibility aggregator.

**What the generator is NOT used for:** representing our fuzzy controllability factor ρ̃_flex. All base profiles are generated **uncontrolled** ("dumb charging"); flexibility activation at controllability ρ is applied downstream by our own nodal aggregator (E3.S1). The generator's smart-charging modes appear only in the optional P3 comparison.

**Scope of location types.** The decision unit is a residential MV area (SimBench, LV aggregated at secondary substations). The location types that electrically load residential substations are **home** and **public** (street chargers in the neighbourhood). Work, rest_area, fast_charging_city, depot, charging_hub, and truck_parking load other parts of the network and are **out of scope** for the nodal EV layer (work/fast/rest shares of car demand are deliberately *excluded* from nodal load — see §3.6).

---

## 2. Tool facts (from the 10 Nov 2025 documentation)

| Item | Fact |
|---|---|
| Interfaces | Dashboard (≤ **100** profiles per run; large runs take minutes) and API (≤ **500** profiles per batch) |
| Endpoint | `POST https://api.charging.data.elaad.nl` → `profile/simulate`; full docs at `/docs#` |
| Profile types | `cp` (charge point: one charge point visited by different EVs) and `ev` (one EV charging at charge points of ONE location type to satisfy its demand **at that location type**) |
| Location types | `depot`, `charging_hub`, `truck_parking`, `rest_area`, `fast_charging_city`, `public`, `work`, `home` |
| Vehicle types | `truck`, `van` (bestelauto), `car` (personenauto); lists allowed for CP profiles (e.g. `["van","car"]`) |
| Mixed locations | At rest areas, fast-charging city, public, and home locations, cars and vans share charge points; for CP profiles the car/van ratio is applied **automatically** and cannot be chosen |
| Key parameters | `start_datetime`, `stop_datetime` (ISO, with timezone), `step_size_s` (900 = 15 min), `timezone` (e.g. `"CET"`), `simulated_year` (prognosis year, e.g. 2035), `profile_type`, `n_profiles`, `location_type`, `vehicle_types`, `cp_capacity_kw`, `seed` |
| Output | JSON: `config`, `statistics` (null), `profile: {cp_ids, datetimes, demands_kw}`; **datetimes are returned in UTC** and must be converted to CET/CEST manually |
| Seed semantics | Same seed preserves annual mileages, energy demand, and sessions and is explicitly useful for a smart-control comparison. **Documented warning: same-seed outputs must NOT be summed as independent chargers** because they contain the same sessions. Use distinct seeds for unrelated profiles that will be aggregated; deliberately reuse the seed only for a labelled treatment/control pair under EV-006 |
| Model basis | Energy demand per EV from CBS annual-mileage distributions × efficiency (Outlook Logistiek 2025: truck 1.1 kWh/km, van 0.3 kWh/km, car 0.2 kWh/km); laadmix per vehicle/location (cars, Outlook Laadprofielen 2023: 55% public, 19% home, 17% work, 4.5% rest areas, 4.5% urban fast); weekly energy sampled with a seasonal distribution; sessions simulated with an SoC-dependent charging curve capped by available capacity; at public locations two charge points share one pole connection (limits simultaneous power); smart charging shifts unmet in-session demand to later moments; **V2G is not part of the generator** |
| Versioning | Current generator based on Outlook Personenauto's (2024) + Outlook Logistiek (2025); **next major update expected around summer 2026** |

---

## 3. Global generation conventions (apply to every batch)

**3.1 Time base.** Full calendar year per batch: `start_datetime = "2025-01-01T00:00:00+01:00"`, `stop_datetime = "2026-01-01T00:00:00+01:00"`, `step_size_s = 900`, `timezone = "CET"`. Expect 35,040 steps per profile; assert this on receipt. Critical winter weeks are **sliced locally** after download — never generate isolated weeks, because the generator distributes annual energy over weeks with a seasonal distribution and a partial-year request would break that consistency and re-randomize sessions.

**3.2 Calendar vs. prognosis year.** `start/stop` define the simulated calendar; `simulated_year` selects the generator's prognosis parameters, including estimated energy-demand effects from vehicle counts, charge-point counts, and vehicle efficiency. Per EV-004, the primary residential library fixes the calendar at 2025 and `simulated_year = 2030`. Downstream alignment follows ALEA-001 and `reports/JOINT_ALEATORY_SAMPLING_PROTOCOL.md`: complete EV trajectories are mapped deterministically to the common season and weekday/weekend calendar, while the paired multivariate weather member remains intact. The exact leap-year and daylight-saving mapping is predeclared, versioned, and tested after the concrete KNMI files are selected; no result may rely on an undocumented timestamp repair.

**3.3 Planning years.** Reuse the one fixed 2030 residential charge-point distribution for the 2030, 2033, and 2035 planning layers. `scenarios.yaml` carries the year-specific number and nodal allocation of physical home charge points. Do not generate residential 2033 or 2035 behavior libraries for the primary model: varying both ElaadNL's internal forecast year and the external adoption counts would mix two sources of scenario growth. A 2025 or 2035 generator-year run is allowed only as a separately labelled sensitivity, not as a primary layer input.

**3.4 Charging control.** All P1/P2 batches: **no smart charging** (uncontrolled). Only Set D (P3) uses `Smart charging (17h–23h)`.

**3.5 Charge-point capacity.** EV-004 fixes `cp_capacity_kw = 11` for the primary home charge-point class. EV-008A now governs public Set B source-generation capacity as an equal mix over 11, 13, 15, and 22 kW AC classes; no public sensitivity, smart-charging class, DC/fast class, or alternative capacity convention may be generated without a separate PI decision.

**3.6 Residential sampling unit and scaling.** The primary home member is one `cp` profile for one physical home charge point. ElaadNL automatically includes its forecast car/van mixture in home charge-point profiles, and the project does not reweight that mixture. Nodal aggregation therefore selects and sums `K_r` complete members for the externally sourced number of home charge points at node `r`; it applies no additional home-share or vehicles-per-charge-point multiplier. The earlier vehicle-level scaling proposal A-011 is superseded. Public charge points remain a separate class.

**3.7 Seed governance.** Generator seeds are **batch seeds**. Seeds are distinct between unrelated stochastic source batches, including candidate and held-out libraries. EV-006 defines one deliberate exception: a smart-charging counterfactual repeats the uncontrolled batch seed and pairs each returned member by index, because both outputs must contain the same annual demand and sessions. The pair identity is `(batch_seed, returned_profile_index, control_mode)`. A matched uncontrolled/smart pair is compared or substituted as two potential outcomes and is never summed or resampled as two independent physical charge points. Until multi-profile semantics are verified, batches remain intact in held-out and leave-out diagnostics. The Monte Carlo layer never calls the API: it bootstrap-resamples archived complete members per node per draw, driven by the project seed tree (`src/rng.py`). Two-layer rule: *ElaadNL seed = which source realization exists; control mode = which potential outcome is used; CRN seed = which members a draw selects.*

**3.8 Freeze-and-archive policy (do this in Week 1–2).** The generator is a **live service** with a major update expected around summer 2026 — mid-project model drift is a real risk. Therefore: generate the approved sets promptly, convert to the implemented compressed NPZ batch format, checksum, and register; the archived files are the frozen dataset. Every batch's manifest records: full JSON request body, response `config` block, retrieval timestamp, documentation version (10 Nov 2025), and the underlying Outlook editions (Personenauto's 2024, Logistiek 2025). The paper cites the archived dataset, not the live service.

**3.9 Batch sizing and finite-library design.** API limit is 500 profiles/batch, but a full-year 15-min response for 500 profiles is a very large JSON payload; use **100 profiles per call** so batch-level diagnostics and retries remain manageable. Set A grows in complete batches toward an initial candidate `M = 1000`, followed by `H = 200` untouched held-out profiles per EV-005. Per EV-005A, seeds `141001` and `141101` are retained only as quarantined precriterion diagnostics and fresh held-out seeds are `141201` and `141301`. `M = 1000` is not accepted a priori. Retry a failed request idempotently with the same body, but never register the retry as a new batch.

---

## 4. The generation matrix — exact batches

Every set lists: purpose, exact API request body, the dashboard alternative, batch seeds, volume, storage path, and acceptance checks. Raw API responses go under the git-ignored root `data/raw/elaad_profiles/`; manifests, checksums, and request metadata go under `data/metadata/elaad_profiles/`; converted compressed NPZ batches go under the ignored `data/processed/elaad_profiles/` directory. Use one file per batch, naming `{set}_{location}_{vehicle}_{profiletype}_y{simulated_year}_batchseed{seed}_n{count}`.

### Set A — Home charge-point library (PRIMARY; purposes P1 + P2)

The core library: charge-point-level, uncontrolled home charging, one complete year, with the generator's native car/van mix.

| Field | Value |
|---|---|
| Volume | Initial candidate **M = 1,000**, quarantined diagnostic **Q = 200**, and fresh held-out **H = 200** (14 API calls × 100 including the quarantined diagnostics); sufficiency decided only by EV-005/E3.S2a |
| Generator year | 2030 only; reused for the 2030, 2033, and 2035 planning layers |
| Candidate batch seeds | 140001, 140101, ..., 140901; the 13xxxx range is retained as legacy provenance |
| Quarantined diagnostic seeds | 141001 and 141101; retained transparently but not candidate members and not held-out adequacy evidence |
| Fresh held-out batch seeds | 141201 and 141301; unopened for adequacy analysis until the E3.S2a design is frozen |
| Storage | `data/processed/elaad_profiles/A_home_vancar_cp_y2030_*.npz` |

API body (first candidate batch; repeat with the listed batch seeds):

```json
{
    "start_datetime": "2025-01-01T00:00:00+01:00",
    "stop_datetime": "2026-01-01T00:00:00+01:00",
    "step_size_s": 900,
    "timezone": "CET",
    "simulated_year": 2030,
    "profile_type": "cp",
    "n_profiles": 100,
    "vehicle_types": ["van", "car"],
    "location_type": "home",
    "cp_capacity_kw": 11,
    "seed": 140001
}
```

Dashboard alternative: charging.elaad.nl → profile type *charge point*, location *thuis (home)*, native car/van selection, year 2030, 100 profiles, 11 kW, seed as above, no smart charging, download, repeat per batch.

**Source checks:** 35,040 steps × 100 series per batch; all demands ≥ 0; returned profiles are not identical. Candidate and quarantined diagnostic batches may retain annual-energy and seasonal-shape summaries as diagnostics without hard-coded acceptance values. Fresh held-out batches commit only request/provenance, checksums, structural validation, calendar/shape integrity, finite/nonnegative checks, and distinct-member count until E3.S2a freezes its criterion. Scientific adequacy is decided only downstream under EV-005. EV-005A's low-cost replacement does not create a blanket requirement to redo materially expensive work without PI consultation. The already retrieved `A_home_car_ev_y2030` probe remains a diagnostic artifact and is not part of this primary `cp` library.

### Set B — Public CP library (APPROVED by EV-008A for source generation only)

Charge-point-level profiles for neighbourhood public chargers; the car/van ratio is applied automatically by the tool. The profile member remains one public charge point, not a pole. The documentation states that at public locations two charge points share one pole connection, which affects simultaneous maximum power; any pole-level reporting or asset-count conversion must preserve that convention instead of relabelling one generated member as one pole.

| Field | Value |
|---|---|
| Volume | Candidate **M = 1,200** and held-out **H = 400**; sufficiency decided only by EV-005/E3.S2a |
| Generator year | `2030`, matching EV-004 behavior-year discipline so external adoption counts carry planning-year growth |
| Capacity mix | Equal physical public AC mix: 25% each for 11, 13, 15, and 22 kW classes |
| Candidate batch seeds | `152001, 152101, 152201`; `152301, 152401, 152501`; `152601, 152701, 152801`; `152901, 153001, 153101` |
| Held-out batch seeds | `153201`, `153301`, `153401`, and `153501`; unopened for adequacy analysis until the E3.S2a design is frozen |
| Body deltas vs Set A | `"location_type": "public"` and capacity-class-specific `"cp_capacity_kw"` in `{11, 13, 15, 22}`; keep `profile_type = "cp"`, `vehicle_types = ["van", "car"]`, uncontrolled, 100 profiles per batch |
| Storage | `data/processed/elaad_profiles/B_public_*_vancar_cp_y2030_*.npz`; ignored and not redistributed |

Approved API body (first candidate batch; repeat with the listed batch seeds and capacity classes):

```json
{
    "start_datetime": "2025-01-01T00:00:00+01:00",
    "stop_datetime": "2026-01-01T00:00:00+01:00",
    "step_size_s": 900,
    "timezone": "CET",
    "simulated_year": 2030,
    "profile_type": "cp",
    "n_profiles": 100,
    "vehicle_types": ["van", "car"],
    "location_type": "public",
    "cp_capacity_kw": 11,
    "seed": 152001
}
```

EV-008A supersedes the single 22 kW EV-008 proposal. Public Set B generation is authorized only for these uncontrolled AC capacity classes and only for source generation plus structural validation. The approved Set B source library was generated as 16 checkpointed 100-profile API calls and is recorded in `data/metadata/elaad_profiles/B_public_vancar_cp_y2030_set_b_library_manifest.json` and `reports/elaad_e2_s2_public_set_b_library_report.md`. Public smart charging, DC/fast charging, held-out adequacy analysis, integrated net-load or event analysis, manuscript results, and any claim that `M = 1,200` is sufficient remain blocked.

### Set C — Calibration subset (purpose P1; no new generation)

C is defined as candidate Set A batch `140001`. It is used only to exercise and validate the fallback fitted sampler: compare reconstructable charging starts, annual energy, seasonal daily shape, and coincidence versus aggregation size. It is not separate data and is never used as held-out evidence.

### Set D — Smart-charging comparison batch (purpose P3; OPTIONAL — generate only if the E9 cross-check is activated)

| Field | Value |
|---|---|
| Volume | 100 profiles matched one-to-one to uncontrolled Set A candidate batch `140001`; reuse batch seed `140001` and pair by returned profile index |
| Mode | *Smart charging (17h–23h)*, **without pooling** |
| Mode parameters | `base capacity` and `ramp speed` — **PI decision before generation** (proposal to react to: base 4 kW per CP during 17–23h, ramp 6 kW/h; both are placeholders, not defaults) |
| Use | Compare each smart profile with its same-session uncontrolled counterpart to isolate peak reduction and post-23h rebound; direction-of-effect and rebound-timing sanity check only — NOT a calibration of ρ̃_flex |
| Storage | `D_home_vancar_cp_sc1723_y2030_*.npz` |

### Set E — Present-day baseline (OPTIONAL; cheap validation)

100 home charge-point profiles at `simulated_year = 2025` (batch seed 525001), used only to diagnose the effect of fixing the primary behavior distribution at 2030. This optional sensitivity is not combined with Set A and is not a planning-layer input.

**Explicitly out of scope:** all truck/van logistics location types (`depot`, `charging_hub`, `truck_parking`), `rest_area`, `fast_charging_city`, and `work` — they do not load the residential decision transformer in our case study. If the case is ever extended to a mixed feeder, this spec gains a Set F; do not improvise one.

---

## 5. Seed governance table

| Set | Year | Seed range | Count | May be aggregated with |
|---|---|---|---|---|
| A candidate | 2030 | batch seeds 140001–140901 in steps of 100 | 1000 | primary residential library after EV-005 acceptance |
| A quarantined diagnostic | 2030 | batch seeds 141001, 141101 | 200 | diagnostic history only; excluded from candidate membership and held-out adequacy certification |
| A held-out | 2030 | batch seeds 141201, 141301 | 200 | validation only after E3.S2a freezes the criterion unless a failed test triggers a new candidate cycle |
| B equal-mix public | 2030 | candidate seeds 152001, 152101, 152201; 152301, 152401, 152501; 152601, 152701, 152801; 152901, 153001, 153101; held-out seeds 153201, 153301, 153401, 153501 | candidate 1200; held-out 400 | public AC source library after EV-008A; adequacy only after E3.S2a freezes its downstream criterion |
| C | 2030 | subset: A batch 140001 | 100 | fallback analysis only; not held out |
| D | 2030 | batch seed 140001 reused from A | 100 matched counterparts | compare/substitute only; never aggregate with its A counterparts as independent chargers |
| E | 2025 | batch seed 525001 | 100 | optional sensitivity only |

Rules: (1) unrelated stochastic batches use distinct ElaadNL seeds; (2) EV-006 smart counterfactuals deliberately repeat the corresponding uncontrolled seed and add `control_mode` to the member identity; (3) a same-seed treatment/control pair is never counted or aggregated as two physical chargers; (4) candidate and held-out batches never overlap; (5) the CRN tree (`src/rng.py`) governs member selection and the API is never called inside the Monte Carlo loop; (6) with- versus without-replacement selection inside one realization remains pending under EV-005 and must not be inferred from this table.

---

## 6. Post-processing pipeline (per batch, scripted in `data/get_elaad_profiles.py`)

1. POST request → save raw JSON to `data/raw/elaad_profiles/` (gzip).
2. Parse: assert `len(datetimes) == 35040`. The 2026-07-10 one-profile API probe returned `demands_kw` time-major (`len(demands_kw) == len(datetimes)`, each row containing one value per returned profile), not profile-major. Preserve this observation in metadata and reshape to timestamp-indexed profile columns during conversion.
3. **Convert datetimes UTC → Europe/Amsterdam** (documented tool behaviour: output is UTC regardless of request timezone); assert the converted series starts 2025-01-01 00:00 local.
4. Compressed NPZ: timezone-aware UTC timestamps, local timestamps, member IDs `(batch_seed, returned_index)`, and a `float32` kW matrix with one complete annual column per member.
5. Checksum (sha256) → `DATA_REGISTER.md` row and `data/metadata/elaad_profiles/` manifest: source (charging.elaad.nl API), request body, retrieval timestamp, documentation version 10 Nov 2025, Outlook basis (Personenauto's 2024 / Logistiek 2025), and EV-002 non-redistribution note. Generated profiles are for internal project computation; raw responses and generated libraries are not committed or redistributed.
6. Library summary report per set. Set A may retain candidate/quarantined diagnostics, while fresh held-out and all public Set B artifacts commit only request/provenance, checksums, structural validation, calendar/shape integrity, finite/nonnegative checks, and distinct-member count until E3.S2a freezes the downstream adequacy criterion.

---

## 7. Open items — verify against the live API docs (`/docs#`) before the first real batch

1. **Multi-profile home CP probe** — verify that the EV-004 request body is accepted, that all 100 returned members are distinct, and that the dashboard/API's native aggregation supports summing members from one response.
2. **Is `work` a valid `location_type` API value?** The doc's parameter list omits it while the tables include it — irrelevant to our sets but resolve for the record.
3. **Rate limits / max payload** — confirm 100-profiles-per-call full-year responses are accepted; tune §3.9 batch size.
4. **Seed vs. n_profiles semantics** — confirm that one seed governs a reproducible batch while returned member indices identify mutually distinct charge-point trajectories. Until confirmed, keep batch-level held-out and resampling units and do not authorize the within-realization replacement rule.
5. **Terms of use / license** — EV-002 approves internal project computation through the public API and requires regenerate-script-only data availability. Generated profiles must not be described as openly licensed or redistributable. If explicit terms later prohibit this research use, stop and escalate.
6. **`statistics` field** — currently `null` in examples; check whether a populated mode exists (session-level metadata would improve Set C's calibration power).
7. **Smart-pair reproducibility** — before any Set D analysis, verify that repeating Set A batch seed `140001` with only the declared smart-control fields changed returns the same member count and pairable member order; compare annual energy and document any unmet-session energy rather than assuming exact conservation.
8. **Public Set B adequacy/use** — EV-008A has signed the equal-mix source-generation protocol, and Set B has been generated and structurally validated. E3.S2a must still freeze the downstream adequacy criterion before held-out public profiles are opened or `M = 1,200` is treated as sufficient.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Generator major update ~summer 2026 changes profiles mid-project | Freeze-and-archive in Week 1–2 (§3.8); cite archived dataset + doc version |
| API unavailable / payload limits | Dashboard fallback (100/run; Set A is 10 candidate plus 2 held-out runs); batch retry idempotence |
| Seed semantics differ from our reading | Open item §7.4 resolved before Monte Carlo integration; worst case: regenerate with corrected seed plan (cheap) |
| Redistribution not permitted or terms remain ambiguous | EV-002 boundary: generated files stay ignored and unredistributed; repro package ships generation code, request configurations, seed schedules, metadata, checksums, and manifests; data-availability text directs readers to regenerate via the public API subject to terms at retrieval time |
| Residential scaling double-counting (§3.6) | Explicit rule + unit test: node EV energy equals the selected charge-point-member sum, with no extra home-share or vehicles-per-point factor |
| Finite library omits relevant behavior | EV-005 nested, disjoint, leave-out, and untouched held-out downstream tests; extend and regenerate a new holdout if the test fails |
| Smart and uncontrolled runs use independent sessions or are accidentally co-aggregated | EV-006 same-seed/index pairing, explicit `control_mode`, and a test that forbids treating the two potential outcomes as independent chargers |

## 9. Acceptance checklist (spec is "done" when)

- [ ] Open items §7.1–.8 resolved and recorded here.
- [x] Set A candidate, quarantined diagnostic, and held-out batches generated, archived, checksummed, and registered; public Set B source-generation batches generated and structurally validated under EV-008A; Sets D/E remain optional.
- [ ] Library source reports produced; Set C calibration deltas reported in the E2.S2 fit report.
- [x] EV-004 fixes the primary residential charge-point class and 2030 generator year.
- [x] EV-005 requires separate finite-library and Monte Carlo uncertainty evidence.
- [ ] E2.S6 records signed 2030/2033/2035 home/public charge-point counts and nodal allocation.
- [x] EV-008A signs the public Set B equal-mix capacity-stratified source-generation protocol.
- [ ] E3.S2a predeclares the numerical downstream adequacy tolerance before held-out results are opened.
- [x] EV-003 records P2 direct empirical bootstrapping as the primary EV layer; P1 remains an explicit fallback if seed, cohort-size, or downstream-adequacy conditions fail.
