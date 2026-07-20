"""Dubois-Foulloy-Mauris-Prade probability-to-possibility transforms.

The functions here are parameter-free uncertainty utilities. They do not choose
flexibility factors, fuzzy-number corners, or project-specific evidence weights.

Convention
----------
For finite states with normalized probability masses ``p_i``, the DFMP
maximum-specificity transform assigns

``pi_i = sum(p_j for p_j <= p_i)``.

Equal masses are assigned equal possibility grades. This indifference-preserving
tie convention is deliberate: splitting ties by input order would make the
membership shape depend on arbitrary list ordering.

Primary source
--------------
Dubois, D., Foulloy, L., Mauris, G., & Prade, H. (2004).
"Probability-possibility transformations, triangular fuzzy sets, and
probabilistic inequalities." Reliable Computing, 10(4), 273-297.
DOI: 10.1023/B:REOM.0000032115.22510.b5.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Hashable, Sequence


@dataclass(frozen=True)
class PossibilityDistribution:
    """Possibility grades aligned with a normalized probability model.

    Parameters
    ----------
    states:
        State labels in the same order as the input probabilities.
    probabilities:
        Normalized probability masses, dimensionless and summing to one.
    scores:
        Finite plausibility-order scores. Higher scores are at least as
        plausible as lower scores. For an ordinary finite probability mass
        function these are the probability masses themselves.
    possibilities:
        Possibility grades in ``[0, 1]``. At least one state has grade one.
    """

    states: tuple[Hashable, ...]
    probabilities: tuple[float, ...]
    scores: tuple[float, ...]
    possibilities: tuple[float, ...]

    def __post_init__(self) -> None:
        if not (
            len(self.states)
            == len(self.probabilities)
            == len(self.scores)
            == len(self.possibilities)
        ):
            raise ValueError(
                "states, probabilities, scores, and possibilities must align"
            )
        if not self.states:
            raise ValueError("possibility distribution must contain at least one state")
        if any(not 0.0 <= value <= 1.0 for value in self.possibilities):
            raise ValueError("possibilities must be in [0, 1]")
        if max(self.possibilities) != 1.0:
            raise ValueError("possibility distribution must be normalized")

    def as_mapping(self) -> dict[Hashable, float]:
        """Return possibility grades keyed by state label."""

        return dict(zip(self.states, self.possibilities))


def probability_to_possibility(
    probabilities: Sequence[float],
    *,
    states: Sequence[Hashable] | None = None,
    scores: Sequence[float] | None = None,
    tolerance: float = 1e-12,
) -> PossibilityDistribution:
    """Return the finite DFMP possibility distribution.

    Parameters
    ----------
    probabilities:
        Non-empty normalized probability masses. Values must be finite,
        non-negative, and sum to one within ``tolerance``.
    states:
        Optional state labels. If omitted, integer indices are used.
    scores:
        Optional plausibility-order scores. Higher scores mean at least as
        plausible. If omitted, probability masses are used, giving the standard
        finite DFMP transform ``pi_i = sum(p_j for p_j <= p_i)``.
    tolerance:
        Absolute tolerance for normalization and score ties.
    """

    masses = _validate_probabilities(probabilities, tolerance=tolerance)
    labels = _validate_states(states, expected_length=len(masses))
    normalized = _normalize(masses)
    order_scores = _validate_scores(scores, fallback=normalized, tolerance=tolerance)
    # DFMP grades accumulate probability mass at no more plausible states. This
    # is what makes the resulting possibility measure dominate the probability
    # measure without adding an independent probabilistic layer.
    raw_possibilities = tuple(
        min(
            1.0,
            math.fsum(
                mass
                for mass, other_score in zip(normalized, order_scores)
                if other_score <= score + tolerance
            ),
        )
        for score in order_scores
    )
    max_score = max(order_scores)
    possibilities = tuple(
        # Normality is a mathematical property of the transform. Rounding in
        # the accumulated masses must not make a valid PMF fail validation.
        1.0 if score == max_score else possibility
        for score, possibility in zip(order_scores, raw_possibilities)
    )

    return PossibilityDistribution(
        states=labels,
        probabilities=normalized,
        scores=order_scores,
        possibilities=possibilities,
    )


def _validate_probabilities(
    probabilities: Sequence[float],
    *,
    tolerance: float,
) -> tuple[float, ...]:
    if not math.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("tolerance must be finite and non-negative")

    masses = tuple(float(probability) for probability in probabilities)
    if not masses:
        raise ValueError("probabilities must not be empty")
    if any(not math.isfinite(probability) for probability in masses):
        raise ValueError("probabilities must be finite")
    if any(probability < 0.0 for probability in masses):
        raise ValueError("probabilities must be non-negative")

    total = math.fsum(masses)
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=tolerance):
        raise ValueError("probabilities must sum to one")
    return masses


def _validate_states(
    states: Sequence[Hashable] | None,
    *,
    expected_length: int,
) -> tuple[Hashable, ...]:
    labels: tuple[Hashable, ...] = (
        tuple(range(expected_length)) if states is None else tuple(states)
    )
    if len(labels) != expected_length:
        raise ValueError("states and probabilities must have the same length")
    return labels


def _validate_scores(
    scores: Sequence[float] | None,
    *,
    fallback: tuple[float, ...],
    tolerance: float,
) -> tuple[float, ...]:
    if scores is None:
        return fallback

    order_scores = tuple(float(score) for score in scores)
    if len(order_scores) != len(fallback):
        raise ValueError("scores and probabilities must have the same length")
    if any(not math.isfinite(score) for score in order_scores):
        raise ValueError("scores must be finite")

    return _canonical_scores(order_scores, tolerance=tolerance)


def _canonical_scores(
    scores: tuple[float, ...],
    *,
    tolerance: float,
) -> tuple[float, ...]:
    sorted_scores = sorted(scores)
    canonical_by_score: dict[float, float] = {}
    group_anchor = sorted_scores[0]
    for score in sorted_scores:
        # Absolute-only grouping avoids math.isclose's scale-dependent relative
        # tolerance and keeps near-tie chains from merging distinct ranks.
        if abs(score - group_anchor) > tolerance:
            group_anchor = score
        canonical_by_score[score] = group_anchor
    return tuple(canonical_by_score[score] for score in scores)


def _normalize(probabilities: tuple[float, ...]) -> tuple[float, ...]:
    total = math.fsum(probabilities)
    return tuple(probability / total for probability in probabilities)
