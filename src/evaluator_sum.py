"""Tier-1 radial summation evaluator for IC-2.

The evaluator implements the approved G0/G0-A1/G0-A2/G0-A3 event semantics for the
fast Monte Carlo inner loop. It preserves the unwidened active-power direction
gate so later model-error envelopes can widen loading trajectories before
episode detection without turning export or zero-flow steps into import events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from src.contracts.loading_trajectory import TimeDomain, validate_loading_trajectory_result
from src.contracts.net_load import NetLoadResult, validate_net_load_result

# G0-A3 makes 1.0 the primary executable default; 1.1/1.2 are
# predeclared sensitivities that callers must request explicitly.
DEFAULT_THRESHOLD_PU = 1.0
DEFAULT_MIN_CONSECUTIVE_STEPS = 4


@dataclass(frozen=True)
class Tier1Evaluation:
    """Tier-1 loading trajectories and G0-A1 event diagnostics.

    Parameters
    ----------
    p_net_kw:
        Aggregate downstream net active power in kW. Positive values denote
        import from the upstream grid into the modeled area.
    q_net_kvar:
        Aggregate downstream net reactive power in kvar.
    s_net_kva:
        Apparent-power magnitude ``sqrt(P_net^2 + Q_net^2)`` in kVA.
    screening_loading_pu:
        Direction-agnostic loading ``abs(S_net) / S_nom,agg`` in p.u.
    import_loading_pu:
        Apparent loading in p.u. where ``P_net > 0`` and zero otherwise.
    export_loading_pu:
        Apparent loading in p.u. where ``P_net < 0`` and zero otherwise.
    import_mask, export_mask, zero_mask:
        Direction masks from the unwidened ``P_net`` sign.
    overload:
        Whether the evaluated time domain contains at least one import episode
        above ``threshold_pu`` for ``min_consecutive_steps`` consecutive steps.
    overload_episode_count:
        Number of distinct import-direction episodes in the evaluated domain.
    longest_import_run_steps:
        Longest consecutive import-direction exceedance run.
    time_domain:
        ``"full_year"`` for primary E evaluation or ``"window_set"`` for
        validation/diagnostic subsets only.
    primary_probability_domain:
        True only when the evaluated domain is the full planning year.
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
    overload: bool
    overload_episode_count: int
    longest_import_run_steps: int
    time_domain: TimeDomain
    primary_probability_domain: bool
    threshold_pu: float
    min_consecutive_steps: int


def evaluate_tier1(
    nodal_p_kw: Sequence[Sequence[float]] | np.ndarray,
    nodal_q_kvar: Sequence[Sequence[float]] | np.ndarray,
    *,
    s_nom_agg_kva: float,
    parent_index: Sequence[int | None] | None = None,
    decision_node: int = 0,
    time_domain: TimeDomain = "full_year",
    window_indices: Sequence[int] | np.ndarray | None = None,
    threshold_pu: float = DEFAULT_THRESHOLD_PU,
    min_consecutive_steps: int = DEFAULT_MIN_CONSECUTIVE_STEPS,
) -> Tier1Evaluation:
    """Evaluate G0 import overload semantics from nodal net P/Q trajectories.

    Parameters
    ----------
    nodal_p_kw, nodal_q_kvar:
        Arrays with shape ``(nodes, timesteps)``. Positive active power is net
        demand/import contribution, and negative active power is net export.
    s_nom_agg_kva:
        Aggregate decision-transformer nameplate denominator in kVA. The caller
        chooses the total or firm convention; this function only applies it.
    parent_index:
        Optional radial topology. ``parent_index[i]`` is node ``i``'s parent
        toward the upstream source; use ``None`` or ``-1`` for the root.
        When omitted, all nodes are treated as downstream of the decision
        transformer and summed directly.
    decision_node:
        Node whose downstream subtree feeds the decision transformer.
    time_domain:
        ``"full_year"`` for primary annual evaluation or ``"window_set"`` for
        validation/diagnostic subsets.
    window_indices:
        Optional timestep positions to evaluate. Required when
        ``time_domain="window_set"`` and forbidden for ``"full_year"``.
    threshold_pu:
        Strict overload threshold in p.u.; G0-A3 primary uses ``> 1.0``.
    min_consecutive_steps:
        Minimum consecutive 15-minute import exceedance steps; G0 uses four.
    """

    p = _as_2d_float_array(nodal_p_kw, name="nodal_p_kw")
    q = _as_2d_float_array(nodal_q_kvar, name="nodal_q_kvar")
    _validate_inputs(
        p,
        q,
        s_nom_agg_kva=s_nom_agg_kva,
        threshold_pu=threshold_pu,
        min_consecutive_steps=min_consecutive_steps,
    )

    p_subtree = radial_downstream_sum(p, parent_index=parent_index)
    q_subtree = radial_downstream_sum(q, parent_index=parent_index)
    if not 0 <= decision_node < p_subtree.shape[0]:
        raise IndexError("decision_node is outside the nodal array")

    p_net = p_subtree[decision_node].copy()
    q_net = q_subtree[decision_node].copy()
    p_net, q_net = _select_time_domain(
        p_net,
        q_net,
        time_domain=time_domain,
        window_indices=window_indices,
    )

    s_net = np.hypot(p_net, q_net)
    screening_loading = s_net / float(s_nom_agg_kva)
    import_mask = p_net > 0.0
    export_mask = p_net < 0.0
    zero_mask = p_net == 0.0
    import_loading = np.where(import_mask, screening_loading, 0.0)
    export_loading = np.where(export_mask, screening_loading, 0.0)
    episodes, longest_run = count_import_overload_episodes(
        import_loading,
        threshold_pu=threshold_pu,
        min_consecutive_steps=min_consecutive_steps,
    )
    result = Tier1Evaluation(
        p_net_kw=p_net,
        q_net_kvar=q_net,
        s_net_kva=s_net,
        screening_loading_pu=screening_loading,
        import_loading_pu=import_loading,
        export_loading_pu=export_loading,
        import_mask=import_mask,
        export_mask=export_mask,
        zero_mask=zero_mask,
        overload=episodes > 0,
        overload_episode_count=episodes,
        longest_import_run_steps=longest_run,
        time_domain=time_domain,
        primary_probability_domain=time_domain == "full_year",
        threshold_pu=float(threshold_pu),
        min_consecutive_steps=int(min_consecutive_steps),
    )
    validate_loading_trajectory_result(result)
    return result


def evaluate_net_load_tier1(
    net_load: NetLoadResult,
    *,
    s_nom_agg_kva: float,
    parent_index: Sequence[int | None] | None = None,
    decision_node: int = 0,
    time_domain: TimeDomain = "full_year",
    window_indices: Sequence[int] | np.ndarray | None = None,
    threshold_pu: float = DEFAULT_THRESHOLD_PU,
    min_consecutive_steps: int = DEFAULT_MIN_CONSECUTIVE_STEPS,
) -> Tier1Evaluation:
    """Evaluate a validated IC-1 result through the Tier-1 IC-2 boundary.

    Parameters
    ----------
    net_load:
        Validated IC-1 aggregate nodal net-load result. Active and reactive
        power are in kW/kvar with shape ``(nodes, timesteps)``.
    s_nom_agg_kva:
        Aggregate transformer denominator in kVA. The caller supplies the
        total or firm convention; this helper only routes the IC-1 trajectories.
    parent_index, decision_node, time_domain, window_indices, threshold_pu,
    min_consecutive_steps:
        Passed through to :func:`evaluate_tier1`.
    """

    # Validate at the IC-1 edge so future real component adapters cannot bypass
    # common-calendar/provenance checks before producing an IC-2 trajectory.
    validate_net_load_result(net_load)
    return evaluate_tier1(
        net_load.p_net_kw,
        net_load.q_net_kvar,
        s_nom_agg_kva=s_nom_agg_kva,
        parent_index=parent_index,
        decision_node=decision_node,
        time_domain=time_domain,
        window_indices=window_indices,
        threshold_pu=threshold_pu,
        min_consecutive_steps=min_consecutive_steps,
    )


def radial_downstream_sum(
    nodal_values: Sequence[Sequence[float]] | np.ndarray,
    *,
    parent_index: Sequence[int | None] | None = None,
) -> np.ndarray:
    """Return downstream subtree sums for each radial node.

    Parameters
    ----------
    nodal_values:
        Array with shape ``(nodes, timesteps)`` in any physical unit.
    parent_index:
        Optional radial parent list. ``None`` means every node contributes only
        to the single aggregate row returned by direct summation.
    """

    values = _as_2d_float_array(nodal_values, name="nodal_values")
    if parent_index is None:
        return values.sum(axis=0, keepdims=True)

    parents = _normalise_parent_index(parent_index, node_count=values.shape[0])
    downstream = values.copy()
    for node in range(values.shape[0]):
        parent = parents[node]
        seen = {node}
        while parent is not None:
            if parent in seen:
                raise ValueError("parent_index contains a cycle")
            downstream[parent] += values[node]
            seen.add(parent)
            parent = parents[parent]
    return downstream


def count_import_overload_episodes(
    import_loading_pu: Sequence[float] | np.ndarray,
    *,
    threshold_pu: float = DEFAULT_THRESHOLD_PU,
    min_consecutive_steps: int = DEFAULT_MIN_CONSECUTIVE_STEPS,
) -> tuple[int, int]:
    """Count import overload episodes from a direction-gated loading series.

    Parameters
    ----------
    import_loading_pu:
        Loading in p.u. after applying the unwidened import mask. Export and
        zero-flow steps should therefore be zero.
    threshold_pu:
        Strict threshold in p.u.; values exactly equal to it do not qualify.
    min_consecutive_steps:
        Minimum consecutive qualifying steps for one episode.
    """

    if min_consecutive_steps <= 0:
        raise ValueError("min_consecutive_steps must be positive")

    episodes = 0
    run_length = 0
    longest_run = 0
    in_episode = False
    for value in np.asarray(import_loading_pu, dtype=float):
        if value > threshold_pu:
            run_length += 1
            longest_run = max(longest_run, run_length)
            if run_length >= min_consecutive_steps and not in_episode:
                episodes += 1
                in_episode = True
        else:
            run_length = 0
            in_episode = False
    return episodes, longest_run


def _validate_inputs(
    p: np.ndarray,
    q: np.ndarray,
    *,
    s_nom_agg_kva: float,
    threshold_pu: float,
    min_consecutive_steps: int,
) -> None:
    if p.shape != q.shape:
        raise ValueError("nodal_p_kw and nodal_q_kvar must have the same shape")
    if p.shape[0] == 0 or p.shape[1] == 0:
        raise ValueError("nodal arrays must contain at least one node and timestep")
    if s_nom_agg_kva <= 0:
        raise ValueError("s_nom_agg_kva must be positive")
    if threshold_pu < 0:
        raise ValueError("threshold_pu must be nonnegative")
    if min_consecutive_steps <= 0:
        raise ValueError("min_consecutive_steps must be positive")


def _select_time_domain(
    p_net: np.ndarray,
    q_net: np.ndarray,
    *,
    time_domain: TimeDomain,
    window_indices: Sequence[int] | np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray]:
    if time_domain == "full_year":
        if window_indices is not None:
            raise ValueError("window_indices are only allowed for time_domain='window_set'")
        return p_net, q_net
    if time_domain == "window_set":
        if window_indices is None:
            raise ValueError("window_indices are required for time_domain='window_set'")
        indices = np.asarray(window_indices, dtype=int)
        if indices.ndim != 1:
            raise ValueError("window_indices must be one-dimensional")
        if len(indices) == 0:
            raise ValueError("window_indices must not be empty")
        if np.any(indices < 0) or np.any(indices >= len(p_net)):
            raise IndexError("window_indices contain a timestep outside the series")
        return p_net[indices], q_net[indices]
    raise ValueError("time_domain must be 'full_year' or 'window_set'")


def _normalise_parent_index(
    parent_index: Sequence[int | None],
    *,
    node_count: int,
) -> tuple[int | None, ...]:
    if len(parent_index) != node_count:
        raise ValueError("parent_index length must match node count")
    parents: list[int | None] = []
    for node, parent in enumerate(parent_index):
        if parent is None or int(parent) == -1:
            parents.append(None)
            continue
        parent_int = int(parent)
        if parent_int == node:
            raise ValueError("a node cannot be its own parent")
        if not 0 <= parent_int < node_count:
            raise IndexError("parent_index contains a parent outside the nodal array")
        parents.append(parent_int)
    return tuple(parents)


def _as_2d_float_array(values: Sequence[Sequence[float]] | np.ndarray, *, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 2:
        raise ValueError(f"{name} must have shape (nodes, timesteps)")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array
