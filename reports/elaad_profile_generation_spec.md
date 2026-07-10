# ElaadNL Laadprofielengenerator — Profile Generation Specification

**Project:** "When can grid reinforcement wait? Bounding overload probability under deeply uncertain demand-side flexibility"
**Feeds:** work-breakdown story E2.S2 (EV model) and E2.S1 (data acquisition); Track 1 of the three-track EV data strategy.
**Source of truth for the tool:** *Documentatie Laadprofielengenerator*, ElaadNL, 10 November 2025 (uploaded PDF). Dashboard: https://charging.elaad.nl/ · API: HTTP POST to https://api.charging.data.elaad.nl (endpoint `profile/simulate`) · API docs: https://api.charging.data.elaad.nl/docs#
**Status of this document:** generation specification — every batch below can be executed either manually via the dashboard or programmatically via the API using the exact JSON bodies given. Nothing has been generated yet.

---

## 1. Purpose and role in the project

The generator is ElaadNL's dashboard + API that produces charging profiles based on the assumptions of the ElaadNL Outlooks (current version largely based on **Outlook Personenauto's 2024** and **Outlook Logistiek 2025**). For this project it serves three purposes:

1. **P1 — NL calibration target (Track 1, E2.S2 T2).** Aggregate charging shapes per location type, against which the UK-DfT-fitted stochastic sampler is calibrated and its NL-transfer assumption validated.
2. **P2 — Frozen NL profile library (candidate upgrade).** Because the generator is seeded, session-based, future-year-aware, and 15-min native, a sufficiently large library of distinct-seed profiles can serve *directly* as the EV aleatory layer (bootstrap-resampled per node per Monte Carlo draw). Whether P2 replaces the UK-fitted sampler as primary is a **PI decision** after the P1 comparison — this spec supports both without rework.
3. **P3 — Smart-charging cross-check (optional).** One batch with the generator's own "Smart charging (17h–23h)" mode, to sanity-check the direction and magnitude of our flexibility aggregator's peak shift against ElaadNL's implementation.

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
| Seed semantics | Same seed ⇒ identical annual mileages, energy demand, and sessions ⇒ identical output. **Documented warning: profiles with the same seed must NOT be summed** — they contain the same sessions and misrepresent charging simultaneity. Use distinct seeds for anything that will be aggregated |
| Model basis | Energy demand per EV from CBS annual-mileage distributions × efficiency (Outlook Logistiek 2025: truck 1.1 kWh/km, van 0.3 kWh/km, car 0.2 kWh/km); laadmix per vehicle/location (cars, Outlook Laadprofielen 2023: 55% public, 19% home, 17% work, 4.5% rest areas, 4.5% urban fast); weekly energy sampled with a seasonal distribution; sessions simulated with an SoC-dependent charging curve capped by available capacity; at public locations two charge points share one pole connection (limits simultaneous power); smart charging shifts unmet in-session demand to later moments; **V2G is not part of the generator** |
| Versioning | Current generator based on Outlook Personenauto's (2024) + Outlook Logistiek (2025); **next major update expected around summer 2026** |

---

## 3. Global generation conventions (apply to every batch)

**3.1 Time base.** Full calendar year per batch: `start_datetime = "2025-01-01T00:00:00+01:00"`, `stop_datetime = "2026-01-01T00:00:00+01:00"`, `step_size_s = 900`, `timezone = "CET"`. Expect 35,040 steps per profile; assert this on receipt. Critical winter weeks are **sliced locally** after download — never generate isolated weeks, because the generator distributes annual energy over weeks with a seasonal distribution and a partial-year request would break that consistency and re-randomize sessions.

**3.2 Calendar vs. prognosis year.** `start/stop` define the simulated calendar; `simulated_year` selects the prognosis parameters (fleet, volumes, behaviour). We hold the calendar fixed at 2025 and vary `simulated_year`. Weekday alignment between this 2025 calendar, the SimBench profile calendar, and KNMI weather years is handled downstream by the documented weekday-mapping rule in the profiles module — record as an ASSUMPTIONS row when implemented.

**3.3 Planning years.** Generate `simulated_year = 2030` and `2035`. For the intermediate 2033 target year: **do not assume the API accepts 2033** — verify against `/docs#` (open item §7). If unavailable, rule: use the 2035 behavioural library for 2033 and let nodal *counts* (our `scenarios.yaml`) carry the 2033 volume — per-vehicle behaviour drift 2033→2035 is second-order relative to counts (ASSUMPTIONS row A-EV-1).

**3.4 Charging control.** All P1/P2 batches: **no smart charging** (uncontrolled). Only Set D (P3) uses `Smart charging (17h–23h)`.

**3.5 Charge-point capacity.** `cp_capacity_kw = 11` for home (3-phase 16 A residential standard; ASSUMPTIONS row A-EV-2 with 7.4 kW sensitivity noted), `cp_capacity_kw = 22` for public (two CPs per pole share the connection internally per the model — no extra correction on our side).

**3.6 The laadmix nuance (critical for correct scaling).** An `ev` profile at `home` covers **only the home share** of that EV's annual energy (the generator applies the laadmix internally; cars ≈ 19% home in the Outlook Laadprofielen 2023 mix). Therefore: when attaching home EV profiles to a node, scale by the **number of EVs with home-charging access at that node** and do **NOT** additionally multiply by a home-share factor — that would double-count the mix. Public CP profiles are scaled by the **number of public charge points** at the node. The split of node EV counts into home-access vs public-reliant is a `scenarios.yaml` parameter (ASSUMPTIONS row A-EV-3), not a generator setting.

**3.7 Seed governance.** Generator seeds are **library seeds**, disjoint across all sets (table in §5) so that any cross-set aggregation is safe under ElaadNL's same-seed warning. The Monte Carlo layer never calls the API: it **bootstrap-resamples** archived library profiles per node per draw, driven by the project seed tree (`src/rng.py`). Two-layer rule: *ElaadNL seed = which library member exists; CRN seed = which members a draw uses.* Never reuse an ElaadNL seed within or across sets.

**3.8 Freeze-and-archive policy (do this in Week 1–2).** The generator is a **live service** with a major update expected around summer 2026 — mid-project model drift is a real risk. Therefore: generate all sets below immediately, convert to parquet, checksum, and register; the archived files are the frozen dataset. Every batch's manifest records: full JSON request body, response `config` block, retrieval timestamp, documentation version (10 Nov 2025), and the underlying Outlook editions (Personenauto's 2024, Logistiek 2025). The paper cites the archived dataset, not the live service.

**3.9 Batch sizing.** API limit is 500 profiles/batch, but a full-year 15-min response for 500 profiles is a very large JSON payload; default to **100 profiles per call** (matching the dashboard limit) and increase only if the API demonstrably handles more. Sequential calls with consecutive seed sub-ranges; retry idempotently (same body ⇒ same output).

---

## 4. The generation matrix — exact batches

Every set lists: purpose, exact API request body (repeat per seed sub-range), the dashboard alternative, seed range, volume, storage path, and acceptance checks. Raw API responses go under the git-ignored root `data/raw/elaad_profiles/`; manifests, checksums, and request metadata go under `data/metadata/elaad_profiles/`; converted parquet libraries go under `data/processed/elaad_profiles/` and are not committed while `*.parquet` remains ignored. Use one file per batch, naming `{set}_{location}_{vehicle}_{profiletype}_y{simulated_year}_seed{first}-{last}`.

### Set A — Home EV library, passenger cars (PRIMARY; purposes P1 + P2)

The core library: vehicle-level, uncontrolled home charging of passenger cars, one full year, per prognosis year.

| Field | Value |
|---|---|
| Volume | **M = 1,000 profiles per simulated_year** (10 API calls × 100, or 10 dashboard runs) |
| Years | 2030 (seeds 130001–131000) and 2035 (seeds 135001–136000) |
| Storage | `data/processed/elaad_profiles/A_home_car_ev_y2030_*.parquet`, `..._y2035_*.parquet` |

API body (2035 example; first sub-range — repeat with `seed` 135101, 135201, … and note `n_profiles` per call vs. seed sub-ranges must be reconciled per the API's seed semantics, open item §7.4):

```json
{
    "start_datetime": "2025-01-01T00:00:00+01:00",
    "stop_datetime": "2026-01-01T00:00:00+01:00",
    "step_size_s": 900,
    "timezone": "CET",
    "simulated_year": 2035,
    "profile_type": "ev",
    "n_profiles": 100,
    "vehicle_types": "car",
    "location_type": "home",
    "cp_capacity_kw": 11,
    "seed": 135001
}
```

Dashboard alternative: charging.elaad.nl → profile type *EV*, location *thuis (home)*, vehicle *personenauto (car)*, year 2035, 100 profiles, seed as above, no smart charging, download, repeat ×10.

**Acceptance checks:** 35,040 steps × 100 series per batch; all demands ≥ 0; per-profile annual energy plausible for the *home share* of a car (order 19% × ~2,600 kWh/yr ≈ 400–700 kWh, wide spread expected — record the empirical distribution, don't hard-fail); mean-of-library winter-evening peak shape visually consistent with ElaadNL Outlook home profiles.

### Set B — Public CP library, mixed car/van (purposes P1 + P2)

Charge-point-level profiles for neighbourhood public chargers; the car/van ratio is applied automatically by the tool.

| Field | Value |
|---|---|
| Volume | **M = 200 per simulated_year** (2 × 100) |
| Years | 2030 (seeds 230001–230200), 2035 (seeds 235001–235200) |
| Body deltas vs Set A | `"profile_type": "cp"`, `"vehicle_types": ["van", "car"]`, `"location_type": "public"`, `"cp_capacity_kw": 22` |
| Storage | `B_public_vancar_cp_y{Y}_*.parquet` |

**Acceptance checks:** step count; utilisation plausibility (public CPs busier than home); no profile identical to another (distinct-seed sanity).

### Set C — Calibration subset (purpose P1; no new generation)

C is **defined as the first 100 seeds of Set A per year** (135001–135100, 130001–130100). Used in E2.S2 T2 to calibrate/validate the UK-DfT-fitted sampler: compare (i) arrival-time density of charging starts, (ii) session-energy distribution (as far as reconstructable from power traces), (iii) aggregate mean daily profile winter vs. summer, (iv) coincidence factor vs. n aggregated profiles. Deltas reported in the fit report; the UK→NL transfer ASSUMPTIONS row cites these deltas as its evidence.

### Set D — Smart-charging comparison batch (purpose P3; OPTIONAL — generate only if the E9 cross-check is activated)

| Field | Value |
|---|---|
| Volume | 100 profiles, `simulated_year` 2035, home, car, seeds 435001–435100 |
| Mode | *Smart charging (17h–23h)*, **without pooling** |
| Mode parameters | `base capacity` and `ramp speed` — **PI decision before generation** (proposal to react to: base 4 kW per CP during 17–23h, ramp 6 kW/h; both are placeholders, not defaults) |
| Use | Compare peak reduction and post-23h rebound against our aggregator at an equivalent controllability setting; direction-of-effect and rebound-timing sanity check only — NOT a calibration of ρ̃_flex |
| Storage | `D_home_car_ev_sc1723_y2035_*.parquet` |

### Set E — Present-day baseline (OPTIONAL; cheap validation)

100 home/car EV profiles at `simulated_year = 2025` (seeds 525001–525100), to check the generator's present-day output against current NL statistics before trusting its 2030/2035 extrapolations. Generate together with Set A; analysis is a half-day.

**Explicitly out of scope:** all truck/van logistics location types (`depot`, `charging_hub`, `truck_parking`), `rest_area`, `fast_charging_city`, and `work` — they do not load the residential decision transformer in our case study. If the case is ever extended to a mixed feeder, this spec gains a Set F; do not improvise one.

---

## 5. Seed governance table

| Set | Year | Seed range | Count | May be aggregated with |
|---|---|---|---|---|
| A | 2030 | 130001–131000 | 1000 | everything (all ranges disjoint) |
| A | 2035 | 135001–136000 | 1000 | everything |
| B | 2030 | 230001–230200 | 200 | everything |
| B | 2035 | 235001–235200 | 200 | everything |
| C | — | ⊂ A (first 100/yr) | — | never aggregated with its parent A members in one nodal draw (same sessions!) — C is analysis-only |
| D | 2035 | 435001–435100 | 100 | analysis-only, never in nodal load |
| E | 2025 | 525001–525100 | 100 | analysis-only |

Rules: (1) an ElaadNL seed appears exactly once across the whole project; (2) any nodal aggregation draws **distinct library members** (bootstrap *without* replacement within one node-draw; across draws replacement is fine); (3) the CRN tree (`src/rng.py`) governs which members are drawn — the API is never called inside the Monte Carlo loop.

---

## 6. Post-processing pipeline (per batch, scripted in `data/get_elaad_profiles.py`)

1. POST request → save raw JSON to `data/raw/elaad_profiles/` (gzip).
2. Parse: assert `len(datetimes) == 35040`; assert `len(demands_kw) == n_profiles`.
3. **Convert datetimes UTC → Europe/Amsterdam** (documented tool behaviour: output is UTC regardless of request timezone); assert the converted series starts 2025-01-01 00:00 local.
4. Wide parquet: index = local timestamp, columns = `profile_{seed}_{i}`, values = kW, float32.
5. Checksum (sha256) → `DATA_REGISTER.md` row and `data/metadata/elaad_profiles/` manifest: source (charging.elaad.nl API), request body, retrieval timestamp, documentation version 10 Nov 2025, Outlook basis (Personenauto's 2024 / Logistiek 2025), license note (**open item §7.5 — confirm terms of use before redistribution or manuscript data-availability claims**), status `proposed` for PI sign-off.
6. Library summary report per set: annual-energy histogram, mean daily profile winter/summer, coincidence-factor curve, max simultaneous power vs. n.

---

## 7. Open items — verify against the live API docs (`/docs#`) before the first real batch

1. **Allowed `simulated_year` values** — is 2033 accepted? If yes, prefer native 2033 (seeds 133001–134000, M = 1000, mirrors Set A) over the §3.3 fallback rule.
2. **Is `work` a valid `location_type` API value?** The doc's parameter list omits it while the tables include it — irrelevant to our sets but resolve for the record.
3. **Rate limits / max payload** — confirm 100-profiles-per-call full-year responses are accepted; tune §3.9 batch size.
4. **Seed vs. n_profiles semantics** — confirm whether one `seed` governs the whole batch (all 100 profiles) or per-profile seeds are derivable; adjust the §5 accounting so that "distinct library members" remains guaranteed (if one seed spans 100 profiles, the seed ranges above become batch seeds and the member id is `(seed, index)` — the aggregation rules apply per member, and the same-seed warning applies per *batch*, meaning members within one batch are already mutually distinct sessions; confirm this reading with ElaadNL if ambiguous).
5. **Terms of use / license** of generated profiles for use in a publication and for redistribution of the archived parquet library (affects the repro package: redistribute vs. regenerate-script-only).
6. **`statistics` field** — currently `null` in examples; check whether a populated mode exists (session-level metadata would improve Set C's calibration power).

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Generator major update ~summer 2026 changes profiles mid-project | Freeze-and-archive in Week 1–2 (§3.8); cite archived dataset + doc version |
| API unavailable / payload limits | Dashboard fallback (100/run — Set A is 10 runs per year); batch retry idempotence |
| Seed semantics differ from our reading | Open item §7.4 resolved before Monte Carlo integration; worst case: regenerate with corrected seed plan (cheap) |
| Redistribution not permitted | Repro package ships the generation script + this spec + request bodies instead of the parquet files |
| Home-share double-counting (§3.6) | Explicit rule + unit test in the nodal attachment code: node EV energy ≈ members' energy sum, no extra mix factor |

## 9. Acceptance checklist (spec is "done" when)

- [ ] Open items §7.1–.6 resolved and recorded here.
- [ ] Sets A, B, E generated, archived, checksummed, registered (Set D deferred until E9 activation decision).
- [ ] Library summary reports produced; Set C calibration deltas reported in the E2.S2 fit report.
- [ ] PI has signed the DATA_REGISTER rows and the A-EV-1/2/3 ASSUMPTIONS rows.
- [ ] PI decision recorded: P2 library as primary EV layer, or UK-fitted sampler as primary with P1 calibration — with rationale.
