# E5.S3 T1 - Output-Domain Model-Error Schema Proposal

**Task:** E5.S3 T1  
**Owner:** Agent B, with Agent A review required before implementation  
**Status:** proposed; not approved  
**Decision requested:** PI approval of the IC-2/IC-3 schema below, or a specific amendment.

## Scope

This proposal defines the smallest G1-A1/G1-A2-compliant schema change at the
IC-2/IC-3 boundary. It does not implement E5.S3 T2-T4 and does not choose
`epsilon_grid`, Tier-1 error endpoints, a G2 adequacy rule, or the Q-5
threshold interpretation.

The current `Tier1Evaluation` already carries the essential IC-2 evidence:
`p_net_kw`, `screening_loading_pu`, direction masks, threshold, persistence
length, and the pre-widening event diagnostics. The smallest compatible change
is therefore to make that trajectory payload the required sample-level input to
IC-3 and add explicit output-error configuration on the IC-3 side.

## Proposed Boundary Types

### IC-2 sample result: `LoadingTrajectoryResult`

IC-2 should return or expose one sample-level object with these required fields:

| Field | Type | Unit / domain | Purpose |
|---|---|---|---|
| `p_net_kw` | `np.ndarray[float64]` shape `(T,)` | kW | Unwidened active-power trajectory for direction masks. |
| `screening_loading_pu` | `np.ndarray[float64]` shape `(T,)` | p.u., nonnegative | Unconditioned Tier-1 loading magnitude `L_T1(t)`. |
| `import_mask` | `np.ndarray[bool_]` shape `(T,)` | boolean | True exactly where unwidened `p_net_kw > 0`. |
| `export_mask` | `np.ndarray[bool_]` shape `(T,)` | boolean | True exactly where unwidened `p_net_kw < 0`; diagnostic only for primary import event. |
| `zero_mask` | `np.ndarray[bool_]` shape `(T,)` | boolean | True exactly where unwidened `p_net_kw == 0`. |
| `threshold_pu` | `float` | p.u. | Strict event threshold, currently the provisional G0-A3 value. |
| `min_consecutive_steps` | `int` | count | Episode persistence length, currently 4. |
| `time_domain` | `Literal["full_year", "window_set"]` | enum | Distinguishes primary full-year evaluation from diagnostics. |
| `primary_probability_domain` | `bool` | boolean | True only for full-year primary probability samples. |

Compatibility note: the existing `src.evaluator_sum.Tier1Evaluation` already
contains these fields. Agent A can either keep that dataclass as the concrete
IC-2 object or introduce a contract alias/protocol with the same fields.

The existing `overload`, `import_loading_pu`, `export_loading_pu`, and episode
diagnostics may remain for backward-compatible diagnostics, but IC-3 must not
consume the boolean `overload` as the source of model-error-aware probabilities.

### IC-3 error configuration: `OutputErrorEnvelope`

IC-3 should add one explicit configuration object:

| Field | Type | Unit / domain | Purpose |
|---|---|---|---|
| `epsilon_grid` | `float` | relative, `0 <= value < 1` | Symmetric relative grid-model envelope from signed A-013 scenarios. |
| `epsilon_tier1_minus` | `float` | p.u., `>= 0` | Additive lower Tier-1-to-pandapower endpoint from G2. |
| `epsilon_tier1_plus` | `float` | p.u., `>= 0` | Additive upper Tier-1-to-pandapower endpoint from G2. |
| `source_status` | `Literal["proposed", "signed"]` or manifest metadata | enum / metadata | Prevents paper runs before A-013 and G2 are approved. |

`epsilon_tier1_minus` and `epsilon_tier1_plus` are intentionally separate so a
future asymmetric or one-sided G2 envelope can be represented without another
interface change. A symmetric G2 envelope is represented by setting both to the
same value.

## Required Propagation Semantics

For each aleatory sample and alpha endpoint, IC-3 receives the IC-2 trajectory
object and computes

```text
L_T1(t) = screening_loading_pu(t)

L_PP_lower(t) = max(0, L_T1(t) - epsilon_tier1_minus)
L_PP_upper(t) =        L_T1(t) + epsilon_tier1_plus

L_lower(t) = (1 - epsilon_grid) * L_PP_lower(t)
L_upper(t) = (1 + epsilon_grid) * L_PP_upper(t)
```

The import event is then classified from direction-gated endpoint trajectories:

```text
lower_import_loading(t) = L_lower(t) if import_mask(t) else 0
upper_import_loading(t) = L_upper(t) if import_mask(t) else 0
```

The same strict threshold, `min_consecutive_steps`, and direction-flip reset
semantics as IC-2 are then applied to each endpoint trajectory. Since
`import_mask` is computed from unwidened `P_net`, export and zero-flow steps
cannot become import overload steps after widening.

## Probability and Confidence-Interval Semantics

For every alpha level, IC-3 must maintain separate endpoint event counts:

```text
lower_successes = sum(lower_endpoint_event_i for i in samples)
upper_successes = sum(upper_endpoint_event_i for i in samples)
```

Lower and upper `ProbabilityEstimate` values are computed from those counts and
the shared sample count. Wilson or the already-approved binomial CI method is
then applied to each count. No probability estimate or confidence interval is
shifted after estimation to represent model error.

## Dependence, Alpha Support, and CRN

- `epsilon_grid` is an unprobabilized interval parameter. It may depend
  arbitrarily on the aleatory inputs, controllability, time, and Tier-1 error
  within the signed envelope; IC-3 therefore evaluates endpoints, not random
  draws of `epsilon_grid`.
- The grid-error interval has the same support at every alpha level. It is not
  defuzzified and does not introduce an additional alpha grid.
- CRN identity remains unchanged: the same sample identity/seed/member IDs feed
  the lower and upper loading endpoints, alpha levels, and treatments. The only
  difference between endpoint counts is the epistemic endpoint applied after
  the same IC-2 trajectory has been produced.
- Clipping is limited to `max(0, L_T1 - epsilon_tier1_minus)` before relative
  scaling. Upper endpoints are not clipped.
- Asymmetric and one-sided Tier-1 errors are represented by unequal endpoint
  fields. A one-sided lower correction uses `epsilon_tier1_plus = 0`; a
  one-sided upper correction uses `epsilon_tier1_minus = 0`.
- Direction flips are represented by the existing `import_mask` sequence. Any
  non-import step sets endpoint import loading to zero, resetting the episode
  counter in the same detector used by IC-2.

## Backward Compatibility and Migration

Backward-compatible diagnostics can keep using `Tier1Evaluation.overload` for
plain Tier-1 checks and legacy tests. Model-error-aware p-box estimation must
migrate from a boolean `SampleEvaluator = Callable[[rho, seed], bool]` to a
trajectory evaluator such as:

```python
TrajectoryEvaluator = Callable[[float, int], LoadingTrajectoryResult]
```

The existing pre-G3 synthetic vertex tests in `src/pbox.py` can remain as a
test-only path, but paper-facing E5.S3 output-error estimation must use the
trajectory path. This is a behavior expansion of IC-3, not a change to the
fuzzy-number API or to the existing `ProbabilityEstimate`/`PBoxAlphaResult`
result shape.

Agent A-owned changes should be limited to documenting or aliasing the current
`Tier1Evaluation` as the IC-2 trajectory result and ensuring AC/Tier-2 drop-in
evaluators expose the same fields. Agent B-owned changes should implement the
IC-3 trajectory endpoint counting after PI approval.

## Acceptance Matrix for E5.S3 T2-T4

| Case | Expected check |
|---|---|
| Lower trajectory clipping | `L_T1 < epsilon_tier1_minus` yields zero lower loading before relative scaling. |
| Exact mixed composition | Hand-computed `L_lower` and `L_upper` match G1-A2 formulas for additive plus relative endpoints. |
| Unwidened direction gate | Export and zero-flow timesteps stay zero in endpoint import trajectories even if widened loading exceeds threshold. |
| Direction flip reset | A non-import step between exceedance runs prevents accidental episode joining. |
| Four-step strict threshold | Exactly four widened import values `> threshold_pu` trigger; values equal to threshold do not. |
| Lower/upper counts | Constructed samples produce separate hand-counted lower and upper successes, probabilities, and CIs. |
| No probability shifting | Tests assert probabilities are computed only from endpoint event counts. |
| CRN identity | Lower and upper endpoints for a sample reuse the same seed/member IDs and trajectory payload. |
| Alpha support | Error-envelope support is identical across alpha levels; only the fuzzy controllability cut changes. |
| Asymmetric Tier-1 endpoints | Unequal `epsilon_tier1_minus`/`epsilon_tier1_plus` produce the expected endpoint events. |
| One-sided Tier-1 endpoints | Zero on either side is accepted and does not require another schema. |
| Nestedness and bound order | Result family still satisfies `P_lower <= P_upper` and alpha nestedness where the fuzzy propagation assumptions apply. |
| Backward diagnostics | Existing `evaluate_tier1(...).overload` tests remain valid for plain Tier-1 diagnostics. |

## Remaining Decisions and Blocks

- **PI:** approve, amend, or reject this IC-2/IC-3 schema proposal.
- **Agent A review:** confirm `Tier1Evaluation` can serve as the IC-2 trajectory result, and define the matching AC/Tier-2 payload if needed.
- **G2:** supply additive Tier-1 endpoint values and validation/adequacy verdict.
- **A-013:** sign numerical `epsilon_grid` scenario values and operating-domain status before paper use.
- **Q-5:** resolve the provisional 1.1-p.u. overload-threshold source and time-aggregation review before integrated event-based scientific analysis.
- **G3:** decide whether endpoint/vertex propagation in controllability is allowed; before G3, the proposal only governs output-error endpoint classification once the appropriate rho sampling path is selected.

