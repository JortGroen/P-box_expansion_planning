# Response to the `epsilon_grid` Elicitation Proposal

**Date:** 2026-07-14

**Status:** review comments; no A-013 sign-off

**Responds to:** `epsilon_grid_expert_elicitation.md`, dated 2026-07-14

## Overall Assessment

The proposal is a useful and unusually transparent starting point. We agree
with its main structural recommendations: place the envelope directly on the
aggregate apparent-power loading quantity, use a relative form, propagate it
before event detection, retain the unwidened direction gate, and predeclare a
sensitivity sweep.

We do not approve the proposed A-013 completion as written. The DSO use-case
needs different wording, several mechanisms need to be reassigned, the
numerical justification overstates what is known, and the asserted-domain
conversion between total and firm capacity is incorrect. Please revise the
proposal using the comments below.

## 1. Correct the DSO Use-Case

The intended story is illustrative: imagine a DSO applying this method in its
normal planning process. Do not describe that DSO's network model as
`calibrated`, and do not imply that it is supported by dense measurements or a
distribution state estimator.

A realistic planning context is:

- topology and connectivity are assumed to be mostly correct;
- line and transformer characteristics are available from asset registers and
  are mostly correct, but retain residual parameter error;
- measurements and forecasts may be available at HV/MV transformers and other
  major boundaries;
- measurements below the HV/MV level are sparse and are not sufficient to
  calibrate all nodal behavior or perform defensible full-network state
  estimation; and
- lower-level injections are therefore forecast, synthesized, or allocated
  using the information normally available to the DSO.

Replace references to a calibrated operational model with **a DSO planning
model populated with the DSO's available asset, topology, boundary-measurement,
and forecast data**.

The abstract discrepancy should be written as

```text
delta_grid(X, rho, t) = L_physical(X, rho, t) - L_DSO_model(X, rho, t)
```

where `L_DSO_model` is the result of the DSO planning workflow for the stated
inputs and operating condition. The case study uses pandapower and SimBench as
a reproducible synthetic implementation of that workflow; it does not claim
that SimBench is the DSO's real network.

In real practice the DSO may use commercial planning software. Numerical
differences between pandapower and a commercial solver implementing the same
network equations and element models are an implementation-verification issue,
not the intended content of `epsilon_grid`. Pandapower's published validation
against PowerFactory/PSS Sincal supports that separation for matched model
formulations, but model-to-model agreement is not field validation:
<https://pandapower.readthedocs.io/en/v1.4.3/about/tests.html>.

Commercial software does not eliminate model error. Residual parameter error,
aggregation, model-form limitations, uncertain control states, and mismatches
between forecast allocation and physical operation may remain. The revised
text must not equate "commercial" with "true".

## 2. Preserve Clear Uncertainty Ownership

We agree that weather, adoption, behavioral variation, technology profiles,
and `rho_flex` uncertainty already represented in `X` must not be counted again
inside `epsilon_grid`.

The limited observability below the HV/MV boundary creates one point that the
proposal should handle explicitly. Uncertainty in spatially allocating demand,
EV, HP, PV, and reactive power must have exactly one owner:

- if it is varied explicitly in the aleatory/scenario model, it belongs to
  `X` and is excluded from `epsilon_grid`; or
- if the planning workflow uses one fixed allocation and its residual effect
  is not otherwise represented, that residual must be named explicitly as
  part of the assumed output discrepancy or introduced as a separate
  sensitivity.

Do not condition the formal definition on perfectly known nodal injections
while simultaneously using unobserved nodal injections as part of the
numerical error budget. State what the inputs mean and assign each uncertainty
once.

## 3. Use a Symmetric Relative Envelope

We prefer the proposed relative and symmetric form:

```text
L_physical in [(1 - epsilon_grid) * L_DSO_model,
               (1 + epsilon_grid) * L_DSO_model]
```

Symmetry is a deliberate governance choice. There is not enough evidence to
defend precise asymmetric endpoints, and `[-0.03, +0.05]` would imply more
knowledge than the project has. A symmetric interval is transparent, simple,
and conservative on the lower bound while retaining the same decision-binding
upper endpoint as that proposed asymmetric alternative.

The relative percentage is invariant to the chosen nameplate denominator. Do
not overstate this as fully decoupling A-013 from the total-versus-firm
decision: the physical operating domain, the overload threshold, and which
states are decision-relevant still change with that convention.

## 4. Reframe the Numerical Recommendation

We are willing to retain the following as an illustrative, predeclared set:

```text
reference assumption: epsilon_grid = 0.05
sensitivity values:   epsilon_grid in {0.02, 0.10}
diagnostic only:      epsilon_grid = 0
```

However, `0.05` must not be described as empirically validated, guaranteed, or
a conservative hard enclosure of all listed mechanisms. It is a realistic
engineering reference assumption for the illustrative case, tested against an
optimistic and a deliberately pessimistic alternative.

The current justification has two internal problems:

1. It combines mechanisms using a root-sum-square argument based on
   independence, while G1-A1 deliberately assumes unknown dependence and does
   not assign probability distributions to these discrepancies.
2. Its own pessimistic linear stack reaches approximately `-4%/+7%`, so a
   symmetric `+/-5%` interval cannot simultaneously be called a conservative
   enclosure of that stack.

Please remove the independence-based aggregation from the formal
justification. Present `5%` as the reference assumption, with `10%` as the
stress case that covers a materially more adverse combined discrepancy. If
the desired claim is instead a hard conservative engineering enclosure, the
primary value would need to be at least the largest defensible stacked
magnitude, likely rounded upward; that is not the claim we currently intend.

## 5. Revise the Mechanism Budget

Please revise M1-M7 as follows.

| Mechanism | Requested treatment |
|---|---|
| M1 solver/numerics | Remove from `epsilon_grid`. Treat matched pandapower-versus-commercial-solver agreement as implementation verification only. |
| M2 network parameters | Retain. Mostly reliable asset data does not mean exact impedances, temperatures, tap data, or loss parameters. Avoid unsupported precision in the propagated percentage. |
| M3 downstream-loss referencing | Resolve the profile reference boundary in E3 where possible. Only residual loss-model discrepancy after that correction belongs in `epsilon_grid`. |
| M4 reactive-power mapping | Split it. Network shunts/cable charging and parameter error may remain; uncertain load PF, DER control mode, and injected Q belong to the input/PF assumptions or their own sensitivity. |
| M5 ZIP/voltage dependence | Clarify the input definition. If `X` contains realized nodal P/Q, this is not a discrepancy conditional on the same injections. If `X` contains nominal demand commands, revise the formal definition accordingly. |
| M6 phase unbalance | Retain only as a model-form residual when the DSO planning model is balanced. Reduce or remove it if the asserted DSO model class explicitly represents unbalance. Do not make a per-phase thermal claim. |
| M7 harmonics | Remove while `L_physical` is defined at fundamental frequency. Including harmonic RMS would change the physical loading quantity and event definition. |

Also address station auxiliary demand, time alignment, meter aggregation, and
the selected transformer side as boundary-definition issues. Fix those
boundaries where possible rather than using `epsilon_grid` as a catch-all.

## 6. Fix the Total/Firm Domain Conversion

The proposed asserted domain states that `0.2-1.3 p.u.` on the total 80 MVA
nameplate is approximately `0.1-0.65 p.u.` on the firm 40 MVA nameplate. This
is reversed. For the two 40 MVA units:

```text
L_firm = |S| / 40 MVA = 2 * (|S| / 80 MVA) = 2 * L_total
```

Therefore:

```text
0.2-1.3 p.u. total basis = 0.4-2.6 p.u. firm basis
```

State the asserted domain first in physical MVA, then translate it into p.u.
under the denominator convention selected by the PI. This avoids another
silent inversion and makes the applicability domain physically interpretable.

## 7. Freeze the Measurement and Model Boundary

Before A-013 is signed, define the physical counterpart of `L_DSO_model`
unambiguously:

- HV-side or MV-side apparent power;
- treatment of transformer and downstream losses;
- inclusion or exclusion of station auxiliary demand;
- aggregation of the two units;
- fundamental-frequency, three-phase, 15-minute mean quantity; and
- handling of missing or time-misaligned transformer measurements.

The choice should match the quantity a DSO could reasonably measure or
forecast at the decision transformer. Tier-1, the AC model, and the physical
reference must then be compared at compatible boundaries. Differences caused
only by inconsistent reference sides must not be presented as scientific
model uncertainty.

## 8. Clarify External Validity

We agree that SimBench-to-Dutch-network representativeness is not part of
`epsilon_grid`. SimBench is a German benchmark developed with DSO input and
comparison against real German networks, but it is still a synthetic proxy for
this illustrative case: <https://www.mdpi.com/1996-1073/13/12/3290>.

The manuscript should say that a DSO application would replace SimBench with
its own planning model and data. It must not say or imply that the present case
has access to hidden Dutch field measurements or that its error interval was
empirically calibrated.

## 9. Provenance and Signing

Keep the AI provenance disclosure. This document is a model-assisted
engineering elicitation draft, not field-expert evidence by itself. A human
reviewer with DSO grid-planning or model-validation experience should review
the mechanism ownership, the `5%` reference value, the `2%/10%` sensitivities,
and the asserted domain before manuscript use.

If no human countersignature is obtained, the manuscript and A-013 should call
the values **illustrative engineering assumptions with mandatory sensitivity
analysis**, not an expert-validated envelope. Every literature statement used
to support a numerical contribution must be checked against the original
source; generic references to common DSO validation practice are not enough to
establish a bound.

## 10. Requested Revision of the Proposed A-013 Row

Please produce a revised row that:

1. uses `L_DSO_model` rather than `L_PP` in the conceptual definition;
2. describes an uncalibrated DSO planning model with sparse lower-level
   observability, not a state-estimated network;
3. uses the symmetric relative form;
4. labels `5%` as the illustrative reference assumption and `2%/10%` as
   mandatory sensitivities;
5. excludes matched solver-to-solver numerical differences;
6. assigns profile allocation, PF/Q, losses, ZIP behavior, unbalance, and
   harmonics consistently without double counting;
7. states the applicability domain in physical MVA and correct p.u.
   equivalents;
8. freezes the transformer-side and station-auxiliary boundary; and
9. records human countersignature as pending rather than completed.

The revised elicitation can then support the PI's A-013 decision. It should not
itself change the signed project definition until that review is complete.
