import json
from pathlib import Path

import pandas as pd
import pytest

from src.profiles import (
    TransformerHeadroom,
    critical_week_report,
    import_window_report,
    transformer_headroom_report,
)
from src.runner import AdapterResult, ExperimentRunner, _grid_inventory_report, _laptop_benchmark_report


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
    assert "- Standard claim-source manifest: `experiments/example/manifest.json`" in report
    assert "- Retained/custom evidence: `experiments/example/custom_evidence.json`" in report
    assert "experiments/example/reports/critical_weeks_validation.md" in report
    assert "experiments/example/data/critical_weeks.csv" in report
    assert "experiments/example/reports/critical_week_loading.png" in report
    assert "`data/critical_weeks.csv`" not in report
    assert "`reports/critical_week_loading.png`" not in report
    assert "- Manifest:" not in report

def test_import_window_report_uses_configured_artifact_paths() -> None:
    frame = pd.DataFrame([{"scenario": 0, "week_rank": 1}])
    config = {
        "report_top_week_rows": 1,
        "top_count": 672,
        "coverage_target": 0.95,
        "margin_weeks": 1,
        "output_dir": "experiments/example_import/data",
        "figure_dir": "experiments/example_import/reports",
        "config_path_label": "experiments/example_import/runner_config.json",
        "manifest_path": "experiments/example_import/custom_evidence.json",
        "report_path": "experiments/example_import/reports/import_window_diagnostic.md",
    }

    report = import_window_report(
        config=config,
        import_windows=frame,
        coverage=frame,
        proposal=pd.DataFrame([{"scenario": 0, "target_feasible": True}]),
        export=pd.DataFrame([{"scenario": 0, "max_export_loading_pu": 0.0}]),
    )

    assert "- Standard claim-source manifest: `experiments/example_import/manifest.json`" in report
    assert "- Retained/custom evidence: `experiments/example_import/custom_evidence.json`" in report
    assert "experiments/example_import/data/import_windows.csv" in report
    assert "`data/import_windows.csv`" not in report
    assert "- Manifest:" not in report


def test_transformer_headroom_report_states_g1_a2_capacity_status() -> None:
    diagnostic = TransformerHeadroom(
        transformer_indices=(0, 1),
        nameplate_mva=(40.0, 40.0),
        total_nameplate_mva=80.0,
        firm_nameplate_mva=40.0,
        outage_convention="firm (n-1) test convention",
        busbar_parallel_status="closed bus-tie test status",
        peak_import_mva=12.0,
        peak_import_timestamp=pd.Timestamp("2016-01-01T00:00:00Z"),
        peak_import_loading_total_pu=0.15,
        peak_import_loading_firm_pu=0.30,
        multiplier_to_095_total=6.3333333333,
        multiplier_to_095_firm=3.1666666667,
        g0_fallback_total_triggered=False,
        firm_capacity_fallback_triggered=False,
        firm_classifies_differently=False,
    )
    trafo_detail = pd.DataFrame(
        [
            {
                "name": "T0",
                "hv_bus": 1,
                "lv_bus": 2,
                "sn_mva": 40.0,
                "parallel": 1,
                "tap_pos": 0,
                "in_service": True,
            }
        ]
    )
    switch_detail = pd.DataFrame(
        [{"bus": 1, "element": 2, "et": "b", "closed": True, "type": "CB", "name": "tie"}]
    )
    config = {
        "scenario": 0,
        "grid_code": "test-grid",
        "fallback_threshold_pu": 0.85,
        "output_dir": "experiments/example_headroom/data",
        "config_path_label": "experiments/example_headroom/runner_config.json",
        "manifest_path": "experiments/example_headroom/custom_evidence.json",
        "report_path": "experiments/example_headroom/reports/transformer_headroom_diagnostic.md",
    }

    report = transformer_headroom_report(
        config=config,
        diagnostic=diagnostic,
        trafo_detail=trafo_detail,
        switch_detail=switch_detail,
    )

    assert "- Standard claim-source manifest: `experiments/example_headroom/manifest.json`" in report
    assert "- Retained/custom evidence: `experiments/example_headroom/custom_evidence.json`" in report
    assert "G1-A2 fixes the grid-model discrepancy as a symmetric relative" in report
    assert "open until E3.S2b reports raw future-layer MVA" in report
    assert "one-transformer-out topology with AC power flow" in report
    assert "G1-A1 denominator/envelope reference" not in report
    assert "- Manifest:" not in report

def test_grid_inventory_report_uses_runner_artifact_paths() -> None:
    report = _grid_inventory_report(
        {
            "output_dir": "experiments/example_inventory",
            "command": ".\\.venv\\Scripts\\python.exe -m src.runner experiments/example_inventory/runner_config.json",
            "historical_input_path": "reports/grid_inventory_input.json",
        },
        [],
        Path("experiments/example_inventory/runner_config.json"),
    )

    assert "experiments/example_inventory/runner_config.json" in report
    assert "- Standard claim-source manifest: `experiments/example_inventory/manifest.json`" in report
    assert "- Retained/custom evidence: `experiments/example_inventory/custom_evidence.json`" in report
    assert "experiments/example_inventory/grid_inventory_rows.json" in report
    assert "experiments/example_inventory/grid_inventory.md" in report
    assert "reports/grid_inventory_input.json" not in report
    assert "- Manifest:" not in report


def test_laptop_benchmark_report_labels_standard_and_custom_evidence() -> None:
    report = _laptop_benchmark_report(
        {
            "config": {"output_dir": "experiments/example_benchmark"},
            "results": [
                {
                    "grid_key": "grid",
                    "backend": "backend",
                    "elapsed_s": {"median": 0.001},
                    "converged_all": True,
                }
            ],
        },
        Path("experiments/example_benchmark/runner_config.json"),
    )

    assert "experiments/example_benchmark/manifest.json" in report
    assert "experiments/example_benchmark/custom_evidence.json" in report
    assert "- Manifest:" not in report
