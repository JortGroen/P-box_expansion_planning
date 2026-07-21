# E2.S2 EV-008 Public Profile Amendment Packet

Status: proposed PI decision packet only. No ElaadNL public API call was made,
no public profile was generated, no EV held-out batch was opened, and no
integrated net-load, congestion, adequacy, event, `P(E)`, or manuscript-result
analysis was run.

## Why This Exists

EV-008 currently proposes one uncontrolled ElaadNL public Set B profile library
with `cp_capacity_kw = 22`. The later NDW/DOT-NL Alkmaar packet (D-012) supports
the profile unit as one charge-point/EVSE/connector-like member rather than one
pole, but it weakens the claim that 22 kW is the unique representative current
Alkmaar public-charging capacity.

This packet compares the two remaining PI choices:

1. keep 22 kW as a signed future/upper-capacity convention; or
2. amend EV-008 to a capacity-stratified public Set B design.

Both options keep EV-003/EV-005 discipline: finite source-library size `M` is
separate from Monte Carlo count `N`, candidate and held-out seeds are disjoint,
member identities remain traceable, and `M = 1000` is not declared sufficient
until downstream E3.S2a adequacy criteria are frozen and passed.

## Shared Generator Settings

| Field | Setting |
|---|---|
| API endpoint | `POST https://api.charging.data.elaad.nl/profile/simulate` |
| Profile type | `cp` |
| Location type | `public` |
| Vehicle types | `["van", "car"]`, retaining the generator's native public car/van mix |
| Simulated year | `2030` |
| Calendar | `2025-01-01T00:00:00+01:00` to `2026-01-01T00:00:00+01:00` |
| Step size | `900` seconds |
| Timezone request | `CET`; returned datetimes must be handled with the same UTC-to-Europe/Amsterdam conversion used for Set A |
| Smart charging | Disabled/uncontrolled only |
| Raw storage if later approved | ignored `data/raw/elaad_profiles/` |
| Processed storage if later approved | ignored `data/processed/elaad_profiles/` |
| Committed storage if later approved | request configs, checksums, manifests, and structural reports under `data/metadata/elaad_profiles/` |

## Option 1 - Keep 22 kW As A Signed Future Convention

This option keeps EV-008 essentially as written, but the approval wording must
say that 22 kW is a deliberate public AC future/upper-capacity convention, not a
claim that 22 kW uniquely represents the current Alkmaar fleet.

Exact first request body:

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
  "cp_capacity_kw": 22,
  "seed": 150001
}
```

| Partition | Seeds | Profiles per call | Members |
|---|---|---:|---:|
| Candidate | `150001, 150101, ..., 150901` | 100 | 1,000 |
| Held-out | `151201`, `151301` | 100 | 200 |

Expected API calls: 12 total, comprising 10 candidate calls and 2 held-out
calls. Each 100-profile batch is a durable checkpoint. A retry uses the exact
same JSON body and is accepted only if any existing raw/processed artifacts and
manifest match that seed, request configuration, and checksums.

Member identity: each member is identified as
`B_public_22kw_uncontrolled_y2030_seed{batch_seed}_idx{returned_index}` plus the
request checksum, raw JSON checksum, raw gzip checksum, processed checksum, and
control mode. The identity does not imply that a batch seed creates 100
independent per-profile seeds.

Later aggregation implication: every local public charge point allocated by
A-014 draws from one public 22 kW source class. The public power class therefore
does not carry current-fleet heterogeneity; the paper/report must describe it
as a signed upper-capacity or future-capacity convention.

## Option 2 - Replace EV-008 With Capacity-Stratified Set B

This option keeps the same public `cp` unit and uncontrolled 2030 behavior
source, but replaces the one-capacity library with four public capacity classes
motivated by D-012's current Alkmaar evidence: 11 kW-ish, 13 kW, 15 kW, and
22 kW-ish AC charging. DC/fast charging remains out of this Set B proposal
unless the PI signs a separate fast-charging class.

| Class | `cp_capacity_kw` | Candidate members | Candidate seeds | Held-out members | Held-out seed |
|---|---:|---:|---|---:|---|
| `public_11kw` | 11 | 300 | `152001`, `152101`, `152201` | 50 | `153201` |
| `public_13kw` | 13 | 300 | `152301`, `152401`, `152501` | 50 | `153301` |
| `public_15kw` | 15 | 200 | `152601`, `152701` | 50 | `153401` |
| `public_22kw` | 22 | 200 | `152801`, `152901` | 50 | `153501` |

Candidate request bodies use `n_profiles = 100`. Held-out request bodies use
`n_profiles = 50`; the API has already accepted `n_profiles = 1` and
`n_profiles = 100`, but the PI may instead require 100-profile held-out calls
per class, which would increase held-out size from 200 to 400.

Exact first candidate request body:

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

Exact first held-out request body:

```json
{
  "start_datetime": "2025-01-01T00:00:00+01:00",
  "stop_datetime": "2026-01-01T00:00:00+01:00",
  "step_size_s": 900,
  "timezone": "CET",
  "simulated_year": 2030,
  "profile_type": "cp",
  "n_profiles": 50,
  "vehicle_types": ["van", "car"],
  "location_type": "public",
  "cp_capacity_kw": 11,
  "seed": 153201
}
```

Expected API calls under the 200-member held-out design: 14 total, comprising
10 candidate calls and 4 held-out calls. If the PI requires 100-profile
held-out checkpoints for every capacity class, the call count is still 14 but
the held-out library becomes `H = 400` rather than `H = 200`.

Member identity: each member is identified as
`B_{capacity_class}_uncontrolled_y2030_seed{batch_seed}_idx{returned_index}`,
with capacity class, `cp_capacity_kw`, partition, request checksum, raw JSON
checksum, raw gzip checksum, processed checksum, and control mode recorded.

Later aggregation implication: public `K_public,r` must be split into capacity
classes before profile sampling. The capacity split should be PI-signed and
kept separate from A-014's node allocation. A-014 can still distribute total
public charge points across load nodes, but aggregation then draws the node's
assigned 11/13/15/22 kW counts from the matching source class.

## Recommendation

Recommend Option 2: amend EV-008 to a capacity-stratified public Set B design.

The reason is not that 22 kW is wrong. The reason is that D-012 makes it hard
to defend 22 kW as the only current Alkmaar public capacity without adding a
strong convention. A capacity-stratified Set B keeps the same ElaadNL public
`cp` route, same profile unit, same fixed 2030 behavior-year discipline, and
same finite-library governance, while turning the NDW evidence into an
auditable modeling distinction. The extra operational burden is modest: 14
planned calls instead of 12 if held-out remains `H = 200`.

If the PI prefers Option 1, the decision should explicitly say: "22 kW is a
signed future/upper-capacity convention for public AC charge points and is not
claimed to be the unique current Alkmaar representative capacity."

## Checkpoint And Resume Requirements

For either option, generation must be per-seed checkpointed:

- write one manifest per requested seed before moving to the next seed;
- record the normalized request JSON and checksum in the manifest;
- keep raw gzip and processed NPZ outputs under ignored paths;
- record raw gzip, uncompressed JSON, and processed-output checksums;
- reject recovery if the saved response config does not match the normalized
  request config, seed, capacity, location type, profile type, calendar, or
  control mode;
- skip a completed seed only when all expected checksums match;
- never turn a retry of the same seed/request into a duplicate batch.

## Long-Run Notice Template

```text
LONG-RUN NOTICE
Task: E2.S2 public Set B generation after EV-008 amendment/approval
Process: run data/get_elaad_profiles.py for the PI-approved public Set B seed plan, one checkpointed API request per seed
Estimated wall time: <pilot runtime per batch> x <number of batches> plus checksum/conversion overhead; send this notice before launch if the estimate exceeds about 15 minutes
Resource impact: network API calls to ElaadNL, local gzip writes under ignored data/raw/elaad_profiles, local NPZ writes under ignored data/processed/elaad_profiles, CPU for validation/checksums
Checkpoint plan: one durable manifest per seed under data/metadata/elaad_profiles; raw gzip and processed NPZ checksums recorded after each successful batch; completed seeds validated before the next request
Resume procedure: rerun the same command/config; the script validates existing request/config/checksums for completed seeds, skips verified seeds, retries only the next incomplete seed with the identical JSON body, and never registers a retry as a duplicate batch
```

## PI Decision Needed

Choose exactly one before public profile generation:

- **Option 1:** approve EV-008 as a 22 kW future/upper-capacity convention with
  12 API calls, `M = 1000`, `H = 200`, and seed plan `150001`-`150901`,
  `151201`, `151301`.
- **Option 2:** amend EV-008 to the capacity-stratified design with 14 planned
  API calls, candidate `M = 1000`, held-out `H = 200` if 50-profile held-out
  calls are accepted, and seed plan `152001`-`152901`, `153201`-`153501`.

Public smart charging, DC/fast charging, held-out adequacy use, integrated
event analysis, and any claim that `M = 1000` is sufficient remain outside this
decision packet.
