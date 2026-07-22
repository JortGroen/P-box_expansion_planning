# E2.S2 EV-To-IC-1 Adapter Guardrails

Task: E2.S2 EV model readiness for later IC-1 integration  
Status: adapter/preflight guardrail only  
Machine-readable packet: `data/metadata/ev_adoption/e2_s2_ev_ic1_adapter_guardrails.json`

## Purpose

This packet is the next safe step after the EV integration-readiness artifact.
It turns the handoff into checks that a future Agent A IC-1 EV adapter can run
before loading generated profile arrays. It does not open held-out adequacy
batches, sample EV demand for scientific results, aggregate net load, evaluate
thresholds, estimate `P(E)`, or claim that the finite EV libraries are
sufficient.

## Candidate Checksum Expectations

The guardrail helper derives expected processed-file SHA-256 values from:

`data/metadata/ev_adoption/e2_s2_ev_integration_readiness.json`

It accepts only candidate processed-profile paths. Raw API responses, held-out
batches, and quarantined diagnostic batches are excluded from this adapter
preflight. A consuming worktree must verify the local candidate file bytes
against the committed expectations before loading any NPZ arrays.

Expected candidate processed files:

| Component | Candidate members | Candidate files |
|---|---:|---:|
| `ev_home` | 1,000 | 10 |
| `ev_public` | 1,200 | 12 |

Checksum verification is intentionally a pre-load guardrail. The helper reads
file bytes to compute SHA-256 but does not parse profile arrays, inspect
behavioral summaries, or touch held-out adequacy profiles.

## Planning-Year Calendar Mapping

The EV source profiles remain on the ElaadNL 2025 local generator calendar:

- timezone: `Europe/Amsterdam`;
- cadence: 900 seconds;
- timestep count: 35,040;
- first local timestamp: `2025-01-01T00:00:00+01:00`;
- future IC-1 target planning year: 2035, per G0-A4.

Before IC-1 aggregation, complete selected EV source members must be mapped to
the common 2035 planning-year calendar by an approved deterministic mapping.
This packet records that requirement and blocks premature profile loading into
IC-1, but it does not choose or implement the mapping algorithm.

## Future Adapter Preflight

A future Agent A EV adapter should:

1. load the EV readiness artifact;
2. derive candidate-only checksum expectations;
3. verify local processed-file SHA-256 values in the consuming worktree;
4. construct the approved planning-year calendar mapping;
5. only then load candidate profile arrays for RNG-001 component-stream
   sampling and IC-1 aggregation.

The selected EV member IDs must remain traceable as
`(component_id, library_id, batch seed, returned profile index)` and later be
recorded with the RNG-001 stream identity in manifests.

## Explicit Non-Claims

- No held-out EV batches were opened or used.
- No candidate profile arrays were opened for this packet.
- No source-library adequacy conclusion was made.
- No within-realization replacement rule was chosen.
- No net-load, congestion, event, `P(E)`, or manuscript-result analysis was
  performed.

## Verification

`tests/test_ev_model.py` now covers:

- candidate-only checksum expectation derivation;
- synthetic local checksum verification without network or profile loading;
- rejection of held-out-like processed paths in the preflight;
- blocking 2035 planning-year calendar assumptions;
- committed guardrail packet counts and policy flags.

