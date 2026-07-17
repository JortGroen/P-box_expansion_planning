"""SimBench profile ingestion and critical-week extraction for E1.S3."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from src.manifest import build_manifest


DEFAULT_SCENARIO_CODES: Mapping[int, str] = {
    0: "1-MV-semiurb--0-sw",
    1: "1-MV-semiurb--1-sw",
    2: "1-MV-semiurb--2-sw",
}

DEFAULT_DECISION_TRANSFORMER_INDICES: tuple[int, ...] = (0, 1)
DEFAULT_WINTER_MONTHS: tuple[int, ...] = (12, 1, 2)
DEFAULT_TOP_COUNTS: tuple[int, ...] = (24, 96, 672)
DEFAULT_IMPORT_TOP_COUNT = 672
DEFAULT_COVERAGE_TARGET = 0.95
# Match the provisional G0-A3 event default; historical manifested configs can
# still pass 1.0 explicitly and must retain their executed interpretation.
DEFAULT_LOADING_THRESHOLD_PU = 1.1
DEFAULT_MIN_CONSECUTIVE_STEPS = 4
DEFAULT_PROFILE_START = "2016-01-01T00:00:00Z"
DEFAULT_STEP_MINUTES = 15


@dataclass(frozen=True)
class ScenarioProfile:
    """Aggregated full-year profile for one SimBench scenario.

    Parameters
    ----------
    scenario:
        SimBench scenario number.
    grid_code:
        SimBench grid code.
    loading_pu:
        Direction-agnostic apparent loading in p.u. of the summed decision
        transformer nameplate rating, sampled every 15 minutes.
    timestamps:
        Timezone-aware synthetic annual timestamps.
    aggregate_p_mw:
        Downstream net active power in MW. Positive values are net demand and
        negative values are reverse active-power flow.
    aggregate_q_mvar:
        Downstream net reactive power in Mvar.
    rating_mva:
        Summed decision-transformer nameplate rating in MVA.
    """

    scenario: int
    grid_code: str
    loading_pu: pd.Series
    timestamps: pd.DatetimeIndex
    aggregate_p_mw: pd.Series
    aggregate_q_mvar: pd.Series
    rating_mva: float


@dataclass(frozen=True)
class DirectionalLoading:
    """G0-A1 import/export loading split for one scenario.

    Parameters
    ----------
    loading_pu:
        Unconditioned apparent loading ``abs(S_net) / S_nom,agg`` in p.u.
    import_loading_pu:
        Apparent loading in p.u. when ``P_net > 0`` and zero otherwise.
    export_loading_pu:
        Apparent loading in p.u. when ``P_net < 0`` and zero otherwise.
    direction:
        Per-step direction label: ``"import"``, ``"export"``, or ``"zero"``.
    """

    loading_pu: pd.Series
    import_loading_pu: pd.Series
    export_loading_pu: pd.Series
    direction: pd.Series


@dataclass(frozen=True)
class TransformerHeadroom:
    """E1.S1b transformer headroom diagnostic values.

    Parameters
    ----------
    transformer_indices:
        Pandapower ``net.trafo`` indices used for the G0 decision transformer.
    nameplate_mva:
        Per-unit nameplate ratings in MVA.
    total_nameplate_mva:
        Sum of all selected unit ratings in MVA.
    firm_nameplate_mva:
        Remaining aggregate nameplate after the outage convention is applied.
    outage_convention:
        Text description of the firm-capacity convention.
    peak_import_mva:
        Full-year maximum import-direction apparent power in MVA.
    peak_import_timestamp:
        Timestamp of the full-year maximum import-direction apparent power.
    peak_import_loading_total_pu:
        Peak import loading divided by total aggregate nameplate.
    peak_import_loading_firm_pu:
        Peak import loading divided by firm aggregate nameplate.
    multiplier_to_095_total:
        Linear load multiplier needed to reach 0.95 p.u. on total nameplate.
    multiplier_to_095_firm:
        Linear load multiplier needed to reach 0.95 p.u. on firm nameplate.
    g0_fallback_total_triggered:
        Whether the signed G0 scenario-0 baseline fallback criterion is met
        under its current total-nameplate convention.
    firm_classifies_differently:
        Whether firm capacity would change the same scenario-0 fallback
        classification.
    """

    transformer_indices: tuple[int, ...]
    nameplate_mva: tuple[float, ...]
    total_nameplate_mva: float
    firm_nameplate_mva: float
    outage_convention: str
    busbar_parallel_status: str
    peak_import_mva: float
    peak_import_timestamp: pd.Timestamp
    peak_import_loading_total_pu: float
    peak_import_loading_firm_pu: float
    multiplier_to_095_total: float
    multiplier_to_095_firm: float
    g0_fallback_total_triggered: bool
    firm_capacity_fallback_triggered: bool
    firm_classifies_differently: bool


def annual_timestamps(
    n_steps: int,
    *,
    start: str = DEFAULT_PROFILE_START,
    step_minutes: int = DEFAULT_STEP_MINUTES,
) -> pd.DatetimeIndex:
    """Return timezone-aware 15-minute timestamps for a SimBench profile year.

    Parameters
    ----------
    n_steps:
        Number of profile rows.
    start:
        ISO timestamp for the first profile row.
    step_minutes:
        Profile step length in minutes.
    """

    if n_steps <= 0:
        raise ValueError("n_steps must be positive")
    if step_minutes <= 0:
        raise ValueError("step_minutes must be positive")
    return pd.date_range(start=start, periods=n_steps, freq=f"{step_minutes}min")


def aggregate_loading_from_profiles(
    *,
    load_p_mw: pd.DataFrame,
    load_q_mvar: pd.DataFrame,
    sgen_p_mw: pd.DataFrame | None,
    sgen_q_mvar: pd.DataFrame | None,
    rating_mva: float,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Compute G0 aggregate apparent loading from profile tables.

    Parameters
    ----------
    load_p_mw, load_q_mvar:
        Load active/reactive power profile tables in MW/Mvar.
    sgen_p_mw, sgen_q_mvar:
        Static-generator active/reactive power profile tables in MW/Mvar. When
        no reactive profile exists, zero Mvar is used.
    rating_mva:
        Summed decision-transformer nameplate rating in MVA.
    """

    if rating_mva <= 0:
        raise ValueError("rating_mva must be positive")
    if len(load_p_mw) != len(load_q_mvar):
        raise ValueError("load p/q profiles must have the same row count")

    load_p = load_p_mw.sum(axis=1).astype(float)
    load_q = load_q_mvar.sum(axis=1).astype(float)
    sgen_p = _sum_optional_profile(sgen_p_mw, len(load_p), load_p.index)
    sgen_q = _sum_optional_profile(sgen_q_mvar, len(load_p), load_p.index)

    net_p = load_p - sgen_p
    net_q = load_q - sgen_q
    loading = np.hypot(net_p.to_numpy(), net_q.to_numpy()) / rating_mva
    loading_pu = pd.Series(loading, index=load_p.index, name="loading_pu")
    return loading_pu, net_p.rename("aggregate_p_mw"), net_q.rename("aggregate_q_mvar")


def split_import_export_loading(
    *,
    loading_pu: pd.Series,
    aggregate_p_mw: pd.Series,
) -> DirectionalLoading:
    """Split apparent loading by G0-A1 active-power direction.

    Parameters
    ----------
    loading_pu:
        Unconditioned apparent loading in p.u.
    aggregate_p_mw:
        Net active power in MW. Positive is import, negative is export, and
        zero is neither direction.
    """

    if len(loading_pu) != len(aggregate_p_mw):
        raise ValueError("loading_pu and aggregate_p_mw must have the same length")
    if not loading_pu.index.equals(aggregate_p_mw.index):
        raise ValueError("loading_pu and aggregate_p_mw must use the same index")

    import_mask = aggregate_p_mw > 0
    export_mask = aggregate_p_mw < 0
    import_loading = loading_pu.where(import_mask, 0.0).rename("import_loading_pu")
    export_loading = loading_pu.where(export_mask, 0.0).rename("export_loading_pu")
    direction = pd.Series("zero", index=aggregate_p_mw.index, name="direction", dtype="object")
    direction.loc[import_mask] = "import"
    direction.loc[export_mask] = "export"
    return DirectionalLoading(
        loading_pu=loading_pu.rename("loading_pu"),
        import_loading_pu=import_loading,
        export_loading_pu=export_loading,
        direction=direction,
    )


def load_simbench_scenario_profile(
    scenario: int,
    *,
    grid_code: str,
    decision_transformer_indices: Sequence[int] = DEFAULT_DECISION_TRANSFORMER_INDICES,
    profile_start: str = DEFAULT_PROFILE_START,
    step_minutes: int = DEFAULT_STEP_MINUTES,
) -> ScenarioProfile:
    """Load full-year SimBench profiles and compute aggregate loading.

    Parameters
    ----------
    scenario:
        Scenario number recorded in the output table.
    grid_code:
        SimBench grid code to load.
    decision_transformer_indices:
        Pandapower ``net.trafo`` indices whose nameplate ratings define the
        G0 decision-transformer aggregate rating.
    profile_start:
        ISO timestamp assigned to profile row 0.
    step_minutes:
        Profile step length in minutes.
    """

    import simbench as sb

    net = sb.get_simbench_net(grid_code)
    rating_mva = float(net.trafo.loc[list(decision_transformer_indices), "sn_mva"].sum())
    absolute_values = sb.get_absolute_values(net, True)
    load_p = absolute_values[("load", "p_mw")]
    load_q = absolute_values[("load", "q_mvar")]
    sgen_p = absolute_values.get(("sgen", "p_mw"))
    sgen_q = absolute_values.get(("sgen", "q_mvar"))
    loading_pu, net_p, net_q = aggregate_loading_from_profiles(
        load_p_mw=load_p,
        load_q_mvar=load_q,
        sgen_p_mw=sgen_p,
        sgen_q_mvar=sgen_q,
        rating_mva=rating_mva,
    )
    timestamps = annual_timestamps(len(loading_pu), start=profile_start, step_minutes=step_minutes)
    loading_pu.index = timestamps
    net_p.index = timestamps
    net_q.index = timestamps
    return ScenarioProfile(
        scenario=scenario,
        grid_code=grid_code,
        loading_pu=loading_pu,
        timestamps=timestamps,
        aggregate_p_mw=net_p,
        aggregate_q_mvar=net_q,
        rating_mva=rating_mva,
    )


def rank_winter_weeks(
    loading_pu: pd.Series,
    *,
    winter_months: Iterable[int] = DEFAULT_WINTER_MONTHS,
) -> pd.DataFrame:
    """Rank winter weeks by their maximum aggregate transformer loading.

    Parameters
    ----------
    loading_pu:
        Time-indexed loading series in p.u.
    winter_months:
        Month numbers that qualify as winter profile rows.
    """

    if not isinstance(loading_pu.index, pd.DatetimeIndex):
        raise TypeError("loading_pu must use a DatetimeIndex")
    if loading_pu.empty:
        raise ValueError("loading_pu must not be empty")

    winter_set = set(winter_months)
    frame = pd.DataFrame({"timestamp": loading_pu.index, "loading_pu": loading_pu.to_numpy()})
    frame["week_start"] = frame["timestamp"].dt.floor("D") - pd.to_timedelta(
        frame["timestamp"].dt.weekday, unit="D"
    )
    frame["is_winter"] = frame["timestamp"].dt.month.isin(winter_set)
    winter = frame.loc[frame["is_winter"]].copy()
    if winter.empty:
        raise ValueError("No winter profile rows found")

    rows: list[dict[str, object]] = []
    for week_start, week_rows in winter.groupby("week_start", sort=True):
        idx_max = week_rows["loading_pu"].idxmax()
        top_row = week_rows.loc[idx_max]
        rows.append(
            {
                "week_start": pd.Timestamp(week_start),
                "week_end_exclusive": pd.Timestamp(week_start) + pd.Timedelta(days=7),
                "max_loading_pu": float(week_rows["loading_pu"].max()),
                "mean_loading_pu": float(week_rows["loading_pu"].mean()),
                "steps_in_winter_months": int(len(week_rows)),
                "top_timestamp": pd.Timestamp(top_row["timestamp"]),
                "top_step_position": int(loading_pu.index.get_loc(top_row["timestamp"])),
            }
        )
    ranked = pd.DataFrame(rows).sort_values(
        ["max_loading_pu", "mean_loading_pu", "week_start"],
        ascending=[False, False, True],
        ignore_index=True,
    )
    ranked.insert(0, "week_rank", np.arange(1, len(ranked) + 1, dtype=int))
    return ranked


def rank_annual_weeks(loading_pu: pd.Series) -> pd.DataFrame:
    """Rank annual weeks by their maximum loading.

    Parameters
    ----------
    loading_pu:
        Time-indexed loading series in p.u.
    """

    if not isinstance(loading_pu.index, pd.DatetimeIndex):
        raise TypeError("loading_pu must use a DatetimeIndex")
    if loading_pu.empty:
        raise ValueError("loading_pu must not be empty")

    frame = pd.DataFrame({"timestamp": loading_pu.index, "loading_pu": loading_pu.to_numpy()})
    frame["week_start"] = frame["timestamp"].dt.floor("D") - pd.to_timedelta(
        frame["timestamp"].dt.weekday, unit="D"
    )
    rows: list[dict[str, object]] = []
    for week_start, week_rows in frame.groupby("week_start", sort=True):
        idx_max = week_rows["loading_pu"].idxmax()
        top_row = week_rows.loc[idx_max]
        rows.append(
            {
                "week_start": pd.Timestamp(week_start),
                "week_end_exclusive": pd.Timestamp(week_start) + pd.Timedelta(days=7),
                "max_loading_pu": float(week_rows["loading_pu"].max()),
                "mean_loading_pu": float(week_rows["loading_pu"].mean()),
                "steps_in_week": int(len(week_rows)),
                "top_timestamp": pd.Timestamp(top_row["timestamp"]),
                "top_step_position": int(loading_pu.index.get_loc(top_row["timestamp"])),
            }
        )
    ranked = pd.DataFrame(rows).sort_values(
        ["max_loading_pu", "mean_loading_pu", "week_start"],
        ascending=[False, False, True],
        ignore_index=True,
    )
    ranked.insert(0, "week_rank", np.arange(1, len(ranked) + 1, dtype=int))
    return ranked


def coverage_by_rank(
    loading_pu: pd.Series,
    ranked_weeks: pd.DataFrame,
    *,
    top_counts: Sequence[int] = DEFAULT_TOP_COUNTS,
) -> pd.DataFrame:
    """Measure how top-ranked winter weeks cover annual top-loading steps.

    Parameters
    ----------
    loading_pu:
        Annual loading series in p.u.
    ranked_weeks:
        Output from :func:`rank_winter_weeks`.
    top_counts:
        Annual top-k step counts to evaluate.
    """

    ordered_steps = set()
    annual_rank = pd.Series(
        np.arange(len(loading_pu)),
        index=loading_pu.sort_values(ascending=False).index,
        name="annual_rank",
    )
    rows: list[dict[str, object]] = []
    for _, week in ranked_weeks.iterrows():
        in_week = (loading_pu.index >= week["week_start"]) & (
            loading_pu.index < week["week_end_exclusive"]
        )
        ordered_steps.update(loading_pu.index[in_week])
        row: dict[str, object] = {"week_rank": int(week["week_rank"])}
        for top_count in top_counts:
            count = min(int(top_count), len(loading_pu))
            top_index = set(annual_rank.iloc[:count].index)
            captured = len(top_index.intersection(ordered_steps))
            row[f"top_{top_count}_coverage"] = captured / count
        rows.append(row)
    return pd.DataFrame(rows)


def count_overload_episodes(
    loading_pu: pd.Series,
    *,
    threshold_pu: float = DEFAULT_LOADING_THRESHOLD_PU,
    min_consecutive_steps: int = DEFAULT_MIN_CONSECUTIVE_STEPS,
) -> int:
    """Count threshold episodes using G0-A1 consecutive-step semantics.

    Parameters
    ----------
    loading_pu:
        Direction-conditioned loading series in p.u. Direction flips should
        already be encoded as zero loading in this series.
    threshold_pu:
        Strict loading threshold in p.u.
    min_consecutive_steps:
        Minimum consecutive 15-minute exceedance steps for an episode.
    """

    if min_consecutive_steps <= 0:
        raise ValueError("min_consecutive_steps must be positive")
    episodes = 0
    run_length = 0
    in_episode = False
    for value in loading_pu:
        if float(value) > threshold_pu:
            run_length += 1
            if run_length >= min_consecutive_steps and not in_episode:
                episodes += 1
                in_episode = True
        else:
            run_length = 0
            in_episode = False
    return episodes


def choose_adaptive_window_count(
    coverage: pd.DataFrame,
    *,
    coverage_column: str,
    target: float = DEFAULT_COVERAGE_TARGET,
    margin_weeks: int = 1,
) -> dict[str, object]:
    """Choose top-K import windows plus a margin week from a coverage curve."""

    if not 0 < target <= 1:
        raise ValueError("target must be in (0, 1]")
    if margin_weeks < 0:
        raise ValueError("margin_weeks must be non-negative")
    if coverage_column not in coverage:
        raise KeyError(f"Missing coverage column: {coverage_column}")
    reached = coverage.loc[coverage[coverage_column] >= target]
    if reached.empty:
        base_k = int(coverage["week_rank"].max())
        feasible = False
    else:
        base_k = int(reached.iloc[0]["week_rank"])
        feasible = True
    selected_k = min(base_k + margin_weeks, int(coverage["week_rank"].max()))
    selected_coverage = float(
        coverage.loc[coverage["week_rank"] == selected_k, coverage_column].iloc[0]
    )
    return {
        "base_k": base_k,
        "margin_weeks": margin_weeks,
        "selected_k": selected_k,
        "selected_coverage": selected_coverage,
        "target": target,
        "target_feasible": feasible,
    }


def firm_nameplate_after_largest_unit_outage(nameplate_mva: Sequence[float]) -> float:
    """Return firm ``(n-1)`` nameplate after the largest unit is outaged.

    Parameters
    ----------
    nameplate_mva:
        Per-transformer nameplate ratings in MVA.
    """

    if len(nameplate_mva) < 2:
        raise ValueError("firm (n-1) nameplate requires at least two transformer units")
    ratings = [float(value) for value in nameplate_mva]
    if any(value <= 0 for value in ratings):
        raise ValueError("all transformer nameplate ratings must be positive")
    return float(sum(ratings) - max(ratings))


def multiplier_to_loading_target(
    *,
    current_loading_pu: float,
    target_loading_pu: float,
) -> float:
    """Return the linear multiplier needed to reach a loading target."""

    if current_loading_pu <= 0:
        raise ValueError("current_loading_pu must be positive")
    if target_loading_pu <= 0:
        raise ValueError("target_loading_pu must be positive")
    return float(target_loading_pu / current_loading_pu)


def transformer_headroom_diagnostic(
    profile: ScenarioProfile,
    *,
    nameplate_mva: Sequence[float],
    transformer_indices: Sequence[int],
    busbar_parallel_status: str,
    fallback_threshold_pu: float = 0.85,
    target_loading_pu: float = 0.95,
) -> TransformerHeadroom:
    """Compute E1.S1b total-versus-firm transformer headroom values.

    Parameters
    ----------
    profile:
        Scenario profile carrying full-year aggregate P/Q and total-nameplate
        loading.
    nameplate_mva:
        Per-unit decision-transformer nameplate ratings in MVA.
    transformer_indices:
        Pandapower ``net.trafo`` indices corresponding to ``nameplate_mva``.
    busbar_parallel_status:
        Auditable text describing the busbar/tie arrangement.
    fallback_threshold_pu:
        G0 scenario-0 baseline fallback threshold in p.u.
    target_loading_pu:
        Diagnostic loading target in p.u. for multiplier calculations.
    """

    if fallback_threshold_pu <= 0:
        raise ValueError("fallback_threshold_pu must be positive")
    ratings = tuple(float(value) for value in nameplate_mva)
    total_nameplate = float(sum(ratings))
    if total_nameplate <= 0:
        raise ValueError("total nameplate must be positive")
    if abs(total_nameplate - profile.rating_mva) > 1e-9:
        raise ValueError("profile rating_mva does not match transformer nameplate sum")

    split = split_import_export_loading(
        loading_pu=profile.loading_pu,
        aggregate_p_mw=profile.aggregate_p_mw,
    )
    peak_timestamp = pd.Timestamp(split.import_loading_pu.idxmax())
    peak_loading_total = float(split.import_loading_pu.loc[peak_timestamp])
    if peak_loading_total <= 0:
        raise ValueError("profile has no positive import-loading steps")
    peak_import_mva = float(peak_loading_total * total_nameplate)

    firm_nameplate = firm_nameplate_after_largest_unit_outage(ratings)
    peak_loading_firm = float(peak_import_mva / firm_nameplate)
    total_triggered = bool(peak_loading_total > fallback_threshold_pu)
    firm_triggered = bool(peak_loading_firm > fallback_threshold_pu)
    return TransformerHeadroom(
        transformer_indices=tuple(int(index) for index in transformer_indices),
        nameplate_mva=ratings,
        total_nameplate_mva=total_nameplate,
        firm_nameplate_mva=firm_nameplate,
        outage_convention=(
            "firm (n-1) is computed as total selected decision-transformer "
            "nameplate minus the single largest in-service unit nameplate"
        ),
        busbar_parallel_status=busbar_parallel_status,
        peak_import_mva=peak_import_mva,
        peak_import_timestamp=peak_timestamp,
        peak_import_loading_total_pu=peak_loading_total,
        peak_import_loading_firm_pu=peak_loading_firm,
        multiplier_to_095_total=multiplier_to_loading_target(
            current_loading_pu=peak_loading_total,
            target_loading_pu=target_loading_pu,
        ),
        multiplier_to_095_firm=multiplier_to_loading_target(
            current_loading_pu=peak_loading_firm,
            target_loading_pu=target_loading_pu,
        ),
        g0_fallback_total_triggered=total_triggered,
        firm_capacity_fallback_triggered=firm_triggered,
        firm_classifies_differently=total_triggered != firm_triggered,
    )


def build_critical_week_tables(
    profiles: Sequence[ScenarioProfile],
    *,
    winter_months: Sequence[int] = DEFAULT_WINTER_MONTHS,
    top_counts: Sequence[int] = DEFAULT_TOP_COUNTS,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build critical-week, coverage, and scenario summary tables."""

    week_tables: list[pd.DataFrame] = []
    coverage_tables: list[pd.DataFrame] = []
    summaries: list[dict[str, object]] = []
    for profile in profiles:
        ranked = rank_winter_weeks(profile.loading_pu, winter_months=winter_months)
        ranked.insert(0, "grid_code", profile.grid_code)
        ranked.insert(0, "scenario", profile.scenario)
        coverage = coverage_by_rank(profile.loading_pu, ranked, top_counts=top_counts)
        coverage.insert(0, "scenario", profile.scenario)
        coverage.insert(1, "grid_code", profile.grid_code)
        annual_max_timestamp = profile.loading_pu.idxmax()
        annual_max_loading = float(profile.loading_pu.max())
        summaries.append(
            {
                "scenario": profile.scenario,
                "grid_code": profile.grid_code,
                "steps": int(len(profile.loading_pu)),
                "rating_mva": profile.rating_mva,
                "annual_max_loading_pu": annual_max_loading,
                "annual_max_timestamp": annual_max_timestamp,
                "annual_top_step_is_winter": bool(annual_max_timestamp.month in set(winter_months)),
                "winter_week_count": int(len(ranked)),
                "top_winter_week_start": ranked.loc[0, "week_start"],
                "top_winter_week_max_loading_pu": float(ranked.loc[0, "max_loading_pu"]),
            }
        )
        week_tables.append(ranked)
        coverage_tables.append(coverage)
    return (
        pd.concat(week_tables, ignore_index=True),
        pd.concat(coverage_tables, ignore_index=True),
        pd.DataFrame(summaries),
    )


def build_import_window_tables(
    profiles: Sequence[ScenarioProfile],
    *,
    top_count: int = DEFAULT_IMPORT_TOP_COUNT,
    coverage_target: float = DEFAULT_COVERAGE_TARGET,
    margin_weeks: int = 1,
    threshold_pu: float = DEFAULT_LOADING_THRESHOLD_PU,
    min_consecutive_steps: int = DEFAULT_MIN_CONSECUTIVE_STEPS,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build G0-A1 import-window and export-diagnostic tables."""

    window_tables: list[pd.DataFrame] = []
    coverage_tables: list[pd.DataFrame] = []
    proposal_rows: list[dict[str, object]] = []
    export_rows: list[dict[str, object]] = []
    coverage_column = f"top_{top_count}_coverage"

    for profile in profiles:
        split = split_import_export_loading(
            loading_pu=profile.loading_pu,
            aggregate_p_mw=profile.aggregate_p_mw,
        )
        ranked = rank_annual_weeks(split.import_loading_pu)
        ranked = ranked.rename(columns={"max_loading_pu": "max_import_loading_pu"})
        ranked.insert(0, "grid_code", profile.grid_code)
        ranked.insert(0, "scenario", profile.scenario)
        coverage = coverage_by_rank(split.import_loading_pu, ranked, top_counts=(top_count,))
        coverage.insert(0, "scenario", profile.scenario)
        coverage.insert(1, "grid_code", profile.grid_code)
        proposal = choose_adaptive_window_count(
            coverage,
            coverage_column=coverage_column,
            target=coverage_target,
            margin_weeks=margin_weeks,
        )
        selected_rank = int(proposal["selected_k"])
        selected_windows = ranked.loc[ranked["week_rank"] <= selected_rank]
        proposal_rows.append(
            {
                "scenario": profile.scenario,
                "grid_code": profile.grid_code,
                "annual_top_import_loading_pu": float(split.import_loading_pu.max()),
                "annual_top_import_timestamp": split.import_loading_pu.idxmax(),
                "base_k_for_target": int(proposal["base_k"]),
                "margin_weeks": int(proposal["margin_weeks"]),
                "selected_k_with_margin": selected_rank,
                "selected_coverage": float(proposal["selected_coverage"]),
                "coverage_target": float(proposal["target"]),
                "target_feasible": bool(proposal["target_feasible"]),
                "selected_window_starts": "; ".join(
                    pd.Timestamp(value).isoformat() for value in selected_windows["week_start"]
                ),
            }
        )
        export_rows.append(
            {
                "scenario": profile.scenario,
                "grid_code": profile.grid_code,
                "export_max_loading_pu": float(split.export_loading_pu.max()),
                "export_max_timestamp": split.export_loading_pu.idxmax(),
                "export_steps_above_threshold": int((split.export_loading_pu > threshold_pu).sum()),
                "export_episodes": count_overload_episodes(
                    split.export_loading_pu,
                    threshold_pu=threshold_pu,
                    min_consecutive_steps=min_consecutive_steps,
                ),
                "import_steps_above_threshold": int((split.import_loading_pu > threshold_pu).sum()),
                "import_episodes": count_overload_episodes(
                    split.import_loading_pu,
                    threshold_pu=threshold_pu,
                    min_consecutive_steps=min_consecutive_steps,
                ),
                "import_steps": int((split.direction == "import").sum()),
                "export_steps": int((split.direction == "export").sum()),
                "zero_direction_steps": int((split.direction == "zero").sum()),
            }
        )
        window_tables.append(ranked)
        coverage_tables.append(coverage)

    return (
        pd.concat(window_tables, ignore_index=True),
        pd.concat(coverage_tables, ignore_index=True),
        pd.DataFrame(proposal_rows),
        pd.DataFrame(export_rows),
    )


def write_critical_week_outputs(config_path: str | Path) -> dict[str, object]:
    """Run the E1.S3 profile extraction from a JSON config file."""

    config_file = Path(config_path)
    config = json.loads(config_file.read_text(encoding="utf-8"))
    output_dir = Path(config["output_dir"])
    figure_dir = Path(config["figure_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    scenario_codes = {int(key): value for key, value in config["scenario_codes"].items()}
    transformer_indices = tuple(int(value) for value in config["decision_transformer_indices"])
    winter_months = tuple(int(value) for value in config["winter_months"])
    top_counts = tuple(int(value) for value in config["top_counts"])
    profiles = [
        load_simbench_scenario_profile(
            scenario,
            grid_code=grid_code,
            decision_transformer_indices=transformer_indices,
            profile_start=config.get("profile_start", DEFAULT_PROFILE_START),
            step_minutes=int(config.get("step_minutes", DEFAULT_STEP_MINUTES)),
        )
        for scenario, grid_code in sorted(scenario_codes.items())
    ]
    critical_weeks, coverage, summary = build_critical_week_tables(
        profiles,
        winter_months=winter_months,
        top_counts=top_counts,
    )

    critical_csv = output_dir / "critical_weeks.csv"
    coverage_csv = output_dir / "critical_week_coverage.csv"
    summary_csv = output_dir / "critical_week_summary.csv"
    critical_weeks.to_csv(critical_csv, index=False)
    coverage.to_csv(coverage_csv, index=False)
    summary.to_csv(summary_csv, index=False)

    parquet_path = output_dir / "critical_weeks.parquet"
    parquet_written = _try_write_parquet(critical_weeks, parquet_path)

    loading_plot = figure_dir / "critical_week_loading.png"
    coverage_plot = figure_dir / "critical_week_coverage.png"
    _write_plots(profiles, coverage, loading_plot=loading_plot, coverage_plot=coverage_plot)

    report_path = Path(config["report_path"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        critical_week_report(
            config=config,
            summary=summary,
            critical_weeks=critical_weeks,
            coverage=coverage,
            parquet_written=parquet_written,
        ),
        encoding="utf-8",
    )

    output_paths: list[Path] = [critical_csv, coverage_csv, summary_csv, loading_plot, coverage_plot, report_path]
    if parquet_written:
        output_paths.append(parquet_path)

    manifest = build_manifest(
        config_path=config_file,
        seeds={"none": "deterministic"},
        output_paths=output_paths,
        extra={
            "artifact_type": "critical_week_evidence",
            "task_id": "E1.S3",
            "timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "command": config["command"],
            "scenario_codes": [
                {"scenario": scenario, "grid_code": grid_code}
                for scenario, grid_code in sorted(scenario_codes.items())
            ],
            "decision_transformer_indices": list(transformer_indices),
            "winter_months": list(winter_months),
            "top_counts": list(top_counts),
            "parquet_written": parquet_written,
        },
    )
    manifest_path = Path(config["manifest_path"])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def write_import_window_outputs(config_path: str | Path) -> dict[str, object]:
    """Run the E1.S3b G0-A1 import-window diagnostic from JSON config."""

    config_file = Path(config_path)
    config = json.loads(config_file.read_text(encoding="utf-8"))
    output_dir = Path(config["output_dir"])
    figure_dir = Path(config["figure_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    scenario_codes = {int(key): value for key, value in config["scenario_codes"].items()}
    transformer_indices = tuple(int(value) for value in config["decision_transformer_indices"])
    top_count = int(config.get("top_count", DEFAULT_IMPORT_TOP_COUNT))
    coverage_target = float(config.get("coverage_target", DEFAULT_COVERAGE_TARGET))
    margin_weeks = int(config.get("margin_weeks", 1))
    threshold_pu = float(config.get("threshold_pu", DEFAULT_LOADING_THRESHOLD_PU))
    min_consecutive_steps = int(
        config.get("min_consecutive_steps", DEFAULT_MIN_CONSECUTIVE_STEPS)
    )
    profiles = [
        load_simbench_scenario_profile(
            scenario,
            grid_code=grid_code,
            decision_transformer_indices=transformer_indices,
            profile_start=config.get("profile_start", DEFAULT_PROFILE_START),
            step_minutes=int(config.get("step_minutes", DEFAULT_STEP_MINUTES)),
        )
        for scenario, grid_code in sorted(scenario_codes.items())
    ]
    import_windows, coverage, proposal, export = build_import_window_tables(
        profiles,
        top_count=top_count,
        coverage_target=coverage_target,
        margin_weeks=margin_weeks,
        threshold_pu=threshold_pu,
        min_consecutive_steps=min_consecutive_steps,
    )

    windows_csv = output_dir / "import_windows.csv"
    coverage_csv = output_dir / "import_window_coverage.csv"
    proposal_csv = output_dir / "import_window_proposal.csv"
    export_csv = output_dir / "export_direction_exceedance.csv"
    import_windows.to_csv(windows_csv, index=False)
    coverage.to_csv(coverage_csv, index=False)
    proposal.to_csv(proposal_csv, index=False)
    export.to_csv(export_csv, index=False)

    coverage_plot = figure_dir / "import_window_coverage.png"
    _write_import_window_plot(
        coverage,
        coverage_column=f"top_{top_count}_coverage",
        target=coverage_target,
        output_path=coverage_plot,
    )

    report_path = Path(config["report_path"])
    report_path.write_text(
        import_window_report(
            config=config,
            import_windows=import_windows,
            coverage=coverage,
            proposal=proposal,
            export=export,
        ),
        encoding="utf-8",
    )

    output_paths = [windows_csv, coverage_csv, proposal_csv, export_csv, coverage_plot, report_path]
    manifest = build_manifest(
        config_path=config_file,
        seeds={"none": "deterministic"},
        output_paths=output_paths,
        extra={
            "artifact_type": "import_window_evidence",
            "task_id": "E1.S3b",
            "timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "command": config["command"],
            "scenario_codes": [
                {"scenario": scenario, "grid_code": grid_code}
                for scenario, grid_code in sorted(scenario_codes.items())
            ],
            "decision_transformer_indices": list(transformer_indices),
            "top_count": top_count,
            "coverage_target": coverage_target,
            "margin_weeks": margin_weeks,
            "threshold_pu": threshold_pu,
            "min_consecutive_steps": min_consecutive_steps,
        },
    )
    manifest_path = Path(config["manifest_path"])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def write_transformer_headroom_outputs(config_path: str | Path) -> dict[str, object]:
    """Run the E1.S1b transformer-headroom diagnostic from JSON config."""

    import simbench as sb

    config_file = Path(config_path)
    config = json.loads(config_file.read_text(encoding="utf-8"))
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    scenario = int(config["scenario"])
    grid_code = str(config["grid_code"])
    transformer_indices = tuple(int(value) for value in config["decision_transformer_indices"])
    busbar_switch_indices = tuple(int(value) for value in config["busbar_switch_indices"])
    transformer_switch_indices = tuple(int(value) for value in config["transformer_switch_indices"])
    fallback_threshold_pu = float(config["fallback_threshold_pu"])
    target_loading_pu = float(config["target_loading_pu"])

    net = sb.get_simbench_net(grid_code)
    trafo_detail = net.trafo.loc[list(transformer_indices)].copy()
    nameplates = tuple(float(value) for value in trafo_detail["sn_mva"])
    switch_detail = net.switch.loc[list(busbar_switch_indices + transformer_switch_indices)].copy()
    busbar_switches_closed = bool(net.switch.loc[list(busbar_switch_indices), "closed"].all())
    transformer_switches_closed = bool(net.switch.loc[list(transformer_switch_indices), "closed"].all())
    equal_taps = bool(trafo_detail["tap_pos"].nunique(dropna=False) == 1)
    in_service = bool(trafo_detail["in_service"].all())
    busbar_parallel_status = (
        f"Closed busbar-parallel transformer bank: busbar/tie switches "
        f"{list(busbar_switch_indices)} closed={busbar_switches_closed}; associated "
        f"transformer circuit-breaker switches {list(transformer_switch_indices)} "
        f"closed={transformer_switches_closed}; equal tap positions={equal_taps}; "
        f"selected transformer units in service={in_service}."
    )

    profile = load_simbench_scenario_profile(
        scenario,
        grid_code=grid_code,
        decision_transformer_indices=transformer_indices,
        profile_start=config.get("profile_start", DEFAULT_PROFILE_START),
        step_minutes=int(config.get("step_minutes", DEFAULT_STEP_MINUTES)),
    )
    diagnostic = transformer_headroom_diagnostic(
        profile,
        nameplate_mva=nameplates,
        transformer_indices=transformer_indices,
        busbar_parallel_status=busbar_parallel_status,
        fallback_threshold_pu=fallback_threshold_pu,
        target_loading_pu=target_loading_pu,
    )

    diagnostic_csv = output_dir / "transformer_headroom_diagnostic.csv"
    diagnostic_table = pd.DataFrame([_headroom_row(diagnostic, config=config)])
    diagnostic_table.to_csv(diagnostic_csv, index=False)

    report_path = Path(config["report_path"])
    report_path.write_text(
        transformer_headroom_report(
            config=config,
            diagnostic=diagnostic,
            trafo_detail=trafo_detail,
            switch_detail=switch_detail,
        ),
        encoding="utf-8",
    )

    output_paths = [diagnostic_csv, report_path]
    manifest = build_manifest(
        config_path=config_file,
        seeds={"none": "deterministic"},
        output_paths=output_paths,
        extra={
            "artifact_type": "transformer_headroom_evidence",
            "task_id": "E1.S1b",
            "timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "command": config["command"],
            "scenario": scenario,
            "grid_code": grid_code,
            "decision_transformer_indices": list(transformer_indices),
            "busbar_switch_indices": list(busbar_switch_indices),
            "transformer_switch_indices": list(transformer_switch_indices),
            "fallback_threshold_pu": fallback_threshold_pu,
            "target_loading_pu": target_loading_pu,
            "outage_convention": diagnostic.outage_convention,
        },
    )
    manifest_path = Path(config["manifest_path"])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def critical_week_report(
    *,
    config: Mapping[str, Any],
    summary: pd.DataFrame,
    critical_weeks: pd.DataFrame,
    coverage: pd.DataFrame,
    parquet_written: bool,
) -> str:
    """Render the E1.S3 validation report as Markdown."""

    top_rows = critical_weeks.loc[critical_weeks["week_rank"] <= int(config["report_top_week_rows"])]
    coverage_rows = coverage.loc[coverage["week_rank"] <= int(config["report_top_week_rows"])]
    output_dir = Path(config["output_dir"])
    figure_dir = Path(config.get("figure_dir", output_dir))
    csv_path = output_dir / "critical_weeks.csv"
    parquet_path = output_dir / "critical_weeks.parquet"
    loading_plot = figure_dir / "critical_week_loading.png"
    coverage_plot = figure_dir / "critical_week_coverage.png"
    report_path = Path(config["report_path"])
    parquet_note = (
        f"`{parquet_path.as_posix()}` was written."
        if parquet_written
        else f"`{parquet_path.as_posix()}` was not written because no parquet engine is installed; "
        f"`{csv_path.as_posix()}` is the version-controlled table."
    )
    return "\n".join(
        [
            "# E1.S3 Time Series And Critical Weeks",
            "",
            "Status: complete for E1.S3 review.",
            "",
            "## Scope",
            "",
            "This report ingests the SimBench full-year 15-minute profiles for the primary",
            "semi-urban MV grid under scenarios 0, 1, and 2. Scenario 0 remains the G0",
            "primary baseline; scenarios 1 and 2 are appendix cross-checks only.",
            "",
            "Loading follows the G0 aggregate decision-transformer definition:",
            "`abs(sum_i S_i(t)) / sum_i S_nom_i`. For this profile-screening story,",
            "the aggregate complex exchange is computed from SimBench absolute load P/Q",
            "and static-generator P profiles. SimBench provides zero static-generator Q",
            "for this grid, so no reactive generator profile is subtracted.",
            "",
            "## Evidence",
            "",
            f"- Input config: `{config['config_path_label']}`",
            f"- Manifest: `{config['manifest_path']}`",
            f"- Report: `{report_path.as_posix()}`",
            f"- Critical-week table: `{csv_path.as_posix()}`; {parquet_note}",
            f"- Validation plots: `{loading_plot.as_posix()}` and",
            f"  `{coverage_plot.as_posix()}`",
            "",
            "## Extraction Rule",
            "",
            f"- Profile calendar: synthetic UTC leap year starting `{config['profile_start']}`",
            f"- Step length: {config['step_minutes']} minutes",
            f"- Winter months: {', '.join(str(month) for month in config['winter_months'])}",
            "- Weeks are ranked by maximum aggregate loading within winter-profile rows.",
            "- Coverage is diagnostic: it reports how many annual top-loading timesteps are",
            "  captured after taking the first N ranked winter weeks.",
            "",
            "## Scenario Summary",
            "",
            _markdown_table(summary),
            "",
            "## Top Ranked Winter Weeks",
            "",
            _markdown_table(top_rows),
            "",
            "## Annual Top-Step Coverage By Ranked Winter Windows",
            "",
            _markdown_table(coverage_rows),
            "",
            "## Validation Finding",
            "",
            _validation_finding(coverage=coverage, summary=summary, top_counts=config["top_counts"]),
            "",
            "## Interpretation For G1",
            "",
            "The report exposes whether winter windows contain the annual highest-loading",
            "steps under SimBench baseline scenarios. It does not settle G1 by itself,",
            "does not benchmark the lower-level lightsim2grid TimeSeriesCPP path, and does",
            "not change the G0 overload-event definition.",
            "",
        ]
    )
def import_window_report(
    *,
    config: Mapping[str, Any],
    import_windows: pd.DataFrame,
    coverage: pd.DataFrame,
    proposal: pd.DataFrame,
    export: pd.DataFrame,
) -> str:
    """Render the E1.S3b G0-A1 import-window report as Markdown."""

    report_rows = int(config["report_top_week_rows"])
    top_import_rows = import_windows.loc[import_windows["week_rank"] <= report_rows]
    top_coverage_rows = coverage.loc[coverage["week_rank"] <= report_rows]
    top_count = int(config["top_count"])
    output_dir = Path(config["output_dir"])
    figure_dir = Path(config.get("figure_dir", output_dir))
    report_path = Path(config["report_path"])
    table_paths = [
        output_dir / "import_windows.csv",
        output_dir / "import_window_coverage.csv",
        output_dir / "import_window_proposal.csv",
        output_dir / "export_direction_exceedance.csv",
    ]
    coverage_plot = figure_dir / "import_window_coverage.png"
    return "\n".join(
        [
            "# E1.S3b G0-A1 Import-Window Diagnostic",
            "",
            "Status: complete for E1.S3b review. This is evidence for G1 only; it does",
            "not mark G1 passed.",
            "",
            "## Scope",
            "",
            "This diagnostic applies the approved G0-A1 import/export split to the",
            "SimBench full-year 15-minute scenario profiles. The apparent-power",
            "magnitude `abs(S_net) / S_nom,agg` remains the loading quantity, while",
            "`P_net > 0` gates import loading, `P_net < 0` gates export loading, and",
            "`P_net = 0` belongs to neither direction.",
            "",
            "Direction flips reset overload episode counters because the direction-gated",
            "loading series is zero outside its direction. Export/feed-in exceedance is",
            "reported separately and remains out of scope for the consumption-deferral",
            "event.",
            "",
            "## Evidence",
            "",
            f"- Input config: `{config['config_path_label']}`",
            f"- Manifest: `{config['manifest_path']}`",
            f"- Report: `{report_path.as_posix()}`",
            "- Output tables: " + ", ".join(f"`{path.as_posix()}`" for path in table_paths),
            f"- Coverage plot: `{coverage_plot.as_posix()}`",
            "",
            "## Adaptive Import-Window Proposal",
            "",
            f"The coverage target is {float(config['coverage_target']):.0%} of the annual",
            f"top-{top_count} import-loading steps. The proposed critical windows are",
            "the smallest top-K annual import-ranked weeks reaching the target, plus",
            f"{int(config['margin_weeks'])} margin week.",
            "",
            _markdown_table(proposal),
            "",
            "## Top Import-Ranked Annual Weeks",
            "",
            _markdown_table(top_import_rows),
            "",
            "## Coverage-Vs-K For Annual Top Import-Loading Steps",
            "",
            _markdown_table(top_coverage_rows),
            "",
            "## Export-Direction Exceedance Side Report",
            "",
            _markdown_table(export),
            "",
            "## Interpretation For G1",
            "",
            "The adaptive windows satisfy the deterministic G0-A1 coverage target for",
            "these SimBench profile screens where `target_feasible` is true. G1 still",
            "needs the PI decision on compute budget and time structure; this report",
            "does not freeze IC schemas or pass G1.",
            "",
        ]
    )
def transformer_headroom_report(
    *,
    config: Mapping[str, Any],
    diagnostic: TransformerHeadroom,
    trafo_detail: pd.DataFrame,
    switch_detail: pd.DataFrame,
) -> str:
    """Render the E1.S1b transformer-headroom diagnostic as Markdown."""

    summary = pd.DataFrame([_headroom_row(diagnostic, config=config)])
    trafo_rows = trafo_detail.reset_index(names="trafo_index")[
        ["trafo_index", "name", "hv_bus", "lv_bus", "sn_mva", "parallel", "tap_pos", "in_service"]
    ]
    switch_rows = switch_detail.reset_index(names="switch_index")[
        ["switch_index", "bus", "element", "et", "closed", "type", "name"]
    ]
    output_dir = Path(config["output_dir"])
    report_path = Path(config["report_path"])
    table_path = output_dir / "transformer_headroom_diagnostic.csv"
    firm_warning = (
        "WARNING: firm capacity would change the G0 scenario-0 fallback classification "
        "for the same case. This requires PI attention before denominator-dependent "
        "model-error envelopes are frozen."
        if diagnostic.firm_classifies_differently
        else "Firm capacity does not change the scenario-0 baseline fallback classification "
        "in this diagnostic, although it doubles the reported loading ratio for the two "
        "identical units."
    )
    recommendation = (
        "Recommendation: keep the current total-nameplate convention for continuity with "
        "G0 unless the PI wants the study to represent firm `(n-1)` planning headroom. "
        "If firm capacity is selected later, update the denominator convention explicitly "
        "before freezing additive p.u. model-error envelopes."
    )
    return "\n".join(
        [
            "# E1.S1b Transformer Headroom Diagnostic",
            "",
            "Status: complete for E1.S1b review. This memo is the G1-C2 prerequisite",
            "for the PI's total-versus-firm nameplate decision; it does not sign or",
            "change G0, G1, or any denominator convention.",
            "",
            "## Scope",
            "",
            "This diagnostic uses SimBench scenario 0 full-year 15-minute profiles for",
            f"`{config['grid_code']}` only. It reports deterministic headroom for the",
            "existing baseline profiles and a linear multiplier to 0.95 p.u. under two",
            "denominator conventions. The multiplier is a routing diagnostic only, not",
            "a Dutch 2035 loading result, forecast, planning threshold, or scientific",
            "claim; the E2/E3 technology layer does not yet exist.",
            "",
            "## Evidence",
            "",
            f"- Input config: `{config['config_path_label']}`",
            f"- Manifest: `{config['manifest_path']}`",
            f"- Report: `{report_path.as_posix()}`",
            f"- Numeric table: `{table_path.as_posix()}`",
            "- Prior inventory reference: `reports/grid_inventory.md`",
            "- G1-A1 denominator/envelope reference:",
            "  `reports/G1_A1_MODEL_ERROR_AMENDMENT_PROPOSAL.md`",
            "",
            "## Decision Transformer And Parallel Operation",
            "",
            f"- Pandapower element table/indexes: `net.trafo` {list(diagnostic.transformer_indices)}",
            f"- Unit count: {len(diagnostic.nameplate_mva)}",
            f"- Per-unit nameplate MVA: {list(diagnostic.nameplate_mva)}",
            f"- Busbar/tie status: {diagnostic.busbar_parallel_status}",
            "",
            _markdown_table(trafo_rows),
            "",
            _markdown_table(switch_rows),
            "",
            "## Total Versus Firm Headroom",
            "",
            _markdown_table(summary),
            "",
            "Firm convention used here: "
            f"{diagnostic.outage_convention}. With two equal 40 MVA units, this leaves",
            "one 40 MVA unit available.",
            "",
            "The existing G0 fallback criterion for scenario-0 baseline loading is",
            f"`L_base > {float(config['fallback_threshold_pu']):.2f}` under the currently",
            "signed total-nameplate definition. Under that signed definition, the",
            f"criterion is triggered: `{str(diagnostic.g0_fallback_total_triggered).lower()}`.",
            "",
            firm_warning,
            "",
            "## Implications For Model-Error Envelopes",
            "",
            "- Additive p.u. envelopes depend on the selected nameplate denominator. A",
            "  fixed MVA discrepancy divided by total nameplate is not the same p.u.",
            "  value when divided by firm capacity.",
            "- Relative envelopes are invariant to the nameplate convention because the",
            "  same multiplicative factor applies to either denominator.",
            "",
            "## Recommendation",
            "",
            recommendation,
            "",
        ]
    )
def _headroom_row(
    diagnostic: TransformerHeadroom,
    *,
    config: Mapping[str, Any],
) -> dict[str, object]:
    return {
        "scenario": int(config["scenario"]),
        "grid_code": config["grid_code"],
        "transformer_indices": list(diagnostic.transformer_indices),
        "unit_count": len(diagnostic.nameplate_mva),
        "unit_nameplate_mva": list(diagnostic.nameplate_mva),
        "total_nameplate_mva": diagnostic.total_nameplate_mva,
        "firm_n_minus_1_nameplate_mva": diagnostic.firm_nameplate_mva,
        "peak_import_mva": diagnostic.peak_import_mva,
        "peak_import_timestamp": diagnostic.peak_import_timestamp.isoformat(),
        "peak_import_loading_total_pu": diagnostic.peak_import_loading_total_pu,
        "peak_import_loading_firm_pu": diagnostic.peak_import_loading_firm_pu,
        "multiplier_to_0_95_total": diagnostic.multiplier_to_095_total,
        "multiplier_to_0_95_firm": diagnostic.multiplier_to_095_firm,
        "g0_total_nameplate_fallback_triggered": diagnostic.g0_fallback_total_triggered,
        "firm_capacity_fallback_triggered": diagnostic.firm_capacity_fallback_triggered,
        "firm_classifies_differently": diagnostic.firm_classifies_differently,
    }


def _validation_finding(
    *,
    coverage: pd.DataFrame,
    summary: pd.DataFrame,
    top_counts: Sequence[int],
) -> str:
    rows: list[str] = []
    for _, scenario_summary in summary.iterrows():
        scenario = int(scenario_summary["scenario"])
        scenario_coverage = coverage.loc[coverage["scenario"] == scenario]
        row_parts = []
        for top_count in top_counts:
            column = f"top_{top_count}_coverage"
            row_parts.append(f"top {top_count}: {float(scenario_coverage[column].max()):.1%}")
        annual_note = (
            "winter"
            if bool(scenario_summary["annual_top_step_is_winter"])
            else "outside winter"
        )
        rows.append(
            f"- Scenario {scenario}: annual peak is {annual_note}; maximum coverage across "
            f"all ranked winter weeks is {', '.join(row_parts)}."
        )
    rows.append(
        "- None of the scenario/window diagnostics reaches the 95% reference line in this "
        "SimBench-only screen. E9.S3 still has to perform the full-year screen specified "
        "in the plan before any critical-window claim is treated as validated."
    )
    return "\n".join(rows)


def _sum_optional_profile(
    profile: pd.DataFrame | None,
    expected_rows: int,
    index: pd.Index,
) -> pd.Series:
    if profile is None or profile.empty:
        return pd.Series(np.zeros(expected_rows), index=index, dtype=float)
    if len(profile) != expected_rows:
        raise ValueError("optional profile row count does not match load profiles")
    return profile.sum(axis=1).astype(float)


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    rows = [
        "| " + " | ".join(_format_markdown_value(value) for value in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    ]
    return "\n".join([header, separator, *rows])


def _format_markdown_value(value: object) -> str:
    if isinstance(value, (list, tuple)):
        return str(list(value))
    if pd.isna(value):
        return "n/a"
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value)


def _try_write_parquet(frame: pd.DataFrame, path: Path) -> bool:
    try:
        frame.to_parquet(path, index=False)
    except ImportError:
        return False
    return True


def _write_import_window_plot(
    coverage: pd.DataFrame,
    *,
    coverage_column: str,
    target: float,
    output_path: Path,
) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4))
    for scenario, scenario_rows in coverage.groupby("scenario"):
        ax.plot(
            scenario_rows["week_rank"],
            scenario_rows[coverage_column],
            marker="o",
            label=f"scenario {scenario}",
        )
    ax.axhline(target, color="0.4", linestyle="--", linewidth=1, label=f"{target:.0%} target")
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("number of annual import-ranked weeks")
    ax.set_ylabel(coverage_column.replace("_", " "))
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def _write_plots(
    profiles: Sequence[ScenarioProfile],
    coverage: pd.DataFrame,
    *,
    loading_plot: Path,
    coverage_plot: Path,
) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4))
    for profile in profiles:
        weekly = profile.loading_pu.resample("W-MON", label="left", closed="left").max()
        ax.plot(weekly.index, weekly.to_numpy(), label=f"scenario {profile.scenario}")
    ax.set_ylabel("weekly max loading (p.u.)")
    ax.set_xlabel("synthetic profile week")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(loading_plot, dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    for scenario, scenario_rows in coverage.groupby("scenario"):
        ax.plot(
            scenario_rows["week_rank"],
            scenario_rows["top_96_coverage"],
            marker="o",
            label=f"scenario {scenario}",
        )
    ax.axhline(0.95, color="0.4", linestyle="--", linewidth=1, label="95% reference")
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("number of ranked winter weeks")
    ax.set_ylabel("coverage of annual top 96 steps")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(coverage_plot, dpi=160)
    plt.close(fig)


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entrypoint for E1.S3/E1.S3b output generation."""

    parser = argparse.ArgumentParser(description="Generate profile-window artifacts.")
    parser.add_argument("--config", default="reports/critical_weeks_input.json")
    args = parser.parse_args(argv)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if config.get("task_id") == "E1.S1b":
        write_transformer_headroom_outputs(args.config)
    elif config.get("task_id") == "E1.S3b":
        write_import_window_outputs(args.config)
    else:
        write_critical_week_outputs(args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
