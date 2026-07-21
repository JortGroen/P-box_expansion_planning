"""Decision metrics for alpha-indexed p-box families."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from src.fuzzy import (
    PiecewiseLinearFuzzyNumber,
    TrapezoidalFuzzyNumber,
    TriangularFuzzyNumber,
)
from src.pbox import FuzzyNumber, PBoxFamily


@dataclass(frozen=True)
class RhoProbabilityPoint:
    """Probability bounds at one synthetic controllability grid point.

    Parameters
    ----------
    rho:
        Demand-side controllability fraction, dimensionless in ``[0, 1]``.
    lower_probability:
        Lower event-probability bound at ``rho``, dimensionless in ``[0, 1]``.
    upper_probability:
        Upper event-probability bound at ``rho``, dimensionless in ``[0, 1]``.
    """

    rho: float
    lower_probability: float
    upper_probability: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.rho) or not 0.0 <= self.rho <= 1.0:
            raise ValueError("rho must be finite and in [0, 1]")
        for name, value in (
            ("lower_probability", self.lower_probability),
            ("upper_probability", self.upper_probability),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and in [0, 1]")
        if self.lower_probability > self.upper_probability:
            raise ValueError("expected lower_probability <= upper_probability")


@dataclass(frozen=True)
class RhoStarAlphaResult:
    """Alpha-indexed lower/upper ``rho_star`` bounds."""

    alpha: float
    p_crit: float
    rho_lower: float
    rho_upper: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.alpha) or not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be finite and in [0, 1]")
        if not math.isfinite(self.p_crit) or not 0.0 <= self.p_crit <= 1.0:
            raise ValueError("p_crit must be finite and in [0, 1]")
        for name, value in (
            ("rho_lower", self.rho_lower),
            ("rho_upper", self.rho_upper),
        ):
            if value != math.inf and (
                not math.isfinite(value) or not 0.0 <= value <= 1.0
            ):
                raise ValueError(f"{name} must be in [0, 1] or math.inf")
        if self.rho_lower > self.rho_upper:
            raise ValueError("rho_lower must be <= rho_upper")


@dataclass(frozen=True)
class RhoStarMembershipResult:
    """Membership bounds for an alpha-indexed ``rho_star`` interval."""

    alpha: float
    mu_lower: float
    mu_upper: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.alpha) or not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be finite and in [0, 1]")
        if not 0.0 <= self.mu_lower <= self.mu_upper <= 1.0:
            raise ValueError("expected 0 <= mu_lower <= mu_upper <= 1")


class ProcurementTargetClassification(str, Enum):
    """Synthetic geometric comparison between rho target and delivery envelope."""

    INSIDE_ENVELOPE = "inside-envelope"
    OVERLAPPING_MONITOR = "overlapping-monitor"
    OUTSIDE_ENVELOPE = "outside-envelope"
    NEVER_SATISFIED = "never-satisfied"


@dataclass(frozen=True)
class ProcurementTargetResult:
    """Alpha-indexed procurement-target framing for synthetic rho intervals."""

    alpha: float
    rho_lower: float
    rho_upper: float
    envelope_lower: float
    envelope_upper: float
    classification: ProcurementTargetClassification

    def __post_init__(self) -> None:
        if not math.isfinite(self.alpha) or not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be finite and in [0, 1]")
        for name, value in (
            ("rho_lower", self.rho_lower),
            ("rho_upper", self.rho_upper),
        ):
            if value != math.inf and (
                not math.isfinite(value) or not 0.0 <= value <= 1.0
            ):
                raise ValueError(f"{name} must be in [0, 1] or math.inf")
        for name, value in (
            ("envelope_lower", self.envelope_lower),
            ("envelope_upper", self.envelope_upper),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and in [0, 1]")
        if self.rho_lower > self.rho_upper:
            raise ValueError("rho_lower must be <= rho_upper")
        if self.envelope_lower > self.envelope_upper:
            raise ValueError("envelope_lower must be <= envelope_upper")
        if not isinstance(self.classification, ProcurementTargetClassification):
            raise TypeError("classification must be a ProcurementTargetClassification")


@dataclass(frozen=True)
class DeferralYearResult:
    """One synthetic year entry in an alpha-indexed deferral horizon."""

    year: int
    alpha: float
    rho_lower: float
    rho_upper: float
    envelope_lower: float
    envelope_upper: float
    classification: ProcurementTargetClassification

    def __post_init__(self) -> None:
        if self.year <= 0:
            raise ValueError("year must be positive")
        ProcurementTargetResult(
            alpha=self.alpha,
            rho_lower=self.rho_lower,
            rho_upper=self.rho_upper,
            envelope_lower=self.envelope_lower,
            envelope_upper=self.envelope_upper,
            classification=self.classification,
        )


@dataclass(frozen=True)
class DeferralHorizonResult:
    """Synthetic alpha-indexed lower/upper deferral-horizon interpretation."""

    alpha: float
    lower_year: int | None
    upper_year: int | None
    first_unmet_year: int | None
    first_never_satisfied_year: int | None
    monotone_in_year: bool
    yearly_results: tuple[DeferralYearResult, ...]

    def __post_init__(self) -> None:
        if not math.isfinite(self.alpha) or not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be finite and in [0, 1]")
        for name, year in (
            ("lower_year", self.lower_year),
            ("upper_year", self.upper_year),
            ("first_unmet_year", self.first_unmet_year),
            ("first_never_satisfied_year", self.first_never_satisfied_year),
        ):
            if year is not None and year <= 0:
                raise ValueError(f"{name} must be positive when supplied")
        if (
            self.lower_year is not None
            and self.upper_year is not None
            and self.lower_year > self.upper_year
        ):
            raise ValueError("lower_year must be <= upper_year")
        if not self.yearly_results:
            raise ValueError("yearly_results must not be empty")
        years = [result.year for result in self.yearly_results]
        if years != sorted(years) or len(set(years)) != len(years):
            raise ValueError("yearly_results must have unique sorted years")
        for result in self.yearly_results:
            if result.alpha != self.alpha:
                raise ValueError("yearly_results alpha must match result alpha")


class ValueOfInformationClassification(str, Enum):
    """Synthetic interval comparison between information value and cost."""

    NET_POSITIVE = "net-positive"
    NET_NEGATIVE = "net-negative"
    INDETERMINATE = "indeterminate"
    NOT_APPLICABLE = "not-applicable"


@dataclass(frozen=True)
class SyntheticMonetaryInterval:
    """Nonnegative synthetic monetary interval for scaffold-only VoI inputs."""

    lower: float
    upper: float
    unit: str

    def __post_init__(self) -> None:
        for name, value in (("lower", self.lower), ("upper", self.upper)):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if self.lower > self.upper:
            raise ValueError("lower must be <= upper")
        if not self.unit.strip():
            raise ValueError("unit must be nonempty")


@dataclass(frozen=True)
class ValueOfInformationInput:
    """Synthetic alpha-indexed cost/benefit input for VoI scaffolding."""

    alpha: float
    decision_width_lower: float
    decision_width_upper: float
    deferral_benefit: SyntheticMonetaryInterval
    information_cost: SyntheticMonetaryInterval

    def __post_init__(self) -> None:
        if not math.isfinite(self.alpha) or not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be finite and in [0, 1]")
        for name, value in (
            ("decision_width_lower", self.decision_width_lower),
            ("decision_width_upper", self.decision_width_upper),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and in [0, 1]")
        if self.decision_width_lower > self.decision_width_upper:
            raise ValueError("decision_width_lower must be <= decision_width_upper")
        if self.deferral_benefit.unit != self.information_cost.unit:
            raise ValueError("deferral_benefit and information_cost units must match")


@dataclass(frozen=True)
class ValueOfInformationResult:
    """Synthetic alpha-indexed lower/upper value-of-information result."""

    alpha: float
    lower_horizon_year: int | None
    upper_horizon_year: int | None
    decision_width_lower: float
    decision_width_upper: float
    deferral_benefit_lower: float
    deferral_benefit_upper: float
    information_cost_lower: float
    information_cost_upper: float
    net_value_lower: float
    net_value_upper: float
    unit: str
    classification: ValueOfInformationClassification

    def __post_init__(self) -> None:
        if not math.isfinite(self.alpha) or not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be finite and in [0, 1]")
        for name, year in (
            ("lower_horizon_year", self.lower_horizon_year),
            ("upper_horizon_year", self.upper_horizon_year),
        ):
            if year is not None and year <= 0:
                raise ValueError(f"{name} must be positive when supplied")
        for name, value in (
            ("decision_width_lower", self.decision_width_lower),
            ("decision_width_upper", self.decision_width_upper),
            ("deferral_benefit_lower", self.deferral_benefit_lower),
            ("deferral_benefit_upper", self.deferral_benefit_upper),
            ("information_cost_lower", self.information_cost_lower),
            ("information_cost_upper", self.information_cost_upper),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if self.decision_width_lower > self.decision_width_upper:
            raise ValueError("decision_width_lower must be <= decision_width_upper")
        if self.deferral_benefit_lower > self.deferral_benefit_upper:
            raise ValueError("deferral_benefit_lower must be <= deferral_benefit_upper")
        if self.information_cost_lower > self.information_cost_upper:
            raise ValueError("information_cost_lower must be <= information_cost_upper")
        for name, value in (
            ("net_value_lower", self.net_value_lower),
            ("net_value_upper", self.net_value_upper),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.net_value_lower > self.net_value_upper:
            raise ValueError("net_value_lower must be <= net_value_upper")
        if not self.unit.strip():
            raise ValueError("unit must be nonempty")
        if not isinstance(self.classification, ValueOfInformationClassification):
            raise TypeError("classification must be a ValueOfInformationClassification")


RhoProbabilityCurves = Mapping[float, Sequence[RhoProbabilityPoint]]
RhoStarFamily = Mapping[float, RhoStarAlphaResult]
YearlyProcurementTargets = Mapping[int, Mapping[float, ProcurementTargetResult]]
ValueOfInformationInputs = Mapping[float, ValueOfInformationInput]


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


def rho_star_from_probability_curves(
    probability_curves: RhoProbabilityCurves,
    p_crit: float,
) -> dict[float, RhoStarAlphaResult]:
    """Return alpha-indexed ``rho_star`` bounds from synthetic monotone curves.

    This pre-G3 scaffold assumes each supplied probability curve is synthetic,
    deterministic, and monotone nonincreasing in ``rho``. For each alpha level,
    it computes

    ``rho_star = inf{rho: P(E | rho) <= P_crit}``

    separately for the lower and upper event-probability curves. Crossings
    between supplied rho grid points use the explicit piecewise-linear
    convention documented here; real project use remains blocked until G3,
    Q-5, G2, A-013, and integrated E3 outputs are resolved.
    """

    if not probability_curves:
        raise ValueError("probability_curves must contain at least one alpha level")
    if not math.isfinite(p_crit) or not 0.0 <= p_crit <= 1.0:
        raise ValueError("p_crit must be finite and in [0, 1]")

    results: dict[float, RhoStarAlphaResult] = {}
    for alpha, points in probability_curves.items():
        ordered = _validate_rho_curve(alpha, points)
        rho_lower = _rho_crossing(
            [(point.rho, point.lower_probability) for point in ordered],
            p_crit,
        )
        rho_upper = _rho_crossing(
            [(point.rho, point.upper_probability) for point in ordered],
            p_crit,
        )
        results[alpha] = RhoStarAlphaResult(
            alpha=alpha,
            p_crit=p_crit,
            rho_lower=rho_lower,
            rho_upper=rho_upper,
        )
    return dict(sorted(results.items()))


def rho_star_membership(
    rho_star_family: RhoStarFamily,
    fuzzy_number: FuzzyNumber,
) -> dict[float, RhoStarMembershipResult]:
    """Read fuzzy-membership bounds for finite ``rho_star`` intervals.

    The helper preserves the alpha-indexed lower/upper structure. It rejects
    ``math.inf`` because a never-satisfied synthetic curve has no finite
    controllability target whose membership can be read from the fuzzy number.
    """

    if not rho_star_family:
        raise ValueError("rho_star_family must contain at least one alpha level")

    results: dict[float, RhoStarMembershipResult] = {}
    for alpha, rho_star in rho_star_family.items():
        if not math.isfinite(rho_star.rho_lower) or not math.isfinite(
            rho_star.rho_upper
        ):
            raise ValueError("membership readout requires finite rho_star bounds")
        mu_lower, mu_upper = _membership_bounds(
            fuzzy_number,
            rho_star.rho_lower,
            rho_star.rho_upper,
        )
        results[alpha] = RhoStarMembershipResult(
            alpha=alpha,
            mu_lower=mu_lower,
            mu_upper=mu_upper,
        )
    return dict(sorted(results.items()))


def classify_procurement_target(
    rho_star_family: RhoStarFamily,
    delivery_envelope: FuzzyNumber,
) -> dict[float, ProcurementTargetResult]:
    """Compare synthetic ``rho_star`` intervals with a delivery envelope.

    The comparison is alpha-indexed and geometric: each finite target interval
    is compared with the delivery-envelope alpha-cut at the same alpha level.
    It is scaffold-only and does not convert the classification into a project
    decision or manuscript number.
    """

    if not rho_star_family:
        raise ValueError("rho_star_family must contain at least one alpha level")

    results: dict[float, ProcurementTargetResult] = {}
    for alpha, rho_star in rho_star_family.items():
        cut = delivery_envelope.alpha_cut(alpha)
        classification = _classify_interval_against_envelope(
            rho_star.rho_lower,
            rho_star.rho_upper,
            cut.lower,
            cut.upper,
        )
        results[alpha] = ProcurementTargetResult(
            alpha=alpha,
            rho_lower=rho_star.rho_lower,
            rho_upper=rho_star.rho_upper,
            envelope_lower=cut.lower,
            envelope_upper=cut.upper,
            classification=classification,
        )
    return dict(sorted(results.items()))


def deferral_horizon_from_procurement_targets(
    yearly_targets: YearlyProcurementTargets,
) -> dict[float, DeferralHorizonResult]:
    """Summarize synthetic year-indexed targets as alpha-indexed horizons.

    ``lower_year`` is the latest supplied year whose target interval is fully
    inside the delivery envelope. ``upper_year`` also admits overlap/monitoring
    years. The output is a scaffold for later manifested results and does not
    infer unevaluated years or collapse alpha levels into a single horizon.
    """

    if not yearly_targets:
        raise ValueError("yearly_targets must contain at least one year")

    ordered_years = _validate_yearly_procurement_targets(yearly_targets)
    alpha_grid = tuple(sorted(yearly_targets[ordered_years[0]]))
    results: dict[float, DeferralHorizonResult] = {}
    for alpha in alpha_grid:
        yearly = tuple(
            _deferral_year_result(year, yearly_targets[year][alpha])
            for year in ordered_years
        )
        lower_year = _latest_year_with_classification(
            yearly,
            {ProcurementTargetClassification.INSIDE_ENVELOPE},
        )
        upper_year = _latest_year_with_classification(
            yearly,
            {
                ProcurementTargetClassification.INSIDE_ENVELOPE,
                ProcurementTargetClassification.OVERLAPPING_MONITOR,
            },
        )
        first_unmet_year = _first_year_with_classification(
            yearly,
            {
                ProcurementTargetClassification.OUTSIDE_ENVELOPE,
                ProcurementTargetClassification.NEVER_SATISFIED,
            },
        )
        first_never_satisfied_year = _first_year_with_classification(
            yearly,
            {ProcurementTargetClassification.NEVER_SATISFIED},
        )
        results[alpha] = DeferralHorizonResult(
            alpha=alpha,
            lower_year=lower_year,
            upper_year=upper_year,
            first_unmet_year=first_unmet_year,
            first_never_satisfied_year=first_never_satisfied_year,
            monotone_in_year=_is_monotone_horizon_sequence(yearly),
            yearly_results=yearly,
        )
    return results


def value_of_information_scaffold(
    deferral_horizons: Mapping[float, DeferralHorizonResult],
    value_inputs: ValueOfInformationInputs,
) -> dict[float, ValueOfInformationResult]:
    """Compare synthetic information benefits and costs by alpha level.

    This scaffold uses caller-supplied synthetic intervals only. It preserves
    alpha-indexed lower/upper decision-width, benefit, cost, and net-value
    bounds, and it does not approve or infer any real economic assumption.
    """

    if not deferral_horizons:
        raise ValueError("deferral_horizons must contain at least one alpha level")
    if not value_inputs:
        raise ValueError("value_inputs must contain at least one alpha level")
    alpha_grid = tuple(sorted(deferral_horizons))
    if tuple(sorted(value_inputs)) != alpha_grid:
        raise ValueError("deferral_horizons and value_inputs need the same alpha grid")

    results: dict[float, ValueOfInformationResult] = {}
    for alpha in alpha_grid:
        horizon = deferral_horizons[alpha]
        value_input = value_inputs[alpha]
        if horizon.alpha != alpha or value_input.alpha != alpha:
            raise ValueError("alpha values must match their mapping keys")
        net_lower, net_upper = _subtract_monetary_intervals(
            value_input.deferral_benefit,
            value_input.information_cost,
        )
        classification = _classify_value_of_information(
            horizon,
            net_lower,
            net_upper,
        )
        results[alpha] = ValueOfInformationResult(
            alpha=alpha,
            lower_horizon_year=horizon.lower_year,
            upper_horizon_year=horizon.upper_year,
            decision_width_lower=value_input.decision_width_lower,
            decision_width_upper=value_input.decision_width_upper,
            deferral_benefit_lower=value_input.deferral_benefit.lower,
            deferral_benefit_upper=value_input.deferral_benefit.upper,
            information_cost_lower=value_input.information_cost.lower,
            information_cost_upper=value_input.information_cost.upper,
            net_value_lower=net_lower,
            net_value_upper=net_upper,
            unit=value_input.deferral_benefit.unit,
            classification=classification,
        )
    return results


def _validate_rho_curve(
    alpha: float,
    points: Sequence[RhoProbabilityPoint],
) -> tuple[RhoProbabilityPoint, ...]:
    if not math.isfinite(alpha) or not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be finite and in [0, 1]")
    if not points:
        raise ValueError("each alpha level needs at least one rho point")

    ordered = tuple(sorted(points, key=lambda point: point.rho))
    if len({point.rho for point in ordered}) != len(ordered):
        raise ValueError("rho points must be unique within each alpha level")
    for left, right in zip(ordered, ordered[1:]):
        if left.lower_probability < right.lower_probability:
            raise ValueError("lower probability curve must be nonincreasing in rho")
        if left.upper_probability < right.upper_probability:
            raise ValueError("upper probability curve must be nonincreasing in rho")
    return ordered


def _rho_crossing(curve: Sequence[tuple[float, float]], p_crit: float) -> float:
    first_rho, first_probability = curve[0]
    if first_probability <= p_crit:
        return first_rho

    previous_rho = first_rho
    previous_probability = first_probability
    for rho, probability in curve[1:]:
        if probability <= p_crit:
            if probability == previous_probability:
                return rho
            # Root-finding is only inside a supplied synthetic monotone bracket;
            # extrapolating beyond the evaluated rho range would create an
            # unsupported controllability target.
            fraction = (p_crit - previous_probability) / (
                probability - previous_probability
            )
            return previous_rho + fraction * (rho - previous_rho)
        previous_rho = rho
        previous_probability = probability

    return math.inf


def _membership_bounds(
    fuzzy_number: FuzzyNumber,
    rho_lower: float,
    rho_upper: float,
) -> tuple[float, float]:
    if rho_lower > rho_upper:
        raise ValueError("rho_lower must be <= rho_upper")

    endpoint_memberships = (
        fuzzy_number.membership(rho_lower),
        fuzzy_number.membership(rho_upper),
    )
    mu_lower = min(endpoint_memberships)
    mu_upper = max(endpoint_memberships)
    core_left, core_right = _core_interval(fuzzy_number)
    # Normal convex fuzzy numbers can peak inside the rho-star interval; only
    # checking endpoints would silently miss a target interval crossing the core.
    if rho_lower <= core_right and core_left <= rho_upper:
        mu_upper = 1.0
    return mu_lower, mu_upper


def _classify_interval_against_envelope(
    rho_lower: float,
    rho_upper: float,
    envelope_lower: float,
    envelope_upper: float,
) -> ProcurementTargetClassification:
    if not math.isfinite(rho_lower) or not math.isfinite(rho_upper):
        return ProcurementTargetClassification.NEVER_SATISFIED
    if envelope_lower <= rho_lower and rho_upper <= envelope_upper:
        return ProcurementTargetClassification.INSIDE_ENVELOPE
    # This scaffold is a geometric comparison only; "monitor" marks partial
    # overlap without assuming procurement success or failure before G3/G4.
    if rho_lower <= envelope_upper and envelope_lower <= rho_upper:
        return ProcurementTargetClassification.OVERLAPPING_MONITOR
    return ProcurementTargetClassification.OUTSIDE_ENVELOPE


def _validate_yearly_procurement_targets(
    yearly_targets: YearlyProcurementTargets,
) -> tuple[int, ...]:
    ordered_years = tuple(sorted(yearly_targets))
    if len(set(ordered_years)) != len(ordered_years):
        raise ValueError("years must be unique")
    for year in ordered_years:
        if year <= 0:
            raise ValueError("years must be positive")
        if not yearly_targets[year]:
            raise ValueError("each year must contain at least one alpha result")

    alpha_grid = tuple(sorted(yearly_targets[ordered_years[0]]))
    for year in ordered_years:
        current_alpha_grid = tuple(sorted(yearly_targets[year]))
        if current_alpha_grid != alpha_grid:
            raise ValueError("each year must contain the same alpha grid")
        for alpha, result in yearly_targets[year].items():
            if result.alpha != alpha:
                raise ValueError("procurement result alpha must match mapping key")
    return ordered_years


def _deferral_year_result(
    year: int,
    procurement_target: ProcurementTargetResult,
) -> DeferralYearResult:
    return DeferralYearResult(
        year=year,
        alpha=procurement_target.alpha,
        rho_lower=procurement_target.rho_lower,
        rho_upper=procurement_target.rho_upper,
        envelope_lower=procurement_target.envelope_lower,
        envelope_upper=procurement_target.envelope_upper,
        classification=procurement_target.classification,
    )


def _latest_year_with_classification(
    yearly: Sequence[DeferralYearResult],
    classifications: set[ProcurementTargetClassification],
) -> int | None:
    years = [result.year for result in yearly if result.classification in classifications]
    return max(years) if years else None


def _first_year_with_classification(
    yearly: Sequence[DeferralYearResult],
    classifications: set[ProcurementTargetClassification],
) -> int | None:
    years = [result.year for result in yearly if result.classification in classifications]
    return min(years) if years else None


def _is_monotone_horizon_sequence(yearly: Sequence[DeferralYearResult]) -> bool:
    order = {
        ProcurementTargetClassification.INSIDE_ENVELOPE: 0,
        ProcurementTargetClassification.OVERLAPPING_MONITOR: 1,
        ProcurementTargetClassification.OUTSIDE_ENVELOPE: 2,
        ProcurementTargetClassification.NEVER_SATISFIED: 3,
    }
    severities = [order[result.classification] for result in yearly]
    # This is only a diagnostic sanity flag: scaffold tests may expose
    # non-monotone synthetic years, but real horizon claims need manifested runs.
    return all(left <= right for left, right in zip(severities, severities[1:]))


def _subtract_monetary_intervals(
    benefit: SyntheticMonetaryInterval,
    cost: SyntheticMonetaryInterval,
) -> tuple[float, float]:
    if benefit.unit != cost.unit:
        raise ValueError("benefit and cost units must match")
    # Interval subtraction must pair the unfavorable endpoints; subtracting
    # midpoints would silently collapse the synthetic uncertainty interval.
    return benefit.lower - cost.upper, benefit.upper - cost.lower


def _classify_value_of_information(
    horizon: DeferralHorizonResult,
    net_lower: float,
    net_upper: float,
) -> ValueOfInformationClassification:
    if horizon.lower_year is None and horizon.upper_year is None:
        return ValueOfInformationClassification.NOT_APPLICABLE
    if net_lower > 0.0:
        return ValueOfInformationClassification.NET_POSITIVE
    if net_upper < 0.0:
        return ValueOfInformationClassification.NET_NEGATIVE
    return ValueOfInformationClassification.INDETERMINATE


def _core_interval(fuzzy_number: FuzzyNumber) -> tuple[float, float]:
    if isinstance(fuzzy_number, TrapezoidalFuzzyNumber):
        return fuzzy_number.core_left, fuzzy_number.core_right
    if isinstance(fuzzy_number, TriangularFuzzyNumber):
        return fuzzy_number.mode, fuzzy_number.mode
    if isinstance(fuzzy_number, PiecewiseLinearFuzzyNumber):
        return fuzzy_number.left[-1][0], fuzzy_number.right[0][0]
    raise TypeError("unsupported fuzzy number type")
