from __future__ import annotations

import pandas as pd
import pytest

from src.profiles import (
    aggregate_loading_from_profiles,
    annual_timestamps,
    coverage_by_rank,
    rank_winter_weeks,
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
