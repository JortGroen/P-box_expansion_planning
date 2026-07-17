"""Decision metrics for alpha-indexed p-box families."""

from __future__ import annotations

import math

from src.pbox import PBoxFamily


def alpha_star(pbox_family: PBoxFamily, p_crit: float) -> float:
    """Return ``inf{alpha: P_up^alpha <= P_crit}`` on the evaluated grid.

    Parameters
    ----------
    pbox_family:
        Alpha-indexed p-box bounds. The upper event probability at each alpha
        level is read from ``result.upper.probability``.
    p_crit:
        Critical overload probability, dimensionless in ``[0, 1]``.

    Returns
    -------
    float
        The smallest evaluated alpha satisfying the upper-bound risk criterion,
        or ``math.inf`` when no evaluated alpha satisfies it.
    """

    if not pbox_family:
        raise ValueError("pbox_family must contain at least one alpha level")
    if not math.isfinite(p_crit) or not 0.0 <= p_crit <= 1.0:
        raise ValueError("p_crit must be finite and in [0, 1]")

    # The project reports evaluated alpha-grid bounds only; interpolating here
    # would invent an unevaluated epistemic level and hide a refinement decision.
    ordered_results = sorted(pbox_family.values(), key=lambda result: result.alpha)
    for result in ordered_results:
        # The mathematical criterion is non-strict. Changing this to "<" would
        # incorrectly skip exact-boundary decisions.
        if result.upper.probability <= p_crit:
            return result.alpha

    return math.inf

