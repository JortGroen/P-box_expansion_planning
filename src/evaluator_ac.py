"""Tier-2 AC loading-trajectory scaffold.

The functions here define the boundary for future pandapower/TimeSeriesCPP AC
evaluators without running an AC solver. They convert already-computed
decision-transformer P/Q trajectories into the shared IC-2 loading trajectory
contract used by output-error propagation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from numbers import Integral
from types import MappingProxyType
from typing import Literal, Mapping, Sequence

import numpy as np

from src.contracts.loading_trajectory import TimeDomain, validate_loading_trajectory_result
from src.evaluator_sum import DEFAULT_MIN_CONSECUTIVE_STEPS, DEFAULT_THRESHOLD_PU


ACBackend = Literal["pandapower", "timeseriescpp", "synthetic"]
CapacityConvention = Literal["total_nameplate", "firm_n_minus_1", "custom"]


@dataclass(frozen=True)
class TransformerCapacityMetadata:
    """Transformer denominator provenance for one AC loading trajectory.

    Parameters
    ----------
    s_nom_agg_kva:
        Aggregate capacity denominator in kVA for p.u. loading.
    convention:
        Nameplate convention used by the caller. The project has not selected
        total versus firm capacity for final analysis.
    transformer_indices:
        pandapower transformer element indices represented by the denominator.
    unit_nameplate_kva:
        Per-unit transformer nameplates in kVA.
    """

    s_nom_agg_kva: float
    convention: CapacityConvention
    transformer_indices: tuple[int, ...]
    unit_nameplate_kva: tuple[float, ...]

    def __post_init__(self) -> None:
        if not np.isfinite(float(self.s_nom_agg_kva)) or self.s_nom_agg_kva <= 0.0:
            raise ValueError("s_nom_agg_kva must be finite and positive")
        if self.convention not in {"total_nameplate", "firm_n_minus_1", "custom"}:
            raise ValueError("convention must be a supported capacity convention")
        if not self.transformer_indices:
            raise ValueError("transformer_indices must not be empty")
        if len(set(self.transformer_indices)) != len(self.transformer_indices):
            raise ValueError("transformer_indices must not contain duplicates")
        if len(self.transformer_indices) != len(self.unit_nameplate_kva):
            raise ValueError("unit_nameplate_kva must match transformer_indices")
        normalized_indices = tuple(
            _as_nonnegative_integer(index, name="transformer_indices") for index in self.transformer_indices
        )
        for nameplate in self.unit_nameplate_kva:
            if not np.isfinite(float(nameplate)) or nameplate <= 0.0:
                raise ValueError("unit_nameplate_kva values must be finite and positive")
        object.__setattr__(self, "s_nom_agg_kva", float(self.s_nom_agg_kva))
        object.__setattr__(self, "transformer_indices", normalized_indices)
        object.__setattr__(self, "unit_nameplate_kva", tuple(float(value) for value in self.unit_nameplate_kva))

    def manifest_metadata(self) -> dict[str, object]:
        """Return JSON-manifestable capacity metadata."""

        return {
            "s_nom_agg_kva": self.s_nom_agg_kva,
            "convention": self.convention,
            "transformer_indices": list(self.transformer_indices),
            "unit_nameplate_kva": list(self.unit_nameplate_kva),
        }


@dataclass(frozen=True)
class ACEvaluatorProvenance:
    """Manifestable identity for a future AC evaluator run."""

    backend: ACBackend
    network_id: str
    solver: str
    run_id: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.backend not in {"pandapower", "timeseriescpp", "synthetic"}:
            raise ValueError("backend must be 'pandapower', 'timeseriescpp', or 'synthetic'")
        for value, name in (
            (self.network_id, "network_id"),
            (self.solver, "solver"),
            (self.run_id, "run_id"),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def manifest_metadata(self) -> dict[str, object]:
        """Return JSON-manifestable AC run provenance."""

        return {
            "backend": self.backend,
            "network_id": self.network_id,
            "solver": self.solver,
            "run_id": self.run_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TransformerPQSeries:
    """Solved AC P/Q trajectory for one decision transformer."""

    transformer_index: int
    p_kw: Sequence[float] | np.ndarray
    q_kvar: Sequence[float] | np.ndarray
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        transformer_index = _as_nonnegative_integer(self.transformer_index, name="transformer_index")
        p = _as_vector(self.p_kw, name="p_kw")
        q = _as_vector(self.q_kvar, name="q_kvar")
        if p.shape != q.shape:
            raise ValueError("p_kw and q_kvar must have identical shapes")
        object.__setattr__(self, "transformer_index", transformer_index)
        object.__setattr__(self, "p_kw", p)
        object.__setattr__(self, "q_kvar", q)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def manifest_metadata(self) -> dict[str, object]:
        """Return non-result transformer-series metadata for manifests."""

        return {
            "transformer_index": self.transformer_index,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ACLoadingTrajectory:
    """AC/Tier-2 trajectory payload satisfying ``LoadingTrajectoryResult``."""

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
    timestamps: np.ndarray
    timestep_s: int
    capacity: TransformerCapacityMetadata
    provenance: ACEvaluatorProvenance

    def manifest_metadata(self) -> dict[str, object]:
        """Return non-result metadata suitable for runner manifests."""

        return {
            "time_domain": self.time_domain,
            "primary_probability_domain": self.primary_probability_domain,
            "timestep_s": self.timestep_s,
            "threshold_pu": self.threshold_pu,
            "min_consecutive_steps": self.min_consecutive_steps,
            "capacity": self.capacity.manifest_metadata(),
            "provenance": self.provenance.manifest_metadata(),
        }


def build_ac_loading_trajectory_from_transformer_series(
    transformer_series: Sequence[TransformerPQSeries],
    *,
    timestamps: Sequence[np.datetime64] | np.ndarray,
    capacity: TransformerCapacityMetadata,
    provenance: ACEvaluatorProvenance,
    time_domain: TimeDomain = "full_year",
    threshold_pu: float = DEFAULT_THRESHOLD_PU,
    min_consecutive_steps: int = DEFAULT_MIN_CONSECUTIVE_STEPS,
) -> ACLoadingTrajectory:
    """Materialize solved transformer P/Q result series into the AC contract.

    The input series are deterministic pandapower-like result fixtures: one P/Q
    trajectory per decision transformer after an AC solve has already happened.
    This helper sums transformer P and Q only; it does not run a power flow,
    classify events, or compare Tier-1 against AC.
    """

    series_tuple = tuple(transformer_series)
    if not series_tuple:
        raise ValueError("transformer_series must not be empty")

    expected_indices = set(capacity.transformer_indices)
    seen_indices: list[int] = []
    p_arrays: list[np.ndarray] = []
    q_arrays: list[np.ndarray] = []
    for series in series_tuple:
        if series.transformer_index in seen_indices:
            raise ValueError("transformer_series must not contain duplicate transformer_index values")
        seen_indices.append(series.transformer_index)
        p_arrays.append(np.asarray(series.p_kw, dtype=float))
        q_arrays.append(np.asarray(series.q_kvar, dtype=float))

    seen_set = set(seen_indices)
    if seen_set != expected_indices:
        missing = sorted(expected_indices - seen_set)
        extra = sorted(seen_set - expected_indices)
        raise ValueError(
            "transformer_series indices must match capacity transformer_indices "
            f"(missing={missing}, extra={extra})"
        )
    if any(array.shape != p_arrays[0].shape for array in (*p_arrays, *q_arrays)):
        raise ValueError("all transformer P/Q series must have identical shapes")

    timestamp_array = _as_15_minute_calendar(timestamps)
    if timestamp_array.shape != p_arrays[0].shape:
        raise ValueError("timestamps must match transformer P/Q series")

    # Denominator provenance must travel with the exact transformer set whose
    # solved P/Q outputs are summed; otherwise G2 can compare unlike assets.
    materialization_metadata = {
        "source": "pandapower_transformer_pq_series",
        "transformer_indices": list(capacity.transformer_indices),
        "series": [series.manifest_metadata() for series in series_tuple],
    }
    enriched_metadata = dict(provenance.metadata)
    enriched_metadata["transformer_result_materialization"] = materialization_metadata
    enriched_provenance = ACEvaluatorProvenance(
        backend=provenance.backend,
        network_id=provenance.network_id,
        solver=provenance.solver,
        run_id=provenance.run_id,
        metadata=enriched_metadata,
    )

    return build_ac_loading_trajectory(
        np.sum(np.vstack(p_arrays), axis=0),
        np.sum(np.vstack(q_arrays), axis=0),
        timestamps=timestamp_array,
        capacity=capacity,
        provenance=enriched_provenance,
        time_domain=time_domain,
        threshold_pu=threshold_pu,
        min_consecutive_steps=min_consecutive_steps,
    )


def build_ac_loading_trajectory(
    p_net_kw: Sequence[float] | np.ndarray,
    q_net_kvar: Sequence[float] | np.ndarray,
    *,
    timestamps: Sequence[np.datetime64] | np.ndarray,
    capacity: TransformerCapacityMetadata,
    provenance: ACEvaluatorProvenance,
    time_domain: TimeDomain = "full_year",
    threshold_pu: float = DEFAULT_THRESHOLD_PU,
    min_consecutive_steps: int = DEFAULT_MIN_CONSECUTIVE_STEPS,
) -> ACLoadingTrajectory:
    """Build an IC-2-compatible AC loading trajectory from solved P/Q outputs.

    The threshold and persistence fields are carried only because the shared
    loading-trajectory contract requires them. This scaffold does not classify
    events, count episodes, run threshold strata, or compare Tier-1 and AC.
    """

    p = _as_vector(p_net_kw, name="p_net_kw")
    q = _as_vector(q_net_kvar, name="q_net_kvar")
    if p.shape != q.shape:
        raise ValueError("p_net_kw and q_net_kvar must have identical shapes")
    timestamp_array = _as_15_minute_calendar(timestamps)
    if timestamp_array.shape != p.shape:
        raise ValueError("timestamps must match p_net_kw and q_net_kvar")
    if time_domain not in {"full_year", "window_set"}:
        raise ValueError("time_domain must be 'full_year' or 'window_set'")
    if not np.isfinite(float(threshold_pu)) or threshold_pu < 0.0:
        raise ValueError("threshold_pu must be finite and nonnegative")
    if isinstance(min_consecutive_steps, bool) or not isinstance(min_consecutive_steps, int):
        raise TypeError("min_consecutive_steps must be an integer")
    if min_consecutive_steps <= 0:
        raise ValueError("min_consecutive_steps must be positive")

    s_net_kva = np.hypot(p, q)
    screening_loading_pu = s_net_kva / capacity.s_nom_agg_kva
    import_mask = p > 0.0
    export_mask = p < 0.0
    zero_mask = p == 0.0
    result = ACLoadingTrajectory(
        p_net_kw=p,
        q_net_kvar=q,
        s_net_kva=s_net_kva,
        screening_loading_pu=screening_loading_pu,
        import_loading_pu=np.where(import_mask, screening_loading_pu, 0.0),
        export_loading_pu=np.where(export_mask, screening_loading_pu, 0.0),
        import_mask=import_mask,
        export_mask=export_mask,
        zero_mask=zero_mask,
        time_domain=time_domain,
        primary_probability_domain=time_domain == "full_year",
        threshold_pu=float(threshold_pu),
        min_consecutive_steps=int(min_consecutive_steps),
        timestamps=timestamp_array,
        timestep_s=900,
        capacity=capacity,
        provenance=provenance,
    )
    validate_loading_trajectory_result(result)
    return result


def _as_vector(values: Sequence[float] | np.ndarray, *, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional array")
    if array.size == 0:
        raise ValueError(f"{name} must not be empty")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _as_nonnegative_integer(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must contain exact nonnegative integers")
    integer = int(value)
    if integer < 0:
        raise ValueError(f"{name} must contain exact nonnegative integers")
    return integer


def _as_15_minute_calendar(values: Sequence[np.datetime64] | np.ndarray) -> np.ndarray:
    timestamps = np.asarray(values)
    if timestamps.ndim != 1:
        raise ValueError("timestamps must be a one-dimensional array")
    if timestamps.size == 0:
        raise ValueError("timestamps must not be empty")
    if not np.issubdtype(timestamps.dtype, np.datetime64):
        raise TypeError("timestamps must use numpy.datetime64 values")
    if np.isnat(timestamps).any():
        raise ValueError("timestamps must not contain NaT")
    if timestamps.size > 1:
        cadence_s = np.diff(timestamps).astype("timedelta64[s]").astype(np.int64)
        # E5-S3-T1 records the four-step one-hour interpretation against 900 s data.
        if not np.all(cadence_s == 900):
            raise ValueError("timestamps must use a complete 900-second cadence")
    return timestamps.astype("datetime64[s]")
