# E3.S2a Integrated Library Adequacy Design Support

Task: E3.S2a support packet for Agent C-owned integrated library adequacy.

Status: scaffold/design support only. This packet defines the information and
preconditions A/C need before opening EV-005 held-out data. It does not open
held-out batches, wire real E2 components, run IC-2 event detection, evaluate
thresholds, compute `P(E)`, or produce manuscript results. Q-5 is resolved
by G0-A3, but integrated event-based adequacy still requires the remaining gates, accepted inputs, and frozen adequacy criterion.

## Purpose

E3.S2a tests whether the finite EV profile library is adequate for the
downstream transformer quantity after baseline, EV, HP, PV, adoption, and
flexibility are assembled into net load and evaluated through IC-2. Per
ALEA-002, component-level profile statistics are diagnostics only; the adequacy
comparison must be made downstream of the aggregated IC-1 result.

This support packet turns the existing IC-1, IC-2, RNG, and EV governance into
a pre-held-out checklist. It is intentionally procedural: it says what must be
frozen and manifested before Agent C opens the held-out EV batches, while
leaving the unresolved scientific choices to the PI.

## Blocking Boundary

G0-A3 resolves Q-5: event-based E3.S2a work must use the strict
`L_import > 1.0 p.u.` four-step primary threshold with the predeclared `1.1`
and `1.2 p.u.` persistent sensitivities. Q-5 itself is no longer a blocker.

E3.S2a remains blocked until the downstream aggregate adequacy criterion is
PI-signed, Agent A IC-1/IC-2 assembly is accepted, A-016 scenario consistency is
resolved, the final 2035 low/middle/high branch is selected or explicitly
branched in a signed run design, candidate component-output checksums verify in
the consuming worktree, and held-out access is explicitly invoked under that
signed route. Until then:

- no held-out event result should be opened;
- no threshold exceedance, episode count, or `P(E)` should be reported as an
  adequacy result;
- no E3.S2a event metric should be tuned or selected using held-out outcomes;
- no manuscript result should be produced from an integrated event run.

Non-event scaffolding may continue. Valid work before the remaining prerequisites
are resolved includes schema checks, synthetic harnesses, candidate-only dry-run
mechanics, manifest template review, checksum-preflight automation, and
provenance validation. Candidate-only diagnostics must stay labeled as
diagnostics and must not be used to certify adequacy.

## Required Inputs Before Held-Out Access
Before opening fresh held-out EV data, A/C should have the following frozen in
version-controlled configuration and runner code:

| Area | Required input | Notes |
|---|---|---|
| IC-1 assembly | `NetLoadProvider.get_net_load(scenario, year, time_domain, rho, seed)` implementation that returns a validated `NetLoadResult` | Public signature stays fixed; real adapters operate behind the merged IC-1 boundary. |
| Component adapters | Baseline, EV, HP, PV, adoption, and flexibility adapters emitting validated `ComponentAdapterOutput` objects | Synthetic adapters are already scaffolded; real E2 adapters must retain source/member provenance. |
| Calendar | One common 900-second calendar for all components in a realization | Required by ALEA-001 and by the G0-A3 four-step one-hour event interpretation. |
| Node mapping | Versioned IC-1 node IDs and component-to-node allocation metadata | Needed to prevent candidate/held-out differences from being caused by mapping drift. |
| Weather identity | One shared HP/PV weather-driver identity per realization | The implementation path remains governed by Q-8 or a later PI-approved weather decision. |
| EV libraries | Candidate and held-out EV source batches with disjoint provenance, checksums, seeds, and member IDs | EV-005 keeps finite-library uncertainty separate from Monte Carlo uncertainty. |
| Adoption | Signed scenario, planning year, local count, and node-allocation metadata | EV within-realization replacement is approved by EV-005B for candidate member selection only; held-out adequacy and M-sufficiency remain separate. |
| Flexibility | Declared `rho` branch and flexibility-adapter provenance | FLEX-001 remains proposed unless separately approved by the PI. |
| IC-2 trajectory | Validated `LoadingTrajectoryResult` output contract, not a legacy boolean only | IC-3 and adequacy comparisons must be able to recompute G0-A3 events from trajectories. |
| Criterion | Predeclared downstream adequacy tolerance and comparison metric | Event-based criteria must use G0-A3 semantics and require PI-signed tolerances before held-out opening. |

## IC-1 Data Contract For Adequacy

Each Monte Carlo sample should produce one IC-1 `NetLoadResult` with:

- complete `p_net_kw` and `q_net_kvar` arrays on the common 15-minute calendar;
- stable `node_ids` matching the versioned assembly plan;
- `component_provenance` entries for baseline, EV, HP, PV, adoption, and
  flexibility;
- `metadata["realization_context"]` containing scenario, planning year,
  `time_domain`, `rho`, root/sample seed identity, component streams,
  calendar metadata, mapping-version metadata, member-selection placeholders,
  and the shared weather-driver ID;
- component source/member IDs sufficient to distinguish candidate, held-out,
  quarantined diagnostic, and synthetic fixture data.

The IC-1 result must preserve complete trajectories. It should not pass
component-level percentiles, EV-only sustained-load metrics, or summarized
profile statistics to adequacy as substitutes for the downstream transformer
quantity.

## IC-2 Data Contract For Adequacy

IC-2 should consume the aggregate IC-1 trajectories and emit a validated
`LoadingTrajectoryResult` with:

- `p_net_kw`, `q_net_kvar`, `s_net_kva`, screening loading, import loading,
  export loading, and direction masks;
- masks derived exactly from the unwidened sign of `P_net`;
- finite, nonnegative screening loading and internally consistent import/export
  diagnostic trajectories;
- `time_domain` and `primary_probability_domain` flags that agree;
- timestep cadence, threshold metadata, persistence metadata, and transformer
  denominator/capacity-convention provenance.

For E3.S2a, this trajectory object is the boundary to downstream adequacy. G0-A3 event quantities can be recomputed from the validated trajectories without relying on a stale boolean overload result.

## CRN Structure

Adequacy comparisons should use common random numbers for paired branches while
keeping physical dependence explicit:

- one root seed creates the sample identity through RNG-001;
- sample and component streams are derived from the seed tree and manifested;
- alpha, endpoint, and treatment labels do not change aleatory identity;
- candidate-library variants and held-out-library variants use analogous sample
  indices and component roles, but candidate and held-out source batches remain
  disjoint;
- HP and PV share a physical weather-driver ID inside one realization;
- CRN reuse does not replace the physical shared-driver metadata.

This means a candidate-vs-held-out comparison should be paired by sample index,
scenario, planning year, time domain, `rho`, node mapping, and non-EV component
streams where scientifically appropriate. The EV source pool changes between
candidate and held-out variants; that pool identity must be visible in the
manifest rather than hidden behind a shared seed.

## Candidate And Held-Out Comparison Design

The predeclared comparison should separate three uncertainty questions:

| Comparison | Purpose | Held-out access? |
|---|---|---:|
| Nested candidate prefixes | Test stability as candidate library size grows within the candidate pool | No |
| Disjoint candidate groups | Expose sensitivity to candidate source-batch composition | No |
| Leave-out variants | Detect whether specific candidate members dominate the downstream quantity | No |
| Fresh held-out batches | Test adequacy against untouched disjoint EV source data after the criterion is frozen | Yes, only after G0-A3-compliant criterion freeze |

The held-out test should be executed once from the frozen committed runner and
configuration. If it fails, the response is to accept the failure, extend and
regenerate a fresh held-out design under PI direction, or escalate the direct
library approach. Failed held-out evidence must not be tuned away or folded into
the candidate library without a new PI-approved holdout plan.

## Manifest Fields

The E3.S2a runner manifest should include, at minimum:

- task ID, runner version, git commit, command, configuration path, config hash,
  package versions, hardware/runtime context, and timestamp;
- scenario, planning year, `time_domain`, `rho`, timestep cadence, calendar ID,
  and node-mapping version;
- G0-A3/Q-5 resolution status, criterion ID, criterion status, loading threshold, persistence
  length, and whether event quantities were computed;
- transformer denominator/capacity convention and source decision status;
- root seed, sample indices, sample seeds, component stream IDs, and source
  member selections;
- candidate, quarantined diagnostic, and held-out EV library IDs, request IDs,
  source seeds, checksums, member counts, and disjointness checks;
- HP/PV shared weather-driver IDs and weather source/member provenance;
- baseline, adoption, and flexibility source/config IDs and checksums;
- IC-1 output checksums and IC-2 trajectory checksums for every compared branch;
- nested-prefix, disjoint-group, leave-out, and held-out comparison file paths
  and checksums;
- explicit `expected_difference` entries for any intentional mismatch between
  candidate and held-out provenance.

If any generated or historical comparison artifact is missing, the runner should
fail explicitly rather than silently omitting that branch from the adequacy
packet.

## Pre-Held-Out Checklist

Before opening held-out EV batches, A/C should be able to answer yes to each
item:

1. IC-1 real adapters produce validated full-year net-load trajectories with a
   common 900-second calendar.
2. IC-2 produces validated loading trajectories from those IC-1 outputs.
3. Candidate and held-out EV libraries are disjoint and checksummed.
4. Candidate-only nested, disjoint, and leave-out mechanics run without
   inspecting held-out outcomes.
5. The downstream criterion, tolerance, and failure response are frozen in a
   committed runner configuration.
6. The criterion records G0-A3 threshold semantics if it uses threshold exceedances, event episodes, or event probabilities.
7. The manifest records seed-tree identity, component streams, member IDs,
   weather-driver identity, node mapping, calendar, denominator convention, and
   every comparison checksum.
8. The PR/report states whether each output is a diagnostic, a held-out
   adequacy result, or a blocked future event result.

## Handoff Notes

Agent A support responsibility is the IC-1/IC-2 contract shape, CRN/provenance
expectations, and non-event scaffold documentation. Agent C owns the actual
E3.S2a adequacy execution and held-out data handling. Agent B can later consume
validated trajectory endpoints for IC-3 only after the required gates for
event-based propagation are resolved.

Suggested STATUS update for the eventual PR body:

`E3.S2a Integrated library adequacy | C | todo | design-support packet added by Agent A | E2.S2-E2.S6, E3.S2, ALEA-002, EV-005; use signed G0-A3 threshold plus remaining gates before opening event-based held-out results | PR: <this PR>`
