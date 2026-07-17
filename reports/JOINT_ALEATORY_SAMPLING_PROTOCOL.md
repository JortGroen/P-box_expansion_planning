# Joint Aleatory Sampling and Dependency Protocol

**Decision ID:** ALEA-001
**Status:** Approved by PI in chat, 2026-07-15
**Applies to:** E2.S2-E2.S6, E3.S2, E3.S4, and all manifested probabilistic experiments

## Purpose

The aleatory layer must preserve dependencies that have a physical or temporal
basis without inventing a fully specified joint distribution that the available
data cannot support. The primary approach is conditional simulation on shared
drivers and a common calendar. Copulas, latent common factors, or multivariate
block bootstrap remain escalation options if validation shows that this simpler
construction materially understates dependence or event-relevant tails.

## Primary Construction

Each Monte Carlo sample represents one coherent planning-year realization.
Internally, the existing IC-1 arguments `(scenario, year, seed)` must resolve to
one auditable realization context containing at least:

- the scenario and planning year;
- one canonical timezone-aware 15-minute calendar;
- the selected weather-member identifier;
- the selected EV and baseline profile-member identifiers;
- component-specific random-stream identifiers derived from the project seed
  tree; and
- the deterministic calendar-mapping version used for every input source.

This context is an internal implementation and manifest concept. It does not by
itself change the approved IC-1 public signature.

### Temporal dependence

Complete annual or contiguous source trajectories are retained. Individual
15-minute values, temperature days, irradiance days, or charging sessions must
not be independently shuffled. Calendar alignment may relabel timestamps, but
it must not silently destroy sequence, episode duration, seasonality, or
weekday/weekend structure.

### Shared weather dependence

One complete historical weather member, anchored to one KNMI calendar year,
supplies the weather vector for a sample. Temperature, irradiance, and any other
weather channels are selected, resampled, and aligned together; they must never
be drawn from unrelated years or shuffled independently. If KNMI does not
supply every required channel, the supplementary observed or reanalysis series
must cover the same timestamps and year. A typical-year PV reference must not be
sampled as though it were the irradiance realization. The heat-pump and PV
models consume the same aligned member, preserving cold/dark and warm/sunny
conditions as represented in the source observations.

The G0 design-cold requirement is met by including at least one complete
historical year containing a design-cold winter in the ensemble. This extends
the winter selection to the full-year input needed by G0-A2 without replacing
or independently synthesizing the non-winter weather.

### Common calendar

EV, baseline, heat-pump, PV, and weather outputs share one canonical calendar
before they are summed. The canonical calendar preserves local season and
weekday/weekend meaning and exposes one unambiguous UTC execution index for
numerical integration. The exact mapping for leap years and daylight-saving
transitions must be predeclared after the concrete KNMI files are selected,
implemented once, versioned, and tested before E2.S3/E2.S4 data are used. No
probabilistic result may depend on an undocumented timestamp repair.

### Component sampling

- EV sampling retains complete ElaadNL annual members and their within-profile
  temporal structure.
- Baseline sampling retains the source calendar and any simultaneous nodal
  structure available from SimBench before adding documented diversity.
- Heat-pump and PV outputs are conditionally generated from the shared weather
  member and scenario capacities.
- Adoption volumes are scenario inputs, not random draws unless a later signed
  decision explicitly assigns them probabilities.
- Flexibility controllability and model-output errors remain epistemic inputs;
  they are not sampled as aleatory component noise.

Where no joint data support an additional residual relationship, the assumed
residual treatment must be stated explicitly in `ASSUMPTIONS.md` before results
are generated. Absence of evidence is not permission to insert an undocumented
correlation or independence assumption.

## Downstream-Only Congestion Evaluation

Per ALEA-002, component-level statistics are data-quality diagnostics only. An
EV-only sustained-load statistic, an isolated technology percentile, or the
ElaadNL dashboard's pointwise daily p95 must not be labelled congestion or used
alone to stop profile-library generation.

For every realization, the sequence is:

1. select and align the baseline, EV, heat-pump, PV, and other declared
   component trajectories on the common calendar;
2. apply scenario adoption volumes and the declared flexibility branch;
3. aggregate the components into nodal net load;
4. evaluate transformer loading through IC-2; and
5. calculate the approved congestion/event measure from that integrated
   loading trajectory.

Finite profile-library adequacy is assessed with nested library subsets and
disjoint held-out batches through this complete downstream chain. Source-level
energy, peak, seasonal, and shape summaries remain useful for debugging, but
they cannot certify decision adequacy. A downstream p95 is allowed as a
provisional workflow and convergence diagnostic while the PI reviews published
congestion definitions; it does not supersede the G0 `P_crit` decision.

## Common Random Numbers

The same complete aleatory realization is reused across alpha levels,
controllability endpoints, model-error endpoints, and comparison treatments.
Component streams may be distinct within a realization, but they must be
derived from one seed tree and remain unchanged when only an epistemic or
methodological branch changes. Common random numbers support fair comparisons;
they do not substitute for physical dependence between components.

## Required Verification

Before E3.S2 integration and the E3.S2b capacity screen:

1. Assert exactly one canonical time index and expected 15-minute step count.
2. Test leap-year and daylight-saving behavior with explicit golden cases.
3. Assert that HP and PV receive the same weather-member ID and aligned weather
   timestamps for each sample.
4. Verify that temperature and irradiance retain their source pairing and
   chronological order after mapping.
5. Verify that any supplementary irradiance source covers the same timestamps
   and year as the KNMI temperature member; otherwise stop and escalate.
6. Verify that EV and baseline members retain complete trajectories and the
   intended weekday/weekend alignment.
7. Verify bit-identical component selections for the same IC-1 seed and across
   all common-random-number branches.
8. Record weather/profile member IDs, mapping version, and seed-tree information
   in the experiment manifest.
9. Produce diagnostics for event-relevant aggregate peaks and four-step episode
   statistics; mean-profile agreement alone is insufficient.
10. Compare candidate library sizes through nested and held-out integrated
    net-load runs; do not certify adequacy from component-level metrics alone.

## Escalation Path

If held-out diagnostics, tail convergence, or available joint observations show
that conditional simulation on weather and calendar does not preserve material
cross-component or spatial dependence, stop before final probabilistic results.
The next options are, in order of interpretability:

1. add a documented shared latent factor;
2. use multivariate or seasonal block bootstrap from joint observations; or
3. fit a copula to documented joint marginals and dependence data.

Any escalation requires evidence, a signed assumption or decision, a methods
paragraph, tests, and manifested sensitivity against the primary construction.
It must not be selected merely because it produces a more convenient congestion
case.
