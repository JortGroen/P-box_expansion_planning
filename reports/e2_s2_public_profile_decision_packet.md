# E2.S2 Public-Charging EV Profile Decision Packet

Status: proposed packet only; no public ElaadNL API call was made.

## Why This Exists

EV-004 fixed the primary residential home charge-point profile library, but it
explicitly left public charging as a separate profile class. EV-007/A-014 now
provide proposed local public charge-point counts and a second-stage nodal
allocation rule, so executable EV adoption scenarios still need a public
behavior-library decision before they can combine home and public charging.

This packet proposes a Set B public-profile protocol for PI review. It does not
download, generate, inspect, or analyze public profiles.

## Documentation Evidence Consulted

Local source consulted read-only: `data/raw/elaadnl/Documentatie Laadprofielengenerator.pdf`
in the PI checkout. The PDF is ignored and was not copied or committed.

Relevant documentation facts:

| Topic | Evidence |
|---|---|
| Version | Document title page: ElaadNL `Documentatie Laadprofielengenerator`, 10 November 2025. |
| Interfaces and limits | Dashboard supports up to 100 profiles per run; API supports up to 500 profiles per batch, with large runs taking minutes (pp. 5, 7). |
| Public profile availability | Public (`public`) is a supported location type; `cp` and `ev` profile types are supported (pp. 5-6, 10). |
| Public native vehicle mix | At public locations, cars and vans charge; for CP profiles the mix is included automatically and individual shares cannot be chosen (pp. 5-6, 10). |
| Unit semantics | A `cp` profile simulates a charge point at a location used by different EVs (p. 5). |
| Public pole convention | For public locations, the simulation assumes two charge points share one pole connection, affecting simultaneous maximum power (p. 13). |
| Seed warning | Same-seed simulations preserve annual mileage, energy demand, and sessions and must not be summed as independent profiles; distinct seeds are required for profiles later aggregated as separate chargers (pp. 6-7). |
| Model basis | Current generator version is based mainly on Outlook Personenauto's 2024 and Outlook Logistiek 2025; public car energy uses the Outlook Laadprofielen 2023 mix, and CP energy divides expected energy demand by forecast charge-point counts per location type (pp. 4, 11-13). |
| Smart charging | Smart charging is available as dashboard/API functionality but shifts unmet in-session demand and is an impact-analysis starting point; V2G is not part of the generator (pp. 6, 14). |

## Proposed Set B Generator Settings

Recommended PI decision: create a separate uncontrolled public charge-point
library with these settings.

| Field | Proposed value |
|---|---|
| Set name | Set B - public CP library |
| API endpoint | `POST https://api.charging.data.elaad.nl/profile/simulate` |
| Profile type | `cp` |
| Location type | `public` |
| Vehicle types | `["van", "car"]`, retaining the generator's native public car/van mix |
| Capacity | `cp_capacity_kw = 22` proposed, not signed |
| Calendar | `2025-01-01T00:00:00+01:00` to `2026-01-01T00:00:00+01:00` |
| Step size | `900` seconds, 15 minutes |
| Timezone request | `CET`; returned datetimes must still be treated as UTC and converted to Europe/Amsterdam as in Set A |
| Simulated year | `2030` |
| Smart charging | Disabled/uncontrolled only |
| Profiles per batch | 100 |
| Candidate library | `M = 1000`, seeds `150001, 150101, ..., 150901` |
| Held-out library | `H = 200`, seeds `151201`, `151301` |
| Storage if later approved | raw gzip under ignored `data/raw/elaad_profiles/`; processed NPZ under ignored `data/processed/elaad_profiles/`; committed manifests/checksums under `data/metadata/elaad_profiles/` |

First proposed request body:

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

## Recommendation On The 22 kW Issue

Recommend 22 kW as the proposed public AC charge-point capacity for PI review,
not as an approved scientific value. This is defensible because the generator
parameter is explicitly `cp_capacity_kw`, public CP profiles are charge-point
profiles, and the local Outlook values being proposed for E2.S6 are public
charge-point counts rather than vehicle counts.

The unresolved part is the relation between charge points and poles. The
documentation says public locations assume two charge points sharing one pole
connection. Therefore a generated member should not be relabelled as a pole.
If the local public counts are actually poles, connectors, or another unit, the
PI should either convert them to charge points before sampling or amend Set B
before any generation. The safest approval wording is: 22 kW per public charge
point, with two generated public charge points corresponding to one pole
connection where pole-level asset accounting is required.

## Later Sampling Under EV-003 And EV-005

If EV-008 is signed and the library is generated, public profiles should be
sampled like home profiles: complete annual archived members are selected by
the project seed tree and recorded by `(batch_seed, returned_profile_index,
location_class = public, control_mode = uncontrolled)`. The Monte Carlo layer
must not call the API.

Finite-library uncertainty remains separate from Monte Carlo uncertainty:

- `M_public` is the size of the frozen public source library.
- `K_public,r` is the local scenario's public charge-point count allocated to
  node `r`.
- `N` is the whole-system Monte Carlo count.
- `K_public * N` is a number of selections, not a unique-profile requirement.

Candidate, nested, disjoint, leave-one-batch-out, and held-out public views
should mirror the Set A home-library protocol. Held-out public profiles must
remain unopened until E3.S2a freezes the downstream adequacy criterion. Historical note: the within-realization replacement rule was later resolved by EV-005B for candidate member-selection implementation only. It still must not be inferred from this public-profile packet, and EV-005B does not certify library adequacy, open held-out data, or authorize integrated analysis.

## Future Long-Run Notice Template

```text
LONG-RUN NOTICE
Task: E2.S2 public Set B generation under proposed EV-008
Process: run data/get_elaad_profiles.py for public uncontrolled batches B_public_vancar_cp_y2030 seeds 150001-150901 and 151201-151301, 100 profiles per batch
Estimated wall time: <pilot runtime per batch> x 12 batches plus conversion/checksum overhead; send this notice if the estimate exceeds about 15 minutes
Resource impact: network API calls, local gzip/NPZ writes under ignored data/raw and data/processed paths, CPU for validation and checksums
Checkpoint plan: one durable batch manifest per seed under data/metadata/elaad_profiles; raw gzip and processed NPZ checksums recorded after each successful batch; completed seeds are validated before the next request
Resume procedure: rerun the same command/config; the script must validate existing request/config/checksums for completed seeds, skip verified seeds, retry only the next incomplete seed with the identical JSON body, and never register a retry as a duplicate batch
```

## PI Decisions Needed Before Generation

1. Approve or amend EV-008's public profile class: `cp`, `public`, native
   `["van", "car"]`, uncontrolled, fixed `simulated_year = 2030`.
2. Approve or amend `cp_capacity_kw = 22`, including the charge-point versus
   pole convention.
3. Confirm that the E2.S6 local public counts are charge-point counts compatible
   with generated public `cp` members, or provide a conversion rule.
4. Approve or amend candidate `M = 1000`, held-out `H = 200`, 100-profile batch
   size, and seed ranges.
5. Confirm that public smart charging is not part of Set B.

## What Was Not Done

- No public API request was made.
- No public raw response, profile library, processed NPZ, or behavioral summary
  was produced.
- No EV held-out batch was opened.
- No integrated net-load, congestion, event, adequacy, `P(E)`, or manuscript
  result was produced.
