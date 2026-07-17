from __future__ import annotations

import pandas as pd
import pytest

from src.profiles import (
    ScenarioProfile,
    aggregate_loading_from_profiles,
    annual_timestamps,
    choose_adaptive_window_count,
    count_overload_episodes,
    firm_nameplate_after_largest_unit_outage,
    coverage_by_rank,
    rank_annual_weeks,
    rank_winter_weeks,
    split_import_export_loading,
    transformer_headroom_diagnostic,
)


def test_annual_timestamps_are_15_minute_utc() -> None:
    timestamps = annual_timestamps(3, start="2016-01-01T00:00:00Z", step_minutes=15)

    assert list(timestamps.astype(str)) == [
        "2016-01-01 00:00:00+00:00",
        "2016-01-01 00:15:00+00:00",
        "2016-01-01 00:30:00+00:00",
    ]


def test_aggregate_loading_counts_reverse_flow_direction_agnostically() -> None:
    load_p = pd.DataFrame({"load_a": [4.0, 1.0]})
    load_q = pd.DataFrame({"load_a": [3.0, 0.0]})
    sgen_p = pd.DataFrame({"pv_a": [0.0, 6.0]})

    loading, net_p, net_q = aggregate_loading_from_profiles(
        load_p_mw=load_p,
        load_q_mvar=load_q,
        sgen_p_mw=sgen_p,
        sgen_q_mvar=None,
        rating_mva=10.0,
    )

    assert list(loading.round(6)) == [0.5, 0.5]
    assert list(net_p) == [4.0, -5.0]
    assert list(net_q) == [3.0, 0.0]


def test_split_import_export_loading_uses_g0_a1_direction_rules() -> None:
    index = pd.date_range("2016-01-01T00:00:00Z", periods=3, freq="15min")
    loading = pd.Series([0.5, 0.6, 0.7], index=index)
    net_p = pd.Series([2.0, -1.0, 0.0], index=index)

    split = split_import_export_loading(loading_pu=loading, aggregate_p_mw=net_p)

    assert list(split.import_loading_pu) == [0.5, 0.0, 0.0]
    assert list(split.export_loading_pu) == [0.0, 0.6, 0.0]
    assert list(split.direction) == ["import", "export", "zero"]


def test_direction_flips_reset_overload_episode_counter() -> None:
    index = pd.date_range("2016-01-01T00:00:00Z", periods=8, freq="15min")
    raw_loading = pd.Series([1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2], index=index)
    net_p = pd.Series([1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0, 1.0], index=index)

    split = split_import_export_loading(loading_pu=raw_loading, aggregate_p_mw=net_p)

    assert count_overload_episodes(split.import_loading_pu, min_consecutive_steps=4) == 1
    assert count_overload_episodes(split.export_loading_pu, min_consecutive_steps=4) == 0


def test_rank_winter_weeks_orders_by_weekly_max_loading() -> None:
    timestamps = pd.date_range("2016-01-01T00:00:00Z", periods=16, freq="D")
    loading = pd.Series(
        [0.2, 1.0, 0.1, 0.3, 0.4, 0.5, 0.6, 0.7, 0.2, 0.9, 0.1, 0.3, 0.4, 0.5, 0.6, 0.7],
        index=timestamps,
    )

    ranked = rank_winter_weeks(loading, winter_months=(1,))

    assert ranked.loc[0, "week_rank"] == 1
    assert ranked.loc[0, "max_loading_pu"] == pytest.approx(1.0)
    assert ranked.loc[0, "top_timestamp"] == timestamps[1]
    assert set(ranked["steps_in_winter_months"]) == {3, 6, 7}


def test_rank_annual_weeks_includes_non_winter_peaks() -> None:
    timestamps = pd.date_range("2016-01-01T00:00:00Z", periods=220, freq="D")
    values = [0.1] * len(timestamps)
    values[200] = 1.0
    loading = pd.Series(values, index=timestamps)

    ranked = rank_annual_weeks(loading)

    assert ranked.loc[0, "top_timestamp"] == timestamps[200]


def test_coverage_by_rank_accumulates_selected_week_windows() -> None:
    timestamps = pd.date_range("2016-01-04T00:00:00Z", periods=14, freq="D")
    loading = pd.Series([1.0, 0.9, 0.8, 0.7, 0.1, 0.1, 0.1, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.1], index=timestamps)
    ranked = pd.DataFrame(
        {
            "week_rank": [1, 2],
            "week_start": [timestamps[7], timestamps[0]],
            "week_end_exclusive": [timestamps[7] + pd.Timedelta(days=7), timestamps[0] + pd.Timedelta(days=7)],
        }
    )

    coverage = coverage_by_rank(loading, ranked, top_counts=(4,))

    assert list(coverage["top_4_coverage"]) == [0.0, 1.0]


def test_choose_adaptive_window_count_adds_margin_after_target() -> None:
    coverage = pd.DataFrame(
        {
            "week_rank": [1, 2, 3],
            "top_672_coverage": [0.5, 0.95, 1.0],
        }
    )

    choice = choose_adaptive_window_count(
        coverage,
        coverage_column="top_672_coverage",
        target=0.95,
        margin_weeks=1,
    )

    assert choice == {
        "base_k": 2,
        "margin_weeks": 1,
        "selected_k": 3,
        "selected_coverage": 1.0,
        "target": 0.95,
        "target_feasible": True,
    }


def test_firm_nameplate_after_largest_unit_outage_uses_remaining_capacity() -> None:
    assert firm_nameplate_after_largest_unit_outage([40.0, 40.0]) == 40.0
    assert firm_nameplate_after_largest_unit_outage([25.0, 40.0, 63.0]) == 65.0


def test_transformer_headroom_diagnostic_compares_total_and_firm_denominators() -> None:
    index = pd.date_range("2016-01-01T00:00:00Z", periods=4, freq="15min")
    profile = ScenarioProfile(
        scenario=0,
        grid_code="toy",
        loading_pu=pd.Series([0.2, 0.3, 0.1, 0.25], index=index),
        timestamps=index,
        aggregate_p_mw=pd.Series([1.0, 1.0, -1.0, 1.0], index=index),
        aggregate_q_mvar=pd.Series([0.0, 0.0, 0.0, 0.0], index=index),
        rating_mva=80.0,
    )

    diagnostic = transformer_headroom_diagnostic(
        profile,
        nameplate_mva=[40.0, 40.0],
        transformer_indices=[0, 1],
        busbar_parallel_status="closed test bank",
        fallback_threshold_pu=0.5,
        target_loading_pu=0.95,
    )

    assert diagnostic.peak_import_timestamp == index[1]
    assert diagnostic.peak_import_mva == pytest.approx(24.0)
    assert diagnostic.peak_import_loading_total_pu == pytest.approx(0.3)
    assert diagnostic.peak_import_loading_firm_pu == pytest.approx(0.6)
    assert diagnostic.multiplier_to_095_total == pytest.approx(0.95 / 0.3)
    assert diagnostic.multiplier_to_095_firm == pytest.approx(0.95 / 0.6)
    assert diagnostic.g0_fallback_total_triggered is False
    assert diagnostic.firm_capacity_fallback_triggered is True
    assert diagnostic.firm_classifies_differently is True
