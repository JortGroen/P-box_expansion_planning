"""Shared IC-2 loading-trajectory contract and validator.

The protocol is structural so existing Tier-1 results and a future AC/Tier-2
result can satisfy the same boundary without inheriting from a common class.
"""

from __future__ import annotations

from typing import Literal, Protocol

import numpy as np


TimeDomain = Literal["full_year", "window_set"]
VALID_TIME_DOMAINS: frozenset[str] = frozenset(("full_year", "window_set"))


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
