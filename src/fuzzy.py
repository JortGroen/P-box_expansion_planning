"""Fuzzy-number utilities for alpha-cut propagation.

The classes in this module are parameter-free math helpers. Project-specific
controllability corners belong in signed registers/configs, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class AlphaCut:
    """Closed interval for one alpha level.

    Parameters
    ----------
    alpha:
        Possibility level in [0, 1].
    lower:
        Lower endpoint of the alpha-cut, in the fuzzy number's native units.
    upper:
        Upper endpoint of the alpha-cut, in the fuzzy number's native units.
    """

    alpha: float
    lower: float
    upper: float

    def __post_init__(self) -> None:
        _validate_alpha(self.alpha)
        if self.lower > self.upper:
            raise ValueError("alpha-cut lower endpoint must be <= upper endpoint")


@dataclass(frozen=True)
class TrapezoidalFuzzyNumber:
    """Normal trapezoidal fuzzy number defined by support and core endpoints.

    The membership is zero outside ``[support_left, support_right]``, one on
    ``[core_left, core_right]``, and linear on both shoulders.
    """

    support_left: float
    core_left: float
    core_right: float
    support_right: float

    def __post_init__(self) -> None:
        if not (
            self.support_left
            <= self.core_left
            <= self.core_right
            <= self.support_right
        ):
            raise ValueError(
                "expected support_left <= core_left <= core_right <= support_right"
            )

    def alpha_cut(self, alpha: float) -> AlphaCut:
        """Return the closed interval at possibility level ``alpha``."""

        _validate_alpha(alpha)
        lower = self.support_left + alpha * (self.core_left - self.support_left)
        upper = self.support_right - alpha * (self.support_right - self.core_right)
        return AlphaCut(alpha=alpha, lower=lower, upper=upper)

    def membership(self, value: float) -> float:
        """Return membership grade for ``value``."""

        if value < self.support_left or value > self.support_right:
            return 0.0
        if self.core_left <= value <= self.core_right:
            return 1.0
        if value < self.core_left:
            width = self.core_left - self.support_left
            return 1.0 if width == 0 else (value - self.support_left) / width
        width = self.support_right - self.core_right
        return 1.0 if width == 0 else (self.support_right - value) / width


@dataclass(frozen=True)
class TriangularFuzzyNumber:
    """Normal triangular fuzzy number with one modal value."""

    support_left: float
    mode: float
    support_right: float

    def __post_init__(self) -> None:
        if not (self.support_left <= self.mode <= self.support_right):
            raise ValueError("expected support_left <= mode <= support_right")

    def alpha_cut(self, alpha: float) -> AlphaCut:
        """Return the closed interval at possibility level ``alpha``."""

        return self.as_trapezoid().alpha_cut(alpha)

    def membership(self, value: float) -> float:
        """Return membership grade for ``value``."""

        return self.as_trapezoid().membership(value)

    def as_trapezoid(self) -> TrapezoidalFuzzyNumber:
        """Represent the triangle as a zero-width-core trapezoid."""

        return TrapezoidalFuzzyNumber(
            self.support_left,
            self.mode,
            self.mode,
            self.support_right,
        )


@dataclass(frozen=True)
class PiecewiseLinearFuzzyNumber:
    """Normal fuzzy number with piecewise-linear left and right shoulders.

    ``left`` is ordered from support to core with nondecreasing membership
    grades ending at 1. ``right`` is ordered from core to support with
    nonincreasing membership grades starting at 1. Each point is ``(x, mu)``.
    """

    left: Sequence[tuple[float, float]]
    right: Sequence[tuple[float, float]]

    def __post_init__(self) -> None:
        if len(self.left) < 2 or len(self.right) < 2:
            raise ValueError("left and right shoulders need at least two points")

        left = tuple((float(x), float(mu)) for x, mu in self.left)
        right = tuple((float(x), float(mu)) for x, mu in self.right)
        _validate_profile(left, side="left")
        _validate_profile(right, side="right")

        if left[-1][1] != 1.0 or right[0][1] != 1.0:
            raise ValueError("left profile must end at mu=1 and right start at mu=1")
        if left[-1][0] > right[0][0]:
            raise ValueError("left core endpoint must be <= right core endpoint")

        object.__setattr__(self, "left", left)
        object.__setattr__(self, "right", right)

    def alpha_cut(self, alpha: float) -> AlphaCut:
        """Return the closed interval at possibility level ``alpha``."""

        _validate_alpha(alpha)
        return AlphaCut(
            alpha=alpha,
            lower=_interpolate_x_for_mu(self.left, alpha),
            # The upper cut endpoint is max{x: mu(x) >= alpha}; using the
            # first crossing would incorrectly truncate a constant-mu plateau.
            upper=_interpolate_x_for_mu(
                self.right,
                alpha,
                prefer_rightmost=True,
            ),
        )

    def membership(self, value: float) -> float:
        """Return membership grade for ``value``."""

        if value < self.left[0][0] or value > self.right[-1][0]:
            return 0.0
        if self.left[-1][0] <= value <= self.right[0][0]:
            return 1.0
        profile = self.left if value < self.left[-1][0] else self.right
        return _interpolate_mu_for_x(profile, value)


def alpha_cuts(
    fuzzy_number: TrapezoidalFuzzyNumber
    | TriangularFuzzyNumber
    | PiecewiseLinearFuzzyNumber,
    alpha_grid: Sequence[float],
) -> tuple[AlphaCut, ...]:
    """Return alpha-cuts for all levels in ``alpha_grid``."""

    return tuple(fuzzy_number.alpha_cut(alpha) for alpha in alpha_grid)


def _validate_alpha(alpha: float) -> None:
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be in [0, 1]")


def _validate_profile(points: tuple[tuple[float, float], ...], side: str) -> None:
    xs = [point[0] for point in points]
    mus = [point[1] for point in points]
    if any(not 0.0 <= mu <= 1.0 for mu in mus):
        raise ValueError("membership grades must be in [0, 1]")
    if any(x2 < x1 for x1, x2 in zip(xs, xs[1:])):
        raise ValueError("profile x values must be nondecreasing")

    if side == "left":
        if points[0][1] != 0.0:
            raise ValueError("left profile must start at mu=0")
        if any(mu2 < mu1 for mu1, mu2 in zip(mus, mus[1:])):
            raise ValueError("left profile memberships must be nondecreasing")
    elif side == "right":
        if points[-1][1] != 0.0:
            raise ValueError("right profile must end at mu=0")
        if any(mu2 > mu1 for mu1, mu2 in zip(mus, mus[1:])):
            raise ValueError("right profile memberships must be nonincreasing")
    else:
        raise ValueError(f"unknown profile side: {side}")


def _interpolate_x_for_mu(
    points: Sequence[tuple[float, float]],
    alpha: float,
    *,
    prefer_rightmost: bool = False,
) -> float:
    segments = list(zip(points, points[1:]))
    if prefer_rightmost:
        segments.reverse()

    for (x0, mu0), (x1, mu1) in segments:
        lo_mu = min(mu0, mu1)
        hi_mu = max(mu0, mu1)
        if lo_mu <= alpha <= hi_mu:
            if mu0 == mu1:
                return x1 if prefer_rightmost else x0
            fraction = (alpha - mu0) / (mu1 - mu0)
            return x0 + fraction * (x1 - x0)
    raise RuntimeError("validated profile does not span the requested alpha")


def _interpolate_mu_for_x(
    points: Sequence[tuple[float, float]], value: float
) -> float:
    for (x0, mu0), (x1, mu1) in zip(points, points[1:]):
        if x0 <= value <= x1:
            if x0 == x1:
                return max(mu0, mu1)
            fraction = (value - x0) / (x1 - x0)
            return mu0 + fraction * (mu1 - mu0)
    return 0.0
