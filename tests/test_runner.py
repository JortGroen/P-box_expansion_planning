import json
from pathlib import Path

import pytest

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
