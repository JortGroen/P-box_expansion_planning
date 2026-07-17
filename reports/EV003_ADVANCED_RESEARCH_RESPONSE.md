# EV-003 Advanced Research Response

> **Provenance:** Advanced-AI research response supplied by the PI on
> 2026-07-15.
> **Status:** Advisory evidence only. This document is not a signed project
> decision, and its proposed values do not supersede `registers/DECISIONS.md`
> or `registers/ASSUMPTIONS.md`.

# Decision Document EV-003: ElaadNL Profile-Library Size and Public Charging Capacity for a Dutch MV Reinforcement Study

## TL;DR
- **Library size:** Replace the fixed 1,000 home / 200 public heuristic with a *derived* sample size from a sequential batch-generation + held-out convergence test on grid-relevant outputs. Treat 1,000/200 only as generation caps, not adequacy targets. The public library must NOT be one-fifth the home library — public CP heterogeneity (car/van mix, occupancy, dual-socket pole sharing) makes its convergence at least as demanding; expect the two libraries to converge to comparable sizes (target order ~2,000 each).
- **Public capacity:** Do NOT use a bare `cp_capacity_kw = 22` as "the load seen by the grid." The evidence supports a **station-level model with 11 kW as the primary per-connector value plus mandatory sensitivity cases**, because ElaadNL's own Outlook convention is 11 kW, most EV onboard chargers cap at 11 kW AC, and the public pole shares one grid connection (~17.25 kW for 3×25 A) across two sockets.
- **API diagnostic:** Run paired, identical-seed generations varying only `cs_capacity_kw` at fixed `cp_capacity_kw = 22` to prove whether the 17.25 kW station connection clips public profiles; compare max 15-min power, counts above thresholds, total energy, and load-duration curves.

## Key Findings
1. **The ElaadNL generator already models a shared pole connection for public locations.** The official documentation (v. 10 Nov 2025, p.13) states verbatim that at public locations "twee laadpunten samen een laadpaal met een gezamenlijke aansluiting vormen" (two charge points together form one charging pole with a shared connection), which limits the maximum power both sockets can draw simultaneously. This means the load seen by the grid is governed by a station/pole capacity, not the per-connector nameplate.
2. **ElaadNL's standard regular charging power is 11 kW** for home, public and work charging in its Outlook prognoses (and 350 kW for fast chargers): "In haar prognoses rekent ElaadNL met een standaard laadvermogen van 11 kW voor thuis-, publieke- en werklaadpunten en 350 kW voor snellaadpunten." Home charge points are explicitly capped at 11 kW in the Outlook Personenauto's 2024.
3. **The default `cs_capacity_kw = 17.25` corresponds to a 3×25 A, 230 V station connection** (3 × 25 × 230 ≈ 17,250 W). ElaadNL's FlexPower field report documents exactly this: poles with a technical capacity of 3×25 A ≈ 17.25 kW, where under double occupancy each connected car receives 11 A × 3 phases (≈ 7.6 kW each).
4. **A nominal 22 kW connector rarely delivers 22 kW.** Most passenger-EV onboard chargers cap AC intake at 11 kW three-phase (or 7.4 kW single-phase); a 3×25 A pole physically cannot supply two 22 kW sockets simultaneously.
5. **Public CP profiles are not "less variable" in a way that justifies a smaller library.** Aggregating sessions inside one CP profile reduces within-profile variance, but the library must span *between-CP* heterogeneity and upper-tail coincidence — statistics that converge slowly and set the required member count.
6. **Extreme upper-tail quantiles (99th, 99.9th) require substantially larger samples than means**, and the bootstrap is known to be unreliable for the most extreme order statistics — a decisive argument against a small public library if tail loads matter.
7. **Coincidence/diversity factors converge with aggregation size.** Bollerslev et al. (IEEE Trans. Transp. Electrif. 8(1):808–819, 2022) find that "the coincidence factor decreases to less than 25% when considering more than 50 EVs with a charging level of 11 kW, with the coincidence factor strongly depending on the number of EVs considered." The same study notes a phase effect: single-phase (3.7 kW) charging keeps the CF below 45%, whereas for three-phase (11 kW) "the combined peak power of the EV population increases by only 50% (despite a 3-times power increase) ... hence the CF is reduced to 25%."

## Details

### 1. Executive recommendation
**Question 1 (library size):** Reject the 1,000/200 pair as *derived* sample sizes; adopt them only as upper generation caps. Determine each library independently using a reproducible, sequential batch-generation procedure with a held-out convergence test on grid-relevant statistics (annual energy, seasonal and time-of-day shape, upper 15-min quantiles, coincidence factors at representative aggregation sizes, and overload-event counts). The public library should be sized by the *same* convergence criterion as the home library and is expected to need a comparable — not smaller — number of members. Recommended operating points (justified in §3): home EV — initial 500, minimum 1,000, target 2,000, maximum 5,000; public CP — initial 500, minimum 1,000, target 2,000, maximum 5,000.

**Question 2 (public capacity):** Adopt option (d)+(e): a **station-level model with one primary per-connector value (11 kW) plus mandatory sensitivity cases**, retaining the generator's native pole-sharing (`cs_capacity_kw` ≈ 17.25 kW). Rationale: 11 kW is ElaadNL's own modelling convention, matches the dominant onboard-charger limit, and reflects the load actually delivered per socket; 22 kW is a hardware nameplate that the pole connection and vehicle fleet rarely realise. Mandatory sensitivities: S1 = 22 kW connectors on a shared 17.25 kW pole (realistic upper bound); S2 = 22 kW connectors with an unclipped/high station capacity (pessimistic hardware bound); S3 = a mixture distribution over {3.7, 7.4, 11, 22} kW reflecting the onboard-charger fleet.

### 2. Evidence table

| # | Source (link) | Section / locator | What it supports |
|---|---|---|---|
| 1 | ElaadNL, *Documentatie Laadprofielengenerator* (10 Nov 2025), https://charging.elaad.nl/assets/Documentatie%20Laadprofielengenerator.pdf | p.13 "Simulatie van de laadsessies"; p.10 "Parameters profile/simulate"; pp.5,7 | Public locations model two charge points sharing one pole/connection; documents `cp_capacity_kw` = "laadcapaciteit per laadpunt in kW"; lists API params; API up to 500 profiles, dashboard up to 100; distinct seeds required before aggregation. |
| 2 | ElaadNL Outlook Personenauto's Update 2024, https://elaad.nl/wp-content/uploads/downloads/ElaadNL_Outlook_Personenautos_2024_def.pdf | §on charge-point types | Home charge points "met een maximaal vermogen van 11 kW"; regular charging modelled at 11 kW; ~837,000 1-phase homes may need 3-phase upgrades. |
| 3 | HIER (citing ElaadNL prognoses), https://www.hier.nu/slim-stroomgebruik-in-buurt/elektrisch-rijden-wat-betekent-dat-voor-het-stroomnet-in-buurt | body | "ElaadNL rekent met een standaard laadvermogen van 11 kW voor thuis-, publieke- en werklaadpunten en 350 kW voor snellaadpunten"; regular charging spans 3.7–22 kW. |
| 4 | ElaadNL FlexPower3 report (2021–2022), https://elaad.nl/wp-content/uploads/2022/11/FlexPower-Rapport.pdf | Figure 9 caption | Poles with technical capacity 3×25 A ≈ 17.25 kW; under double occupancy each car gets 11 A × 3 phases (~7.6 kW). Corroborates `cs_capacity_kw = 17.25`. |
| 5 | NAL Smart Charging Requirements (SCR), https://elaad.nl/wp-content/uploads/downloads/smart-charging-requirements-uk-1.pdf | Module on charge-point capacity | Charge point "Maximum 22 kW (AC 3×32 A)" — nameplate connector ceiling. |
| 6 | Bollerslev et al., "Coincidence Factors for Domestic EV Charging from Driving and Plug-In Behavior," IEEE Trans. Transp. Electrif. 8(1):808–819, 2022, https://orbit.dtu.dk/en/publications/coincidence-factors-for-domestic-ev-charging-from-driving-and-plu/ | abstract/results | CF < 25% for >50 EVs at 11 kW; strongly depends on number of EVs; three-phase combined peak rises only 50% despite 3× power; battery size/driving minor. |
| 7 | Panda, Li & Tindemans (TU Delft), "Aggregate Peak EV Charging Demand: The Impact of Segmented Network Tariffs," arXiv 2403.12215v2, https://arxiv.org/pdf/2403.12215 | §II.A–B | ~300,000 transactions over 650 Dutch CSs in 2022; each CS provides up to 23 kW distributed among two CPs, each CP max 23 kW; aggregate-peak method across N=1…1024 CPs using 100 random CP selections; diversity factor normalised to single-CP 23 kW. |
| 8 | Holbert, "Estimating Upper-Tail Quantiles: Why Sample Size Matters," https://www.cfholbert.com/blog/quantiles-small-sample-sizes/ | body | Upper-tail (95th/99th) estimates are high-variance in small samples and need far larger n than the median. |
| 9 | SAS communities / bootstrap literature, https://communities.sas.com/t5/SAS-Programming/Calculating-bootstrapped-95-CI-for-99th-percentile-of-a-variable/td-p/931158 | body | Bootstrap gives poor estimates of the sampling distribution of extreme order statistics. |
| 10 | AC-limit charging guides (Besen/AMPERE POINT/joint), https://www.besen-group.com/what-is-the-ac-limit-for-ev-charging/ | body | Onboard charger is the binding AC limit; 11 kW is the practical standard, 22 kW rarely realised. |
| 11 | Wolterman et al., *Nationaal Laadonderzoek 2023* (RVO/ElaadNL), https://elaad.nl/wp-content/uploads/downloads/Nationaal_Laadonderzoek_2023_Rapport_def.pdf | authorship/methods | Authoritative Dutch survey of charging behaviour/practice (3,854 respondents). |
| 12 | NKL *Basisset AC* for public charging tenders, https://nklnederland.nl/basisset-ac-standaardisatie-voor-publieke-laadpalen/ | overview | Standardised DSO/NAL requirement set for public AC poles; netbewust laden standard on new poles. |
| 13 | arXiv 2409.01284 (Elaad/Elia/Fluvius uncertainty), https://arxiv.org/html/2409.01284v2 | §II | ElaadNL public-session dataset charging power spans 0–23 kW; seasonality/extreme-week identification methodology. |

### 3. Recommended library-size procedure and numerical stopping rule

**3.1 Which statistics determine adequacy.** For a distribution-grid reinforcement study the library must reproduce, within tolerance, the statistics that drive asset loading and overload risk:
- (a) **Mean annual energy** per profile (kWh) — smooth, converges fastest.
- (b) **Seasonal and time-of-day shape** — the monthly and 96-step average power curves.
- (c) **Upper 15-min load quantiles** of the *aggregated* node load: 95th, 99th, 99.9th percentiles.
- (d) **Coincidence/diversity factor** at representative aggregation sizes (N = 5, 20, 50, 100 connectors/EVs), since peak-per-connector falls with N (Bollerslev et al.: CF < 25% beyond 50 EVs at 11 kW).
- (e) **Overload-event results** where a transformer/cable rating is available: number of intervals above rating, and total overload energy.

**3.2 Distinguishing finite-library uncertainty from Monte Carlo sampling error.** Two distinct error sources must be reported separately:
- **Monte Carlo sampling error** — variance from bootstrapping a *fixed* library and aggregating; reducible by drawing more Monte Carlo scenarios. Quantify by repeating the aggregation many times from the same library and taking the spread.
- **Finite-library (representativeness) error** — bias/variance from the library containing only a finite number of *distinct* generated members. Bootstrapping cannot reduce this: reusing the same members repeatedly cannot manufacture unseen tail behaviour. Quantify it by *held-out* comparison between two disjoint halves of the library and by watching how target statistics drift as new *distinct* batches are added. This is the error the 1,000/200 heuristic ignores.

**3.3 Sequential batch-generation with held-out convergence test (the stopping rule).**
Because one API request returns up to 100 members under one batch seed (dashboard limit 100; API limit 500), generate in batches of 100 with distinct seeds per batch — the documentation explicitly warns that same-seed profiles share sessions and misrepresent coincidence when aggregated.

Procedure, run independently for home `ev` and public `cp`, for each prognosis year (2030, 2033, 2035):
1. Generate an initial library of **L = 500** members (5 batches). *(500 = a floor at which a 95th-percentile estimate has ≥ ~25 exceedances per profile-year and coincidence factors at N ≤ 50 are estimable with narrow CIs; below this, tail estimates are unstable.)*
2. Compute target statistics (a)–(e) on the cumulative library. For quantiles and coincidence factors, form **95% bootstrap confidence intervals** by resampling the library (B = 1,000 resamples).
3. Add one batch (+100 distinct members). Recompute.
4. **Convergence (stability) test** — stop when ALL of the following hold on two successive additions:
   - Relative change in **mean annual energy** ≤ **2%** *(a mean converges as 1/√L; 2% is well within typical demand-forecast uncertainty and cheap to achieve).*
   - Relative 95% bootstrap CI half-width of the aggregated **95th-percentile** 15-min load ≤ **5%**, of the **99th** ≤ **7%**, of the **99.9th** ≤ **12%** *(tolerances widen with rarity because tail-estimator variance grows; 12% at 99.9th reflects the genuine, irreducible difficulty of one-in-1,000-interval events and avoids demanding false precision).*
   - **Held-out test:** split the library into two random disjoint halves; the maximum absolute deviation between their load-duration curves, expressed as a fraction of aggregated peak, ≤ **3%** *(3% ≈ a fraction of a transformer thermal margin; deviations below this do not change a reinforcement verdict).*
   - Relative change in the **coincidence factor** at N = 20 and N = 50 ≤ **5%**.
   - If a rating is defined: change in the **overload-interval count** ≤ **5%** or ≤ 1 interval, whichever is larger.
5. **Minimum L = 1,000** regardless (guarantees ≥ ~350 intervals informing the 99th percentile per profile and stable N = 50 coincidence factors). **Maximum L = 5,000** as a compute cap; if convergence is not reached by 5,000, report the residual CI widths as an explicit limitation rather than continuing indefinitely.

**3.4 Recommended sizes and the verdict on 1,000/200.**

| Library | Initial | Minimum | Target | Maximum | Basis |
|---|---|---|---|---|---|
| Home `ev` | 500 | 1,000 | 2,000 | 5,000 | Home profiles are relatively homogeneous (one car, 11 kW, evening peak); tail and coincidence converge by low-thousands. |
| Public `cp` | 500 | 1,000 | 2,000 | 5,000 | Public CP profiles carry extra between-profile heterogeneity (car/van mix, occupancy, dual-socket pole sharing, morning+evening bimodality); this offsets the within-profile averaging, so convergence is *not* faster than home. |

**Verdict:** 1,000 home is defensible as a *minimum* but should be confirmed, not assumed, by §3.3; treat 1,000 as the floor and 2,000 as the target. **200 public cannot be defended** as a derived size and should be replaced: nothing in the ElaadNL model makes public convergence five times easier, and the tail/coincidence statistics that matter most for reinforcement converge no faster for public than for home. Use 200 only as an early checkpoint, not a stopping point.

### 4. Recommended public charging-capacity configuration and sensitivities

**Layered definitions (to avoid conflation):**
- **Connector/EVSE nameplate:** up to 22 kW (AC 3×32 A) per NAL SCR — a hardware ceiling.
- **Maximum per charge point (socket):** 22 kW nameplate, but effectively min(connector, vehicle OBC).
- **Actual vehicle charging power:** dominated by the onboard charger — most passenger EVs 11 kW three-phase or 7.4 kW single-phase; only a minority accept 22 kW AC.
- **Charging-station/pole connection:** commonly 3×25 A ≈ 17.25 kW in Dutch public practice (the generator's `cs_capacity_kw` default).
- **Two sockets on one pole:** share the pole connection; under double occupancy each socket is throttled (FlexPower: ~11 A × 3 ≈ 7.6 kW each). Note that TU Delft's Dutch dataset analysis (arXiv 2403.12215) normalises the single-CP network-capacity requirement to 23 kW per CP, so 22–23 kW is a real *provisioning* figure at CP level even though delivered per-socket power under sharing is lower.
- **Load seen by the distribution grid:** the pole-level draw, bounded by `cs_capacity_kw` and the number of simultaneously active sockets — NOT the connector nameplate.

**Primary configuration:** per-connector `cp_capacity_kw = 11` kW with the generator's native two-socket pole sharing retained (`cs_capacity_kw` ≈ 17.25 kW). This is the value best supported by (i) ElaadNL's own Outlook convention, (ii) the dominant onboard-charger limit, and (iii) the shared 3×25 A pole connection.

**Why not 22 kW as primary:** 22 kW is a nameplate that is rarely realised — the pole cannot deliver 2×22 kW on 3×25 A, and few cars accept 22 kW AC. Using it as the single value overstates grid load and would drive over-reinforcement, violating the principle of not choosing a value merely because it "produces useful congestion."

**Mandatory sensitivities:**
- **S1 (realistic upper):** `cp_capacity_kw = 22`, `cs_capacity_kw = 17.25` — nameplate connectors on a shared pole; shows the ceiling the current draft *intended* while respecting the shared connection.
- **S2 (pessimistic hardware bound):** `cp_capacity_kw = 22` with a high/unclipped `cs_capacity_kw` — the worst-case, used only to bracket.
- **S3 (fleet mixture):** draw per-connector capacity from a distribution over {3.7, 7.4, 11, 22} kW reflecting the onboard-charger fleet; report as the most physically faithful case.

### 5. Mapping to ElaadNL API parameters

Endpoint: `POST https://api.charging.data.elaad.nl/profile/simulate`

Common (all cases):
```
"start_datetime": "2030-01-01T00:00:00+01:00",
"stop_datetime":  "2031-01-01T00:00:00+01:00",
"step_size_s": 900,
"timezone": "CET",
"simulated_year": 2030,        // repeat for 2033, 2035
"n_profiles": 100,              // batch size; loop with distinct seeds to reach L
"seed": <distinct per batch>
```
Home library:
```
"profile_type": "ev",
"location_type": "home",
"vehicle_types": "car",
"cp_capacity_kw": 11
```
Public library (primary):
```
"profile_type": "cp",
"location_type": "public",
"vehicle_types": ["van", "car"],   // generator handles the mix automatically
"cp_capacity_kw": 11,
"cs_capacity_kw": 17.25            // retain pole-sharing (verify it is a settable input; see §6)
```
Public sensitivities: S1 `cp_capacity_kw:22, cs_capacity_kw:17.25`; S2 `cp_capacity_kw:22, cs_capacity_kw:<high>`; S3 loop `cp_capacity_kw` over the mixture.

Notes: profiles that will be aggregated must use **distinct seeds** (documentation: same-seed profiles share sessions and misrepresent coincidence). Each member is identified as (batch seed, returned index). The parameter table in the documentation PDF lists `start_datetime, stop_datetime, step_size_s, timezone, simulated_year, profile_type, n_profiles, location_type, vehicle_types, cp_capacity_kw, seed`; `cs_capacity_kw` is **not** in that table (see §6/§7).

### 6. Minimal API diagnostic experiment (reproducible)

**Goal:** determine whether `cs_capacity_kw = 17.25` clips public profiles generated with `cp_capacity_kw = 22`.

1. Fix a set of K = 100 seeds S = {s₁…s₁₀₀}.
2. **Run A (clipped):** for each sᵢ, POST public/cp, `cp_capacity_kw = 22`, `cs_capacity_kw = 17.25`, one batch of 100, `simulated_year = 2030`, full-year, `step_size_s = 900`.
3. **Run B (unclipped):** identical requests, identical seeds, only `cs_capacity_kw` raised to a value ≥ 2×22 = 44 (or the maximum accepted) so the pole cannot bind.
4. **Paired comparison** per profile and aggregated:
   - Max 15-min power (kW): expect Run A ≤ Run B if clipping occurs.
   - Count of intervals ≥ {11, 17.25, 22, 30} kW.
   - Total annual energy (kWh): if clipping only reshapes timing, energy should be nearly equal; a drop signals demand not served within sessions.
   - Load-duration curves overlaid; quantify the gap at the top 0.1%/1%/5%.
5. **Decision:** if Run A caps at ~17.25 kW per pole (or ~7.6 kW per socket under double occupancy) while Run B reaches ~22 kW, the station connection is the binding constraint and `cs_capacity_kw` — not `cp_capacity_kw` — is the parameter that determines grid load. If A and B are identical, `cs_capacity_kw` is inert for this location/version and the pole-sharing is governed elsewhere (document accordingly).
6. **Also verify schema:** query the live OpenAPI at `https://api.charging.data.elaad.nl/docs` / `openapi.json` to confirm `cs_capacity_kw` is an accepted *input* (vs. only a response-`config` field) and its default; if it is not settable, the diagnostic reduces to confirming the fixed pole behaviour and the 22 kW request must be interpreted as a per-connector cap only. (The `ElaadNL/ls-profielen-model` GitHub repository is the best lead for the underlying request-model defaults if the live schema cannot be reached.)

### 7. Remaining uncertainties and limitations
- The live machine-readable OpenAPI schema could not be retrieved (the FastAPI Swagger UI is JS-rendered and `openapi.json` was not directly fetchable). `cs_capacity_kw` is **not** listed in the documentation PDF parameter table; its status as a settable input, and its 17.25 kW default, are **inferred** from the FlexPower report (3×25 A ≈ 17.25 kW pole behaviour) and the documented two-socket shared-pole model, not confirmed from the schema. §6 step 6 resolves this empirically.
- The generator assigns public CP profiles the *expected average* energy demand per charge point (documentation p.12); real between-CP annual-energy variance may be larger, so the library may understate true public heterogeneity — an argument for the larger public library, not the smaller.
- 2030–2035 onboard-charger fleet shares (how many EVs accept 22 kW AC) are uncertain; the mixture S3 is a modelling assumption, not observed 2030 practice.
- Bootstrap CIs for the 99.9th percentile are themselves imprecise (extreme order statistics); the 12% tolerance acknowledges this and should be reported, not hidden.
- Smart/netbewust charging (now standard on new public poles per NKL Basisset AC / NAL) will reshape public peaks; the regular-charging library is a conservative upper case unless a smart-charging option is explicitly generated.

### 8. Manuscript-ready Methods paragraph
> Annual 15-minute charging profiles were generated with the ElaadNL Laadprofielengenerator (API `profile/simulate`, documentation v. 10 Nov 2025) for prognosis years 2030, 2033 and 2035, separately for home passenger-car demand (`profile_type=ev`, `location_type=home`, `vehicle_types=car`) and public charge points (`profile_type=cp`, `location_type=public`, `vehicle_types=[van,car]`). Home charging capacity was set to 11 kW, consistent with the ElaadNL Outlook convention (a standard 11 kW for home, public and workplace charging) and the maximum rating of Dutch home charge points. For public charging we adopted a station-level representation: a per-connector capacity of 11 kW — reflecting the dominant passenger-EV onboard-charger limit and ElaadNL's standard regular-charging power — combined with the generator's native two-socket pole model in which both connectors share one grid connection (`cs_capacity_kw ≈ 17.25` kW, i.e. a 3×25 A, 230 V connection), so that the load presented to the distribution grid is the pole draw rather than the connector nameplate. Because a 22 kW connector nameplate is rarely realised (the pole connection and vehicle onboard chargers bind first), 22 kW was retained only as a sensitivity together with a fleet-mixture case over {3.7, 7.4, 11, 22} kW. Library sizes were not fixed a priori: profiles were generated in batches of 100 with distinct random seeds and accumulated until grid-relevant statistics converged under a held-out criterion — relative change in mean annual energy ≤ 2%, relative 95% bootstrap CI half-widths of the aggregated 95th/99th/99.9th 15-min load quantiles ≤ 5/7/12%, ≤ 3% maximum load-duration-curve deviation between disjoint library halves, and ≤ 5% change in coincidence factors at 20 and 50 aggregated units — with a minimum of 1,000 and a cap of 5,000 members per library and year. Monte Carlo sampling error (from bootstrapping a fixed library) was reported separately from finite-library representativeness error (from the number of distinct generated members), the latter assessed by held-out comparison. Members were identified by (batch seed, returned profile index) and only distinct-seed members were aggregated, avoiding the shared-session bias flagged in the generator documentation.

### 9. Draft decision-register text — "EV-003 — ElaadNL profile-library size and public charging capacity"
> **EV-003 — ElaadNL profile-library size and public charging capacity.**
> **Status:** Decided (pending §6 API diagnostic and per-year convergence run).
> **Decision 1 (library size):** The fixed 1,000 home / 200 public profile counts are rescinded as derived sample sizes and retained only as generation caps. Library sizes are determined independently for home and public, per prognosis year, by sequential batch generation (batches of 100, distinct seeds) with a held-out convergence test on annual energy, seasonal/time-of-day shape, 95th/99th/99.9th 15-min load quantiles, coincidence factors at N = 20/50, and overload-interval counts. Minimum 1,000; target 2,000; maximum 5,000 per library. The public library is sized by the same criterion as the home library and is not assumed smaller.
> **Decision 2 (public capacity):** Primary per-connector `cp_capacity_kw = 11` kW with the generator's two-socket shared-pole connection (`cs_capacity_kw ≈ 17.25` kW). Mandatory sensitivities: 22 kW on a shared pole (S1), 22 kW unclipped (S2), and a {3.7/7.4/11/22} kW fleet mixture (S3). A bare 22 kW single value is rejected as unrepresentative of grid-observed load.
> **Rationale:** ElaadNL Outlook uses 11 kW for home/public/work; most onboard chargers cap at 11 kW AC; the public pole shares a ~17.25 kW connection; tail and coincidence statistics converge no faster for public than for home.
> **Verification:** paired identical-seed API runs varying only `cs_capacity_kw`; confirm `cs_capacity_kw` is a settable input via the live OpenAPI schema.
> **Review trigger:** ElaadNL generator update (~summer 2026), or new onboard-charger fleet data, or a change in DSO overload rating that the ≤ 3% held-out tolerance would flip.

## Recommendations
1. **Immediately reclassify 1,000/200 as caps, not targets**, and implement the §3.3 stopping rule; run it per year for both libraries. Benchmark that changes the plan: if convergence is reached below 1,000 for home, keep the 1,000 floor; if public has not converged by 2,000, continue to 5,000 and report residual CI widths.
2. **Set public primary `cp_capacity_kw = 11` kW with pole-sharing retained**; always run sensitivities S1–S3. Threshold: if the §6 diagnostic shows `cs_capacity_kw` does not clip, escalate the interpretation of the 22 kW case and rely on S3 as the physically faithful base.
3. **Run the §6 API diagnostic first**, before committing compute to full libraries, so the meaning of `cp_capacity_kw` vs `cs_capacity_kw` is settled and profiles are generated with the correct capacity semantics.
4. **Report Monte Carlo and finite-library errors separately** in the study, and state the 99.9th-percentile CI width as an explicit limitation.
5. **Re-evaluate on the ~summer-2026 generator update**, which may change model conventions and defaults.

## Caveats
- Recommendations assume the reinforcement verdict is sensitive to upper-tail 15-min loads and coincidence at modest aggregation; if only annual energy matters, far smaller libraries suffice (mean converges fast) — but that is not typical for MV reinforcement.
- `cs_capacity_kw` settability and default are inferred, not schema-confirmed; §6 resolves this.
- 11 kW primary is a *present-convention + fleet* argument; if the local study population is dominated by 22 kW-capable vehicles or vans, weight S3/S1 more heavily.
- All 2030–2035 values are prognosis assumptions from ElaadNL Outlooks, not observations.
