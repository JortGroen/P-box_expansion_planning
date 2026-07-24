"""Shared IC-2 loading-trajectory contract and validator.

The protocol is structural so existing Tier-1 results and a future AC/Tier-2
result can satisfy the same boundary without inheriting from a common class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, Sequence

import numpy as np


TimeDomain = Literal["full_year", "window_set"]
PreRunPurpose = Literal["e3_s2b_future_layer_screen", "e3_s3_tier2_ac_validation"]
VALID_TIME_DOMAINS: frozenset[str] = frozenset(("full_year", "window_set"))
VALID_PRERUN_PURPOSES: frozenset[str] = frozenset(
    ("e3_s2b_future_layer_screen", "e3_s3_tier2_ac_validation")
)
G0_A3_PRIMARY_THRESHOLD_PU = 1.0
G0_A3_SENSITIVITY_THRESHOLDS_PU: tuple[float, ...] = (1.1, 1.2)
G0_A3_MIN_CONSECUTIVE_STEPS = 4
IC_TIMESTEP_SECONDS = 900


class LoadingTrajectoryResult(Protocol):
    """Common IC-2 trajectory payload consumed by output-error propagation.

    Attributes
    ----------
    p_net_kw:
        Unwidened aggregate net active power in kW. Positive is import and
        negative is export.
    q_net_kvar:
        Unwidened aggregate net reactive power in kvar.
    s_net_kva:
        Apparent-power magnitude ``hypot(p_net_kw, q_net_kvar)`` in kVA.
    screening_loading_pu:
        Direction-agnostic loading in p.u. of the selected transformer
        denominator.
    import_loading_pu, export_loading_pu:
        Diagnostic direction-gated loadings derived from screening loading and
        the unwidened active-power sign.
    import_mask, export_mask, zero_mask:
        Mutually exclusive and complete direction masks from the unwidened
        active-power sign.
    time_domain:
        ``"full_year"`` for primary probability evaluation or ``"window_set"``
        for validation/diagnostic domains only.
    primary_probability_domain:
        True exactly when ``time_domain == "full_year"``.
    threshold_pu:
        Strict p.u. event threshold used by the producer.
    min_consecutive_steps:
        Positive event-persistence length in timesteps.
    """

    p_net_kw: np.ndarray
    q_net_kvar: np.ndarray
    s_net_kva: np.ndarray
    screening_loading_pu: np.ndarray
    import_loading_pu: np.ndarray
    export_loading_pu: np.ndarray
    import_mask: np.ndarray
    export_mask: np.ndarray
    zero_mask: np.ndarray
    time_domain: TimeDomain
    primary_probability_domain: bool
    threshold_pu: float
    min_consecutive_steps: int


@dataclass(frozen=True)
class LoadingTrajectoryPreRunConfig:
    """Manifestable dry-run configuration for later E3.S2b/E3.S3 setup.

    The config carries governed event metadata so future runner manifests can be
    wired consistently, but fixture validation below deliberately refuses to
    classify events or accept primary full-year payloads in this scaffold.
    """

    config_id: str
    purpose: PreRunPurpose
    planning_years: tuple[int, ...] = (2030, 2033, 2035)
    fixture_time_domain: TimeDomain = "window_set"
    timestep_seconds: int = IC_TIMESTEP_SECONDS
    governed_threshold_pu: float = G0_A3_PRIMARY_THRESHOLD_PU
    sensitivity_thresholds_pu: tuple[float, ...] = G0_A3_SENSITIVITY_THRESHOLDS_PU
    min_consecutive_steps: int = G0_A3_MIN_CONSECUTIVE_STEPS
    capacity_convention_status: str = "pending_g1_a2_e3_s2b"
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_nonempty_text(self.config_id, name="config_id")
        if self.purpose not in VALID_PRERUN_PURPOSES:
            raise ValueError("purpose must be a supported E3.S2b/E3.S3 pre-run purpose")
        if self.fixture_time_domain != "window_set":
            raise ValueError("pre-run fixtures must stay in the non-primary window_set domain")
        if (
            isinstance(self.timestep_seconds, bool)
            or not isinstance(self.timestep_seconds, int)
            or self.timestep_seconds != IC_TIMESTEP_SECONDS
        ):
            raise ValueError("timestep_seconds must be the 900-second IC cadence")
        _validate_planning_years(self.planning_years)
        if float(self.governed_threshold_pu) != G0_A3_PRIMARY_THRESHOLD_PU:
            raise ValueError("governed_threshold_pu must match approved G0-A3 primary metadata")
        if tuple(float(value) for value in self.sensitivity_thresholds_pu) != G0_A3_SENSITIVITY_THRESHOLDS_PU:
            raise ValueError("sensitivity_thresholds_pu must match approved G0-A3 sensitivity metadata")
        if self.min_consecutive_steps != G0_A3_MIN_CONSECUTIVE_STEPS:
            raise ValueError("min_consecutive_steps must match approved G0-A3 persistence metadata")
        if self.capacity_convention_status != "pending_g1_a2_e3_s2b":
            raise ValueError("capacity_convention_status must remain pending until the governed screen")
        _validate_metadata_mapping(self.metadata, name="metadata")
        object.__setattr__(self, "planning_years", tuple(self.planning_years))
        object.__setattr__(self, "timestep_seconds", int(self.timestep_seconds))
        object.__setattr__(self, "governed_threshold_pu", float(self.governed_threshold_pu))
        object.__setattr__(self, "sensitivity_thresholds_pu", tuple(float(v) for v in self.sensitivity_thresholds_pu))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def manifest_record(self) -> dict[str, object]:
        """Return array-free metadata for pre-run runner manifests."""

        return {
            "config_id": self.config_id,
            "purpose": self.purpose,
            "planning_years": self.planning_years,
            "fixture_time_domain": self.fixture_time_domain,
            "timestep_seconds": self.timestep_seconds,
            "governed_event_metadata": {
                "basis": "G0-A3",
                "primary_threshold_pu": self.governed_threshold_pu,
                "strict_import_loading_gt_threshold": True,
                "sensitivity_thresholds_pu": self.sensitivity_thresholds_pu,
                "min_consecutive_15_minute_steps": self.min_consecutive_steps,
                "not_evaluated_here": True,
            },
            "capacity_convention_status": self.capacity_convention_status,
            "metadata": dict(self.metadata),
        }


def prepare_loading_trajectory_prerun_manifest(
    config: LoadingTrajectoryPreRunConfig,
    fixtures: Sequence[LoadingTrajectoryResult],
) -> dict[str, object]:
    """Validate synthetic trajectory fixtures for later pre-run wiring.

    This helper is for configuration readiness only. It validates the shared
    trajectory shape/direction contract and emits array-free fixture metadata;
    it does not count overload episodes, estimate probabilities, compare tiers,
    or choose a capacity convention.
    """

    if not fixtures:
        raise ValueError("fixtures must not be empty")
    fixture_records: list[dict[str, object]] = []
    for index, fixture in enumerate(fixtures):
        validate_loading_trajectory_result(fixture)
        if fixture.time_domain != config.fixture_time_domain:
            raise ValueError("pre-run fixtures must use the configured non-primary time_domain")
        if fixture.primary_probability_domain:
            raise ValueError("pre-run fixtures must not be primary_probability_domain payloads")
        if hasattr(fixture, "overload"):
            raise ValueError("pre-run fixtures must not include legacy boolean overload results")
        if float(fixture.threshold_pu) != config.governed_threshold_pu:
            raise ValueError("fixture threshold_pu must match governed pre-run metadata")
        if fixture.min_consecutive_steps != config.min_consecutive_steps:
            raise ValueError("fixture min_consecutive_steps must match governed pre-run metadata")
        fixture_records.append(
            {
                "fixture_index": index,
                "time_domain": fixture.time_domain,
                "primary_probability_domain": fixture.primary_probability_domain,
                "timestep_count": int(np.asarray(fixture.p_net_kw).size),
                "direction_step_counts": {
                    "import": int(np.count_nonzero(fixture.import_mask)),
                    "export": int(np.count_nonzero(fixture.export_mask)),
                    "zero": int(np.count_nonzero(fixture.zero_mask)),
                },
                "threshold_metadata_only": True,
            }
        )

    # The explicit guard flags keep this manifest usable for runner wiring while
    # preventing a synthetic fixture packet from being mistaken for G2 evidence.
    return {
        "dry_run_only": True,
        "synthetic_fixtures_only": True,
        "no_real_net_load_arrays": True,
        "no_event_detection": True,
        "no_probability_estimate": True,
        "no_capacity_screen_result": True,
        "no_tier_comparison": True,
        "config_manifest": config.manifest_record(),
        "fixture_count": len(fixture_records),
        "fixtures": fixture_records,
    }


def validate_loading_trajectory_result(result: LoadingTrajectoryResult) -> None:
    """Validate a loading-trajectory result against the approved IC-2 boundary."""

    p_net_kw = _as_vector(result.p_net_kw, name="p_net_kw")
    q_net_kvar = _as_vector(result.q_net_kvar, name="q_net_kvar")
    s_net_kva = _as_vector(result.s_net_kva, name="s_net_kva")
    screening_loading_pu = _as_vector(result.screening_loading_pu, name="screening_loading_pu")
    import_loading_pu = _as_vector(result.import_loading_pu, name="import_loading_pu")
    export_loading_pu = _as_vector(result.export_loading_pu, name="export_loading_pu")
    import_mask = _as_bool_vector(result.import_mask, name="import_mask")
    export_mask = _as_bool_vector(result.export_mask, name="export_mask")
    zero_mask = _as_bool_vector(result.zero_mask, name="zero_mask")

    arrays = (
        q_net_kvar,
        s_net_kva,
        screening_loading_pu,
        import_loading_pu,
        export_loading_pu,
        import_mask,
        export_mask,
        zero_mask,
    )
    if p_net_kw.size == 0:
        raise ValueError("loading trajectories must not be empty")
    if any(array.shape != p_net_kw.shape for array in arrays):
        raise ValueError("all loading trajectories and masks must have identical shapes")

    expected_s = np.hypot(p_net_kw, q_net_kvar)
    if not np.allclose(s_net_kva, expected_s, rtol=1e-9, atol=1e-9):
        raise ValueError("s_net_kva must equal hypot(p_net_kw, q_net_kvar)")
    if np.any(screening_loading_pu < 0.0):
        raise ValueError("screening_loading_pu must be nonnegative")

    expected_import = p_net_kw > 0.0
    expected_export = p_net_kw < 0.0
    expected_zero = p_net_kw == 0.0
    if not np.array_equal(import_mask, expected_import):
        raise ValueError("import_mask must match p_net_kw > 0")
    if not np.array_equal(export_mask, expected_export):
        raise ValueError("export_mask must match p_net_kw < 0")
    if not np.array_equal(zero_mask, expected_zero):
        raise ValueError("zero_mask must match p_net_kw == 0")

    mask_count = import_mask.astype(int) + export_mask.astype(int) + zero_mask.astype(int)
    if not np.array_equal(mask_count, np.ones_like(mask_count)):
        raise ValueError("direction masks must be mutually exclusive and collectively complete")

    # IC-3 widens loading magnitudes only; direction remains the unwidened P-net sign.
    expected_import_loading = np.where(import_mask, screening_loading_pu, 0.0)
    expected_export_loading = np.where(export_mask, screening_loading_pu, 0.0)
    if not np.allclose(import_loading_pu, expected_import_loading, rtol=1e-12, atol=1e-12):
        raise ValueError("import_loading_pu must equal screening loading on import steps and zero elsewhere")
    if not np.allclose(export_loading_pu, expected_export_loading, rtol=1e-12, atol=1e-12):
        raise ValueError("export_loading_pu must equal screening loading on export steps and zero elsewhere")

    _validate_threshold_and_persistence(
        threshold_pu=result.threshold_pu,
        min_consecutive_steps=result.min_consecutive_steps,
    )
    _validate_time_domain(
        time_domain=result.time_domain,
        primary_probability_domain=result.primary_probability_domain,
    )



def _validate_planning_years(values: tuple[int, ...]) -> None:
    if not values:
        raise ValueError("planning_years must not be empty")
    years: list[int] = []
    for year in values:
        if isinstance(year, bool) or not isinstance(year, int) or year <= 0:
            raise ValueError("planning_years must contain positive integers")
        years.append(year)
    if len(set(years)) != len(years):
        raise ValueError("planning_years must not contain duplicates")
    if 2035 not in years:
        raise ValueError("planning_years must include the G0-A4 primary planning year 2035")


def _require_nonempty_text(value: str, *, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _validate_metadata_mapping(mapping: Mapping[str, object], *, name: str) -> None:
    for key, value in mapping.items():
        _require_nonempty_text(key, name=f"{name} key")
        if value is None:
            raise ValueError(f"{name} values must not be None")
        if isinstance(value, str) and not value:
            raise ValueError(f"{name} string values must be non-empty")


def _as_vector(values: np.ndarray, *, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional array")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _as_bool_vector(values: np.ndarray, *, name: str) -> np.ndarray:
    array = np.asarray(values)
    if array.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional array")
    if array.dtype != np.bool_:
        raise ValueError(f"{name} must be a boolean array")
    return array


def _validate_threshold_and_persistence(
    *,
    threshold_pu: float,
    min_consecutive_steps: int,
) -> None:
    threshold = float(threshold_pu)
    if not np.isfinite(threshold) or threshold < 0.0:
        raise ValueError("threshold_pu must be finite and nonnegative")
    if isinstance(min_consecutive_steps, bool) or not isinstance(min_consecutive_steps, int):
        raise TypeError("min_consecutive_steps must be an integer")
    if min_consecutive_steps <= 0:
        raise ValueError("min_consecutive_steps must be positive")


def _validate_time_domain(
    *,
    time_domain: str,
    primary_probability_domain: bool,
) -> None:
    if time_domain not in VALID_TIME_DOMAINS:
        raise ValueError("time_domain must be 'full_year' or 'window_set'")
    if not isinstance(primary_probability_domain, bool):
        raise TypeError("primary_probability_domain must be a bool")
    expected_primary = time_domain == "full_year"
    if primary_probability_domain is not expected_primary:
        raise ValueError("primary_probability_domain must equal (time_domain == 'full_year')")
