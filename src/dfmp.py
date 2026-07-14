"""Dubois-Foulloy-Mauris-Prade probability-to-possibility transform.

This module implements the finite, ordinal probability-to-possibility
transform used to construct a possibility distribution from a normalized
discrete probability mass function. It does not choose any project-specific
flexibility factors or fuzzy-number corners.

Source convention: Dubois, Foulloy, Mauris, and Prade (2004), "Probability-
possibility transformations, triangular fuzzy sets, and probabilistic
inequalities", Reliable Computing 10:273-297.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Hashable, Sequence


@dataclass(frozen=True)
class PossibilityDistribution:
    """Possibility grades aligned with an input probability mass function.

    Parameters
    ----------
    states:
        State labels in the same order as the input probabilities.
    probabilities:
        Normalized probability masses, dimensionless and summing to one.
    possibilities:
        Possibility grades in [0, 1]. At least one state has grade one.
    """

    states: tuple[Hashable, ...]
    probabilities: tuple[float, ...]
    possibilities: tuple[float, ...]

    def __post_init__(self) -> None:
        if not (
            len(self.states) == len(self.probabilities) == len(self.possibilities)
        ):
            raise ValueError("states, probabilities, and possibilities must align")
        if not self.states:
            raise ValueError("possibility distribution must contain at least one state")
        if any(not 0.0 <= value <= 1.0 for value in self.possibilities):
            raise ValueError("possibilities must be in [0, 1]")
        if max(self.possibilities) != 1.0:
            raise ValueError("possibility distribution must be normalized")


def probability_to_possibility(
    probabilities: Sequence[float],
    *,
    states: Sequence[Hashable] | None = None,
    tolerance: float = 1e-12,
) -> PossibilityDistribution:
    """Return the finite DFMP possibility distribution.

    Mathematical convention
    -----------------------
    For a finite probability mass function ``p`` over states ``x_i``, this uses
    the Dubois-Foulloy-Mauris-Prade maximum-specificity transform

    ``pi_i = sum(p_j for p_j <= p_i)``.

    Equal probability masses receive equal possibility grades, making the
    result independent of the input order within tied groups. The output
    possibility distribution dominates the input probability measure in the
    usual finite sense: every event's probability is bounded above by the
    maximum possibility of its member states.

    Parameters
    ----------
    probabilities:
        Non-empty normalized probability masses, dimensionless. Values must be
        finite, non-negative, and sum to one within ``tolerance``.
    states:
        Optional state labels. If omitted, integer indices are used.
    tolerance:
        Absolute tolerance for normalization and tie grouping.
    """

    masses = tuple(float(probability) for probability in probabilities)
    if not masses:
        raise ValueError("probabilities must not be empty")
    if tolerance < 0.0:
        raise ValueError("tolerance must be non-negative")
    if any(not math.isfinite(probability) for probability in masses):
        raise ValueError("probabilities must be finite")
    if any(probability < 0.0 for probability in masses):
        raise ValueError("probabilities must be non-negative")

    total = math.fsum(masses)
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=tolerance):
        raise ValueError("probabilities must sum to one")

    labels = tuple(range(len(masses))) if states is None else tuple(states)
    if len(labels) != len(masses):
        raise ValueError("states and probabilities must have the same length")

    normalized = tuple(probability / total for probability in masses)
    possibilities = tuple(
        min(
            1.0,
            math.fsum(
                other for other in normalized if other <= probability + tolerance
            ),
        )
        for probability in normalized
    )

    return PossibilityDistribution(
        states=labels,
        probabilities=normalized,
        possibilities=possibilities,
    )
