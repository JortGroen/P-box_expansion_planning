import json
from pathlib import Path

import pandas as pd
import pytest

from src.profiles import critical_week_report
from src.runner import AdapterResult, ExperimentRunner


def test_experiment_runner_writes_manifest_and_comparison(tmp_path: Path) -> None:
    config_path = tmp_path / "runner_config.json"
    output_dir = tmp_path / "experiment"
    historical = tmp_path / "historical.txt"
    historical.write_text("same\n", encoding="utf-8")
    config_path.write_text(
        json.dumps(
            {
                "task_id": "T0",
                "adapter": "test.adapter",
                "adapter_version": "v1",
                "output_dir": output_dir.as_posix(),
                "seeds": {"root": 7},
                "comparisons": [
                    {
                        "label": "same output",
                        "generated_artifact": "result",
                        "historical_path": historical.as_posix(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def adapter(config: dict[str, object], path: Path) -> AdapterResult:
        result = Path(config["output_dir"]) / "result.txt"
        result.write_text("same\n", encoding="utf-8")
        return AdapterResult(
            output_paths=(result,),
            artifacts={"result": result},
            metadata={"test_adapter": True},
        )

    manifest = ExperimentRunner({"test.adapter.v1": adapter}).run(config_path)

    manifest_path = output_dir / "manifest.json"
    comparison_path = output_dir / "comparison.json"
    assert manifest_path.is_file()
    assert comparison_path.is_file()
    assert manifest["seeds"] == {"root": 7}
    assert manifest["extra"]["adapter"] == "test.adapter"
    assert manifest["extra"]["adapter_version"] == "v1"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    assert comparison[0]["match"] is True


def test_experiment_runner_rejects_unknown_adapter(tmp_path: Path) -> None:
    config_path = tmp_path / "runner_config.json"
    config_path.write_text(
        json.dumps(
            {
                "task_id": "T0",
                "adapter": "missing",
                "adapter_version": "v1",
                "output_dir": (tmp_path / "experiment").as_posix(),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(KeyError, match="Unknown experiment adapter"):
        ExperimentRunner({}).run(config_path)


def test_e1_s3b_runner_config_preserves_historical_threshold() -> None:
    config = json.loads(
        Path("experiments/e1_s3b_import_window/runner_config.json").read_text(encoding="utf-8")
    )

    assert config["historical_threshold_pu"] == 1.0
    assert config["diagnostic_config"]["threshold_pu"] == 1.0


def test_comparison_requires_existing_historical_file(tmp_path: Path) -> None:
    config_path = tmp_path / "runner_config.json"
    output_dir = tmp_path / "experiment"
    config_path.write_text(
        json.dumps(
            {
                "task_id": "T0",
                "adapter": "test.adapter",
                "adapter_version": "v1",
                "output_dir": output_dir.as_posix(),
                "comparisons": [
                    {
                        "label": "missing historical",
                        "generated_artifact": "result",
                        "historical_path": (tmp_path / "missing.txt").as_posix(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def adapter(config: dict[str, object], path: Path) -> AdapterResult:
        result = Path(config["output_dir"]) / "result.txt"
        result.write_text("generated\n", encoding="utf-8")
        return AdapterResult(output_paths=(result,), artifacts={"result": result}, metadata={})

    with pytest.raises(FileNotFoundError, match="Historical comparison file is missing"):
        ExperimentRunner({"test.adapter.v1": adapter}).run(config_path)


def test_comparison_requires_declared_expected_difference(tmp_path: Path) -> None:
    config_path = tmp_path / "runner_config.json"
    output_dir = tmp_path / "experiment"
    historical = tmp_path / "historical.txt"
    historical.write_text("historical\n", encoding="utf-8")
    config_path.write_text(
        json.dumps(
            {
                "task_id": "T0",
                "adapter": "test.adapter",
                "adapter_version": "v1",
                "output_dir": output_dir.as_posix(),
                "comparisons": [
                    {
                        "label": "undeclared mismatch",
                        "generated_artifact": "result",
                        "historical_path": historical.as_posix(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def adapter(config: dict[str, object], path: Path) -> AdapterResult:
        result = Path(config["output_dir"]) / "result.txt"
        result.write_text("generated\n", encoding="utf-8")
        return AdapterResult(output_paths=(result,), artifacts={"result": result}, metadata={})

    with pytest.raises(AssertionError, match="differs without declared expected_difference"):
        ExperimentRunner({"test.adapter.v1": adapter}).run(config_path)


def test_critical_week_report_uses_configured_artifact_paths() -> None:
    summary = pd.DataFrame(
        [
            {
                "scenario": 0,
                "annual_top_step_is_winter": True,
            }
        ]
    )
    critical_weeks = pd.DataFrame(
        [
            {
                "scenario": 0,
                "week_rank": 1,
                "week_start": pd.Timestamp("2016-01-04T00:00:00Z"),
                "week_end_exclusive": pd.Timestamp("2016-01-11T00:00:00Z"),
                "max_loading_pu": 0.5,
            }
        ]
    )
    coverage = pd.DataFrame(
        [
            {
                "scenario": 0,
                "week_rank": 1,
                "top_24_coverage": 1.0,
            }
        ]
    )
    config = {
        "report_top_week_rows": 1,
        "output_dir": "experiments/example/data",
        "figure_dir": "experiments/example/reports",
        "config_path_label": "experiments/example/runner_config.json",
        "manifest_path": "experiments/example/custom_evidence.json",
        "report_path": "experiments/example/reports/critical_weeks_validation.md",
        "profile_start": "2016-01-01T00:00:00Z",
        "step_minutes": 15,
        "winter_months": [12, 1, 2],
        "top_counts": [24],
    }

    report = critical_week_report(
        config=config,
        summary=summary,
        critical_weeks=critical_weeks,
        coverage=coverage,
        parquet_written=False,
    )

    assert "experiments/example/runner_config.json" in report
    assert "experiments/example/custom_evidence.json" in report
    assert "experiments/example/reports/critical_weeks_validation.md" in report
    assert "experiments/example/data/critical_weeks.csv" in report
    assert "experiments/example/reports/critical_week_loading.png" in report
    assert "`data/critical_weeks.csv`" not in report
    assert "`reports/critical_week_loading.png`" not in report
