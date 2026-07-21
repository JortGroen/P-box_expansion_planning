"""Flexibility aggregation scaffold for aligned 15-minute net-load components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence

import numpy as np


ReboundMode = Literal["none", "shift_to_adjacent"]
DEFAULT_TIMESTEP_HOURS = 0.25


@dataclass(frozen=True)
class FlexComponent:
    """One aligned component trajectory in kW.

    Parameters
    ----------
    name:
        Stable component identifier for metadata and manifests.
    p_kw:
        One-dimensional 15-minute active-power trajectory in kW. Positive
        values are demand/import contributions; negative values are export.
    controllable_fraction:
        Fraction of positive demand eligible for flexibility before applying
        controllability ``rho``.
    is_import_controllable:
        True only for demand-side controllable load components. PV/export
        components must leave this false.
    component_type:
        Informational component type, such as ``"ev"``, ``"heat_pump"``,
        ``"baseline"``, or ``"pv"``.
    node_id:
        Optional node identifier preserved in metadata.
    timestamps:
        Optional complete timestamp sequence. When supplied, all components
        must carry the identical sequence.
    """

    name: str
    p_kw: Sequence[float] | np.ndarray
    controllable_fraction: float = 0.0
    is_import_controllable: bool = False
    component_type: str = "demand"
    node_id: str | int | None = None
    timestamps: Sequence[Any] | None = None


@dataclass(frozen=True)
class FlexComponentResult:
    """Adjusted component trajectory and audit metadata."""

    name: str
    component_type: str
    node_id: str | int | None
    original_p_kw: np.ndarray
    adjusted_p_kw: np.ndarray
    reduction_p_kw: np.ndarray
    rebound_p_kw: np.ndarray
    controllable_fraction: float
    eligible: bool
    reason: str
    reduction_kwh: float
    rebound_kwh: float
    timestamps: tuple[Any, ...] | None


@dataclass(frozen=True)
class FlexAggregationResult:
    """Aggregated original and adjusted trajectories with metadata."""

    rho: float
    rebound_mode: ReboundMode
    timestep_hours: float
    active_mask: np.ndarray
    component_results: tuple[FlexComponentResult, ...]
    aggregate_original_p_kw: np.ndarray
    aggregate_adjusted_p_kw: np.ndarray
    total_reduction_kwh: float
    total_rebound_kwh: float
    timestamps: tuple[Any, ...] | None


def apply_flexibility(
    components: Sequence[FlexComponent],
    *,
    rho: float,
    active_mask: Sequence[bool] | np.ndarray | None = None,
    rebound_mode: ReboundMode = "none",
    timestep_hours: float = DEFAULT_TIMESTEP_HOURS,
) -> FlexAggregationResult:
    """Apply controllability ``rho`` to eligible import-side demand components.

    Parameters
    ----------
    components:
        Aligned component trajectories in kW.
    rho:
        Controllability level in ``[0, 1]``.
    active_mask:
        Optional Boolean trajectory marking timesteps where flexibility may be
        activated. When omitted, all timesteps are eligible.
    rebound_mode:
        ``"none"`` applies pure demand reduction. ``"shift_to_adjacent"``
        shifts each reduced kWh to the next timestep, or the previous timestep
        for reductions at the final index.
    timestep_hours:
        Duration represented by each trajectory step in hours.
    """

    rho_value = _validate_unit_interval(rho, name="rho")
    timestep_hours_value = _validate_positive_float(timestep_hours, name="timestep_hours")
    if rebound_mode not in ("none", "shift_to_adjacent"):
        raise ValueError("rebound_mode must be 'none' or 'shift_to_adjacent'")
    if not components:
        raise ValueError("components must not be empty")

    prepared = [_prepare_component(component) for component in components]
    length = prepared[0].p_kw.size
    timestamps = _validate_alignment(prepared)
    mask = _prepare_active_mask(active_mask, length=length)

    component_results = tuple(
        _apply_component_flexibility(
            component,
            rho=rho_value,
            active_mask=mask,
            rebound_mode=rebound_mode,
            timestep_hours=timestep_hours_value,
        )
        for component in prepared
    )
    aggregate_original = np.sum([item.original_p_kw for item in component_results], axis=0)
    aggregate_adjusted = np.sum([item.adjusted_p_kw for item in component_results], axis=0)
    return FlexAggregationResult(
        rho=rho_value,
        rebound_mode=rebound_mode,
        timestep_hours=timestep_hours_value,
        active_mask=mask.copy(),
        component_results=component_results,
        aggregate_original_p_kw=aggregate_original,
        aggregate_adjusted_p_kw=aggregate_adjusted,
        total_reduction_kwh=float(sum(item.reduction_kwh for item in component_results)),
        total_rebound_kwh=float(sum(item.rebound_kwh for item in component_results)),
        timestamps=timestamps,
    )


@dataclass(frozen=True)
class _PreparedComponent:
    name: str
    p_kw: np.ndarray
    controllable_fraction: float
    is_import_controllable: bool
    component_type: str
    node_id: str | int | None
    timestamps: tuple[Any, ...] | None


def _apply_component_flexibility(
    component: _PreparedComponent,
    *,
    rho: float,
    active_mask: np.ndarray,
    rebound_mode: ReboundMode,
    timestep_hours: float,
) -> FlexComponentResult:
    eligible, reason = _eligibility(component)
    reduction = np.zeros_like(component.p_kw)
    if eligible:
        # Only positive demand is reduced; negative PV/export must remain a side diagnostic.
        reduction = np.where(
            active_mask & (component.p_kw > 0.0),
            component.p_kw * component.controllable_fraction * rho,
            0.0,
        )

    rebound = _compute_rebound(reduction, mode=rebound_mode)
    adjusted = component.p_kw - reduction + rebound
    return FlexComponentResult(
        name=component.name,
        component_type=component.component_type,
        node_id=component.node_id,
        original_p_kw=component.p_kw.copy(),
        adjusted_p_kw=adjusted,
        reduction_p_kw=reduction,
        rebound_p_kw=rebound,
        controllable_fraction=component.controllable_fraction,
        eligible=eligible,
        reason=reason,
        reduction_kwh=float(np.sum(reduction) * timestep_hours),
        rebound_kwh=float(np.sum(rebound) * timestep_hours),
        timestamps=component.timestamps,
    )


def _compute_rebound(reduction: np.ndarray, *, mode: ReboundMode) -> np.ndarray:
    rebound = np.zeros_like(reduction)
    if mode == "none" or not np.any(reduction):
        return rebound
    if reduction.size < 2:
        raise ValueError("shift_to_adjacent rebound requires at least two timesteps")
    for index, value in enumerate(reduction):
        if value == 0.0:
            continue
        target = index + 1 if index + 1 < reduction.size else index - 1
        rebound[target] += value
    return rebound


def _eligibility(component: _PreparedComponent) -> tuple[bool, str]:
    if not component.is_import_controllable:
        return False, "not marked as import-side controllable demand"
    if component.controllable_fraction == 0.0:
        return False, "zero controllable fraction"
    return True, "reduced positive import demand by controllable_fraction * rho during active steps"


def _prepare_component(component: FlexComponent) -> _PreparedComponent:
    if not component.name:
        raise ValueError("component name must not be empty")
    p_kw = np.asarray(component.p_kw, dtype=float)
    if p_kw.ndim != 1:
        raise ValueError(f"{component.name}: p_kw must be one-dimensional")
    if p_kw.size == 0:
        raise ValueError(f"{component.name}: p_kw must not be empty")
    if not np.isfinite(p_kw).all():
        raise ValueError(f"{component.name}: p_kw must contain only finite values")
    controllable_fraction = _validate_unit_interval(
        component.controllable_fraction,
        name=f"{component.name}: controllable_fraction",
    )
    timestamps = tuple(component.timestamps) if component.timestamps is not None else None
    if timestamps is not None and len(timestamps) != p_kw.size:
        raise ValueError(f"{component.name}: timestamps length must match p_kw")
    return _PreparedComponent(
        name=component.name,
        p_kw=p_kw.copy(),
        controllable_fraction=controllable_fraction,
        is_import_controllable=bool(component.is_import_controllable),
        component_type=component.component_type,
        node_id=component.node_id,
        timestamps=timestamps,
    )


def _validate_alignment(components: Sequence[_PreparedComponent]) -> tuple[Any, ...] | None:
    length = components[0].p_kw.size
    first_timestamps = components[0].timestamps
    for component in components[1:]:
        if component.p_kw.size != length:
            raise ValueError("all component trajectories must have identical length")
        if component.timestamps != first_timestamps:
            raise ValueError("all component timestamps must be identical when supplied")
    return first_timestamps


def _prepare_active_mask(active_mask: Sequence[bool] | np.ndarray | None, *, length: int) -> np.ndarray:
    if active_mask is None:
        return np.ones(length, dtype=bool)
    mask = np.asarray(active_mask)
    if mask.ndim != 1:
        raise ValueError("active_mask must be one-dimensional")
    if mask.size != length:
        raise ValueError("active_mask length must match component trajectories")
    if mask.dtype != np.bool_:
        raise ValueError("active_mask must be a boolean array")
    return mask.copy()


def _validate_unit_interval(value: float, *, name: str) -> float:
    value_float = float(value)
    if not np.isfinite(value_float) or not 0.0 <= value_float <= 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return value_float


def _validate_positive_float(value: float, *, name: str) -> float:
    value_float = float(value)
    if not np.isfinite(value_float) or value_float <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return value_float
