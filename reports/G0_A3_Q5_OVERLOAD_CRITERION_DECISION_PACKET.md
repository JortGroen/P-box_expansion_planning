# G0-A3 / Q-5 Overload-Criterion Decision Packet

Status: PI-facing decision packet only. This packet records source review, semantics, and implementation implications for Q-5. It does not resolve Q-5, run integrated event analysis, estimate `P(E)`, or create manuscript numbers.

## Purpose

Q-5 blocks the first integrated event-based scientific analysis because G0-A3 currently uses a provisional executable event definition: strict import loading above `1.1 p.u.` for at least four consecutive 15-minute samples. The PI decision needed is whether that working rule is a defensible primary criterion, should be reframed as an explicitly chosen modelling criterion, or should be replaced or supplemented before real event analysis.

## Current Executable Rule

The current code-level rule is:

- event state: import-direction loading `L_import > 1.1 p.u.`;
- persistence: at least four consecutive 15-minute samples;
- comparator: strict greater-than, so equality at exactly `1.1 p.u.` does not count;
- aggregation: sample persistence, not a rolling hourly average;
- direction: import/export direction is evaluated from the unwidened net-power sign;
- reset: direction flips or non-exceeding samples break a candidate episode.

In scientific prose this should be described as a provisional working overload criterion, not as a verified Dutch grid-code or DSO planning rule, unless Q-5 is resolved with a source that supports that stronger claim.

## Evidence Review

| Source inspected | What it supports | What it does not support |
| --- | --- | --- |
| Dutch Staatsblad 2025, 347, grid-code amendment: https://zoek.officielebekendmakingen.nl/stb-2025-347.html | Dutch regulation uses time-limited interruption and contingency concepts in transmission and high-voltage contexts. Examples include transformer-related outage allowances expressed in MW and minutes or weeks. | It does not define an MV/LV or HV/MV transformer overload event as `L_import > 1.1 p.u.` for one hour. It does not validate the current binary p.u. threshold. |
| IEC 60076-7 loading-guide discussion summarized in a CIGRE CSE distribution-transformer EV case study: https://cse.cigre.org/cse-n026/improving-the-utilization-of-distribution-transformers-supplying-public-electric-vehicle-charging-installations-a-new-zealand-case-study.html | Transformer loading can be treated thermally, with loading limits depending on operating class, duration, temperatures, ambient conditions, and ageing constraints. | It does not provide the current strict `1.1 p.u.` one-hour Dutch planning event. IEC-style use would require a thermal model and signed transformer/ambient assumptions, not a simple binary threshold. |
| Phase to Phase distribution-network protection examples: https://www.phasetophase.nl/book/book_1_6.html | Protection settings can use multiples of nominal current, but on protection/fault time scales of seconds. | These settings are not planning overload criteria and do not justify a one-hour `1.1 p.u.` event rule. |
| Dutch metering-code provision found in public legal sources: https://wetten.overheid.nl/BWBR0037946/2019-07-10/0/Hoofdstuk4/Paragraaf4.3/Sub-paragraaf4.3.6/Artikel4.3.6.8 | Some measurement-transformer requirements refer to operation up to a percentage of nominal current. | Metering accuracy/current-transformer requirements are not transformer-loading permission or a planning event definition. |

No reviewed primary source currently supports the exact combination of strict `>1.1 p.u.`, one hour, import direction, and four 15-minute consecutive samples as a settled Dutch DSO overload criterion. The present rule is therefore defensible only as an explicit project modelling convention unless a better source is supplied.

## Semantics To Decide

The PI decision should pin down the following semantics before integrated event analysis:

- **Threshold value:** keep `1.1 p.u.`, revert to `1.0 p.u.`, or use another sourced threshold.
- **Comparator:** strict `>` versus inclusive `>=`. The current strict comparator avoids treating exact-boundary samples as overloads.
- **Persistence meaning:** four consecutive 15-minute samples versus a rolling one-hour average.
- **Direction:** continue using unwidened net-power sign for import/export gating, consistent with G1-A2/E5-S3-T1.
- **Capacity denominator:** total capacity versus firm capacity remains separate from Q-5 but must be recorded with any criterion used in real analysis.
- **1.0-1.1 band:** decide whether this band is non-event headroom, a diagnostic-only exposure band, or part of a cumulative overload rule.

## Decision Options

### Option A: Keep the current rule as an explicit modelling criterion

Definition: event if `L_import > 1.1 p.u.` for at least four consecutive 15-minute samples. Do not add a cumulative rule for the `1.0-1.1 p.u.` band.

Implementation implication: minimal code change. The existing detector semantics remain valid, but runner manifests and methods text should identify the rule as a project modelling criterion rather than a sourced Dutch DSO threshold.

Interpretation implication: the result estimates the probability of a sustained high-overload event under this chosen definition. It does not measure all nameplate exceedance and may ignore long mild overload exposure between `1.0` and `1.1 p.u.`.

Suggested PI wording: "For the primary integrated analysis, use strict `L_import > 1.1 p.u.` for four consecutive 15-minute samples as a predeclared project overload-event criterion, without claiming it is a Dutch DSO standard. Treat the `1.0-1.1 p.u.` band as non-event exposure unless separately reported as a diagnostic."

### Option B: Keep `1.1 p.u.` but change one hour to rolling-hour average

Definition: event if a rolling one-hour aggregation exceeds `1.1 p.u.`. The PI would still need to specify whether all samples in the window must be import-direction samples or whether average import power determines direction.

Implementation implication: replace or supplement the current consecutive-sample detector with an averaging detector, add tests for windows with spikes and dips, and record aggregation semantics in manifests.

Interpretation implication: smoother than the current rule. Brief spikes above `1.1 p.u.` may not count, while sustained near-threshold operation with a high average may count differently from sample persistence.

### Option C: Add a cumulative rule for the `1.0-1.1 p.u.` band

Definition: event if either the high-overload rule is met or cumulative exposure in the `1.0-1.1 p.u.` band exceeds a signed exposure budget.

Implementation implication: this requires a new stateful exposure detector, a source or PI decision for the exposure metric, and rules for cooling/reset. Possible metrics include count of samples above `1.0 p.u.`, time integral of `L_import - 1.0`, or a thermal-state approximation. None should be invented inside Agent B work.

Interpretation implication: captures long mild overload exposure, but the result becomes a mixed high-threshold/cumulative-exposure event. Without a sourced thermal budget this option risks adding an unvalidated scientific assumption.

### Option D: Demote `1.1 p.u.` to sensitivity and use `1.0 p.u.` as primary

Definition: primary event is strict import loading above `1.0 p.u.` for at least four consecutive 15-minute samples; `1.1 p.u.` may remain a sensitivity or severe-overload diagnostic.

Implementation implication: update defaults/configuration and tests, and make all labels unambiguous. This would likely change event rates materially, so it must be decided before any real event run.

Interpretation implication: easier to describe as sustained nameplate exceedance, but still not a sourced one-hour thermal overload rule by itself.

### Option E: Replace the binary p.u. rule with a transformer thermal-loading model

Definition: event status follows a sourced thermal loading calculation using transformer characteristics, ambient temperature, loading history, and ageing or hot-spot constraints.

Implementation implication: out of scope for a quick Q-5 unblock. Requires new data, assumptions, validation, and ownership coordination.

Interpretation implication: physically richer and closer to transformer-loading guides, but much heavier and more assumption-dependent.

## Recommendation

If the PI wants to unblock the integrated analysis without adding unsupported thermal assumptions, Option A is the smallest defensible choice: keep the executable rule, explicitly label it as a predeclared project modelling criterion, and do not claim source-derived Dutch DSO status. Under this choice the `1.0-1.1 p.u.` band should not enter the primary event rule; it can be tracked later as a diagnostic or sensitivity only if the PI asks for that.

If the PI wants the primary criterion to be source-derived rather than convention-derived, Q-5 should remain open until a primary planning, grid-code, or DSO engineering source is obtained. In that case, Agent B should not proceed to real event analysis.

## Implementation Notes For Each Choice

| Choice | Detector impact | Manifest/provenance impact | Agent ownership impact |
| --- | --- | --- | --- |
| Option A | Keep strict consecutive detector and existing tests; ensure config records criterion ID. | Record threshold, comparator, cadence, persistence length, direction gate, and capacity denominator. | Mostly Agent A runner/config plus Agent B methods/protocol review. |
| Option B | Add rolling-average detector and edge-case tests. | Record aggregation window and direction semantics. | Likely Agent A-owned evaluator/runner change; Agent B can provide synthetic decision tests. |
| Option C | Add cumulative exposure detector with reset/cooling semantics. | Record exposure metric, budget, cooling/reset rule, and source. | Cross-agent; requires PI scientific decision before implementation. |
| Option D | Change primary threshold default/config and relabel `1.1` as sensitivity if retained. | Record threshold source/status and comparator. | Cross-agent because current evaluator defaults and documentation change. |
| Option E | New thermal model, not a simple detector tweak. | Record thermal model, transformer parameters, ambient inputs, ageing criterion, and validation source. | New scoped task/gate needed. |

## Acceptance Criteria After PI Resolution

Whichever option is selected, the later implementation should include synthetic tests for:

- equality at the threshold;
- one-sample gaps resetting persistence when consecutive-sample semantics are used;
- direction flips resetting import episodes;
- exactly four 15-minute samples triggering one-hour persistence;
- three samples not triggering;
- rolling-window edge cases if Option B is selected;
- cumulative exposure accumulation and reset/cooling if Option C is selected;
- manifest fields for threshold, comparator, cadence, persistence/aggregation, direction gate, and capacity denominator.

## Exact PI Decision Requested

Please resolve Q-5 by selecting one of the options above or by supplying a primary source that defines the desired overload criterion. The minimum actionable decision is:

1. primary threshold value;
2. strict or inclusive comparator;
3. consecutive-sample, rolling-average, cumulative-exposure, or thermal-model semantics;
4. whether the `1.0-1.1 p.u.` band is ignored, diagnostic-only, or event-forming;
5. capacity denominator convention to record with the event definition, or confirmation that denominator choice remains blocked separately.