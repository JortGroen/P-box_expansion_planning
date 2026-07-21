from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from src.baseline_model import (
    BASELINE_COMPONENT,
    BaselineLoadTrajectory,
    BaselineTrajectoryLibrary,
    validate_canonical_calendar,
)


def _calendar(n_steps: int = 96) -> tuple[datetime, ...]:
    start = datetime(2025, 1, 3, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
    return tuple(start + timedelta(minutes=15 * index) for index in range(n_steps))


def _trajectory(
    *,
    trajectory_id: str = "baseline_a",
    timestamps: tuple[datetime, ...] | None = None,
) -> BaselineLoadTrajectory:
    axis = timestamps or _calendar()
    values = np.column_stack(
        [
            np.arange(len(axis), dtype=np.float64),
            np.arange(len(axis), dtype=np.float64) + 100.0,
        ]
    )
    return BaselineLoadTrajectory(
        timestamps=axis,
        load_kw=values,
        trajectory_id=trajectory_id,
        source_id="synthetic_baseline_fixture",
    )


def test_baseline_trajectory_records_alea_metadata_without_congestion_claims() -> None:
    trajectory = _trajectory()
    metadata = trajectory.metadata().manifest_record()

    assert metadata["component"] == BASELINE_COMPONENT
    assert metadata["trajectory_id"] == "baseline_a"
    assert metadata["calendar_timezone"] == "Europe/Amsterdam"
    assert metadata["n_timesteps"] == 96
    assert metadata["n_series"] == 2
    assert metadata["preserves_temporal_order"] is True
    assert metadata["weekday_weekend_preserved"] is True
    assert metadata["seasonal_order_preserved"] is True
    assert metadata["congestion_evaluated"] is False
    assert metadata["adequacy_certified"] is False
    assert len(str(metadata["time_axis_sha256"])) == 64
    assert len(str(metadata["values_sha256"])) == 64


def test_complete_trajectory_values_and_calendar_order_are_preserved() -> None:
    trajectory = _trajectory()
    values = trajectory.values()

    assert np.array_equal(values[:, 0], np.arange(96, dtype=np.float64))
    assert trajectory.weekday_weekend_labels()[:4] == ("weekday", "weekday", "weekday", "weekday")
    assert set(trajectory.season_labels()) == {"winter"}
    values[0, 0] = -999.0
    assert trajectory.values()[0, 0] == 0.0


def test_library_selection_is_deterministic_and_manifestable() -> None:
    first = _trajectory(trajectory_id="baseline_a")
    second = _trajectory(trajectory_id="baseline_b")
    library = BaselineTrajectoryLibrary((first, second))

    assert library.n_trajectories == 2
    assert library.trajectory(0).trajectory_id == "baseline_a"
    assert library.trajectory(0).trajectory_id == "baseline_a"
    assert [record["trajectory_id"] for record in library.metadata_records()] == [
        "baseline_a",
        "baseline_b",
    ]


def test_calendar_validation_rejects_mismatched_timestamps() -> None:
    trajectory = _trajectory()
    mismatched = tuple(item + timedelta(minutes=15) for item in _calendar())

    with pytest.raises(ValueError, match="canonical calendar"):
        trajectory.require_calendar(mismatched)

    with pytest.raises(ValueError, match="canonical calendar"):
        BaselineTrajectoryLibrary((trajectory, _trajectory(timestamps=mismatched)))


def test_calendar_validation_rejects_naive_and_non_15_minute_axes() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        validate_canonical_calendar((datetime(2025, 1, 1, 0, 0),))

    bad_spacing = (
        datetime(2025, 1, 1, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam")),
        datetime(2025, 1, 1, 0, 10, tzinfo=ZoneInfo("Europe/Amsterdam")),
    )
    with pytest.raises(ValueError, match="15-minute"):
        validate_canonical_calendar(bad_spacing)


def test_load_validation_reports_clear_errors() -> None:
    axis = _calendar(4)

    with pytest.raises(ValueError, match="length"):
        BaselineLoadTrajectory(
            timestamps=axis,
            load_kw=np.ones(3),
            trajectory_id="short",
            source_id="fixture",
        )

    values = np.ones(4)
    values[2] = np.nan
    with pytest.raises(ValueError, match="finite"):
        BaselineLoadTrajectory(
            timestamps=axis,
            load_kw=values,
            trajectory_id="nan",
            source_id="fixture",
        )
