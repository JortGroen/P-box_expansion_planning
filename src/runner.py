"""ExperimentRunner and versioned adapters for governed project diagnostics."""

from __future__ import annotations

import argparse
import copy
import json
import statistics
import time
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from src.grid_loader import inventory_markdown, inventory_rows, load_candidate_grid
from src.manifest import build_manifest, sha256_file, write_manifest


Adapter = Callable[[Mapping[str, Any], Path], "AdapterResult"]


@dataclass(frozen=True)
class AdapterResult:
    """Files and metadata produced by one versioned runner adapter."""

    output_paths: tuple[Path, ...]
    artifacts: Mapping[str, Path]
    metadata: Mapping[str, Any]


class ExperimentRunner:
    """Run one versioned experiment config and write the standard manifest."""

    def __init__(self, adapters: Mapping[str, Adapter] | None = None) -> None:
        self.adapters = dict(adapters or default_adapters())

    def run(self, config_path: str | Path) -> dict[str, Any]:
        path = Path(config_path)
        config = json.loads(path.read_text(encoding="utf-8"))
        adapter_key = _adapter_key(config)
        try:
            adapter = self.adapters[adapter_key]
        except KeyError as exc:
            valid = ", ".join(sorted(self.adapters))
            raise KeyError(f"Unknown experiment adapter {adapter_key!r}. Valid adapters: {valid}") from exc

        output_dir = Path(config["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        result = adapter(config, path)
        comparison_path = _write_comparison(config, result.artifacts, output_dir)
        output_paths = [*result.output_paths]
        if comparison_path is not None:
            output_paths.append(comparison_path)

        manifest = build_manifest(
            config_path=path,
            seeds=config.get("seeds", {"none": "deterministic"}),
            output_paths=output_paths,
            extra={
                "artifact_type": "experiment_runner_manifest",
                "task_id": config["task_id"],
                "adapter": config["adapter"],
                "adapter_version": config["adapter_version"],
                "timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                **dict(result.metadata),
            },
        )
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return manifest


def default_adapters() -> dict[str, Adapter]:
    return {
        "bootstrap.smoke.v1": _run_bootstrap_smoke,
        "e0.s3b.reconciliation.v1": _run_reconciliation_suite,
        "e1.s1.grid_inventory.v1": _run_grid_inventory,
        "e1.s2.laptop_benchmark.v1": _run_laptop_benchmark,
        "e1.s3.critical_weeks.v1": _run_profile_diagnostic,
        "e1.s3b.import_window.v1": _run_profile_diagnostic,
        "e1.s1b.transformer_headroom.v1": _run_profile_diagnostic,
        "e1.s2b.timeseriescpp_benchmark.v1": _run_timeseriescpp_benchmark,
    }


def _adapter_key(config: Mapping[str, Any]) -> str:
    return f"{config['adapter']}.{config['adapter_version']}"


def _run_bootstrap_smoke(config: Mapping[str, Any], config_path: Path) -> AdapterResult:
    output_dir = Path(config["output_dir"])
    smoke_output = output_dir / "bootstrap_output.txt"
    smoke_output.write_text(
        "bootstrap manifest smoke run; not a scientific experiment\n",
        encoding="utf-8",
    )
    return AdapterResult(
        output_paths=(smoke_output,),
        artifacts={"bootstrap_output": smoke_output},
        metadata={"scientific_result": False, "legacy_entrypoint": "preserved"},
    )


def _run_grid_inventory(config: Mapping[str, Any], config_path: Path) -> AdapterResult:
    output_dir = Path(config["output_dir"])
    rows = inventory_rows()
    selected = set(config.get("candidate_grid_keys", []))
    if selected:
        rows = [row for row in rows if row["key"] in selected]

    raw_path = output_dir / "grid_inventory_rows.json"
    report_path = output_dir / "grid_inventory.md"
    custom_evidence_path = output_dir / "custom_evidence.json"
    raw_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(_grid_inventory_report(config, rows, config_path), encoding="utf-8")
    custom_manifest = build_manifest(
        config_path=config_path,
        seeds={"none": "deterministic"},
        output_paths=[raw_path, report_path],
        extra={
            "artifact_type": "grid_inventory_custom_reproduction",
            "task_id": "E1.S1",
            "command": config["command"],
            "candidate_grid_codes": [row["code"] for row in rows],
            "timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        },
    )
    custom_evidence_path.write_text(json.dumps(custom_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return AdapterResult(
        output_paths=(raw_path, report_path, custom_evidence_path),
        artifacts={"raw": raw_path, "report": report_path, "custom_evidence": custom_evidence_path},
        metadata={"historical_task": "E1.S1", "diagnostic_threshold_pu": "not_applicable"},
    )


def _grid_inventory_report(config: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], config_path: Path) -> str:
    return "\n".join(
        [
            "# E1.S1 Grid Inventory Runner Reproduction",
            "",
            "Status: ExperimentRunner reproduction of the accepted E1.S1 inventory.",
            "",
            "This artifact preserves the grid-inventory diagnostic as a runner-managed",
            "claim source. It does not run overload-event analysis and has no p.u.",
            "threshold to relabel under G0-A3.",
            "",
            "## Evidence",
            "",
            f"- Runner config: `{config_path.as_posix()}`",
            f"- Manifest: `{(Path(config['output_dir']) / 'manifest.json').as_posix()}`",
            f"- Data: `{(Path(config['output_dir']) / 'grid_inventory_rows.json').as_posix()}`",
            f"- Report: `{(Path(config['output_dir']) / 'grid_inventory.md').as_posix()}`",
            f"- Command: `{config['command']}`",
            "",
            inventory_markdown(list(rows)),
            "",
        ]
    )


def _run_laptop_benchmark(config: Mapping[str, Any], config_path: Path) -> AdapterResult:
    import pandapower as pp

    output_dir = Path(config["output_dir"])
    raw_path = output_dir / "benchmark_raw.json"
    report_path = output_dir / "BENCHMARK.md"
    custom_evidence_path = output_dir / "custom_evidence.json"
    warmups = int(config["warmups"])
    repeats = int(config["repeats"])
    common_kwargs = dict(config["runpp_kwargs_common"])
    raw: dict[str, Any] = {
        "schema_version": 1,
        "task_id": "E1.S2",
        "timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "config": dict(config),
        "results": [],
    }

    for grid in config["candidate_grids"]:
        for backend in config["backends"]:
            kwargs = {**common_kwargs, **backend["kwargs"]}
            for _ in range(warmups):
                net = load_candidate_grid(grid["key"])
                pp.runpp(net, **kwargs)
            timings: list[float] = []
            converged: list[bool] = []
            warnings_seen: list[str] = []
            for _ in range(repeats):
                net = load_candidate_grid(grid["key"])
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    start = time.perf_counter()
                    pp.runpp(net, **kwargs)
                    elapsed = time.perf_counter() - start
                timings.append(elapsed)
                converged.append(bool(net.converged))
                warnings_seen.extend(str(warning.message) for warning in caught)
            raw["results"].append(
                {
                    "grid_key": grid["key"],
                    "grid_code": grid["code"],
                    "backend": backend["name"],
                    "converged_all": all(converged),
                    "elapsed_s": {
                        "min": min(timings),
                        "median": statistics.median(timings),
                        "mean": statistics.fmean(timings),
                        "max": max(timings),
                    },
                    "warnings": sorted(set(warnings_seen)),
                }
            )

    raw_path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(_laptop_benchmark_report(raw, config_path), encoding="utf-8")
    custom_manifest = build_manifest(
        config_path=config_path,
        seeds={"none": "deterministic"},
        output_paths=[raw_path, report_path],
        extra={
            "artifact_type": "laptop_benchmark_custom_reproduction",
            "task_id": "E1.S2",
            "command": config["command"],
            "timestamp_utc": raw["timestamp_utc"],
            "warmups": warmups,
            "repeats": repeats,
        },
    )
    custom_evidence_path.write_text(json.dumps(custom_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return AdapterResult(
        output_paths=(raw_path, report_path, custom_evidence_path),
        artifacts={"raw": raw_path, "report": report_path, "custom_evidence": custom_evidence_path},
        metadata={"historical_task": "E1.S2", "diagnostic_threshold_pu": "not_applicable"},
    )


def _laptop_benchmark_report(raw: Mapping[str, Any], config_path: Path) -> str:
    rows = [
        {
            "grid": row["grid_key"],
            "backend": row["backend"],
            "median_ms": float(row["elapsed_s"]["median"]) * 1000.0,
            "converged_all": row["converged_all"],
        }
        for row in raw["results"]
    ]
    return "\n".join(
        [
            "# E1.S2 Laptop Benchmark Runner Reproduction",
            "",
            "Status: ExperimentRunner reproduction of the historical high-level",
            "`pandapower.runpp` benchmark. Timing values are expected to differ from",
            "the retained custom evidence because this is a fresh wall-clock run.",
            "",
            "## Evidence",
            "",
            f"- Runner config: `{config_path.as_posix()}`",
            "- Standard manifest: `manifest.json` in this experiment directory",
            "",
            _markdown_table(rows),
            "",
            "No claim is made that AC power flow is infeasible; this remains a",
            "high-level orchestration benchmark only.",
            "",
        ]
    )


def _run_profile_diagnostic(config: Mapping[str, Any], config_path: Path) -> AdapterResult:
    from src.profiles import (
        write_critical_week_outputs,
        write_import_window_outputs,
        write_transformer_headroom_outputs,
    )

    diagnostic_config = _diagnostic_config(config, config_path)
    _ensure_generated_parents(config)
    runtime_config_path = Path(config["output_dir"]) / "diagnostic_config.runtime.json"
    runtime_config_path.write_text(json.dumps(diagnostic_config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    task_id = diagnostic_config["task_id"]
    if task_id == "E1.S1b":
        write_transformer_headroom_outputs(runtime_config_path)
    elif task_id == "E1.S3b":
        write_import_window_outputs(runtime_config_path)
    else:
        write_critical_week_outputs(runtime_config_path)

    output_paths = tuple(Path(path) for path in config["generated_output_paths"])
    artifacts = {name: Path(path) for name, path in config["generated_artifacts"].items()}
    return AdapterResult(
        output_paths=(runtime_config_path, *output_paths),
        artifacts=artifacts,
        metadata={
            "historical_task": task_id,
            "diagnostic_threshold_pu": diagnostic_config.get("threshold_pu", "not_applicable"),
            "historical_threshold_preserved": True,
        },
    )


def _diagnostic_config(config: Mapping[str, Any], config_path: Path) -> dict[str, Any]:
    diagnostic_config = copy.deepcopy(config["diagnostic_config"])
    diagnostic_config["command"] = config["command"]
    diagnostic_config["config_path_label"] = config_path.as_posix()
    return diagnostic_config


def _ensure_generated_parents(config: Mapping[str, Any]) -> None:
    for path in config.get("generated_output_paths", []):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    for path in config.get("generated_artifacts", {}).values():
        Path(path).parent.mkdir(parents=True, exist_ok=True)
def _run_timeseriescpp_benchmark(config: Mapping[str, Any], config_path: Path) -> AdapterResult:
    from src.evaluator_ac_benchmark import write_outputs

    diagnostic_config = _diagnostic_config(config, config_path)
    _ensure_generated_parents(config)
    runtime_config_path = Path(config["output_dir"]) / "diagnostic_config.runtime.json"
    runtime_config_path.write_text(json.dumps(diagnostic_config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_outputs(runtime_config_path)
    output_paths = tuple(Path(path) for path in config["generated_output_paths"])
    artifacts = {name: Path(path) for name, path in config["generated_artifacts"].items()}
    return AdapterResult(
        output_paths=(runtime_config_path, *output_paths),
        artifacts=artifacts,
        metadata={"historical_task": "E1.S2b", "diagnostic_threshold_pu": "not_applicable", "timing_rerun": True},
    )


def _run_reconciliation_suite(config: Mapping[str, Any], config_path: Path) -> AdapterResult:
    runner = ExperimentRunner()
    child_manifests: list[dict[str, Any]] = []
    rerun_children = bool(config.get("rerun_children", True))
    for child in config["child_config_paths"]:
        child_path = Path(child)
        if rerun_children:
            manifest = runner.run(child_path)
        else:
            child_config = json.loads(child_path.read_text(encoding="utf-8"))
            manifest_path = Path(child_config["output_dir"]) / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        child_manifests.append({"config_path": child_path.as_posix(), "manifest": manifest})

    output_dir = Path(config["output_dir"])
    raw_path = output_dir / "runner_retrofit_summary.json"
    report_path = Path(config["report_path"])
    summary = _suite_summary(config, child_manifests)
    raw_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(_suite_report(summary), encoding="utf-8")
    return AdapterResult(
        output_paths=(raw_path, report_path),
        artifacts={"raw": raw_path, "report": report_path},
        metadata={"historical_task": "E0.S3b", "child_runs": len(child_manifests)},
    )


def _suite_summary(config: Mapping[str, Any], child_manifests: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    for child in config["child_config_paths"]:
        child_path = Path(child)
        child_config = json.loads(child_path.read_text(encoding="utf-8"))
        output_dir = Path(child_config["output_dir"])
        comparison_path = output_dir / "comparison.json"
        comparisons = json.loads(comparison_path.read_text(encoding="utf-8")) if comparison_path.exists() else []
        diagnostics.append(
            {
                "task_id": child_config["task_id"],
                "adapter": _adapter_key(child_config),
                "config_path": child_path.as_posix(),
                "standard_manifest_path": (output_dir / "manifest.json").as_posix(),
                "comparison_path": comparison_path.as_posix() if comparison_path.exists() else None,
                "comparisons": comparisons,
                "historical_threshold_pu": child_config.get("historical_threshold_pu", "not_applicable"),
            }
        )
    return {
        "schema_version": 1,
        "task_id": "E0.S3b",
        "timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "diagnostics": diagnostics,
        "child_manifests": child_manifests,
    }


def _suite_report(summary: Mapping[str, Any]) -> str:
    rows = []
    for diagnostic in summary["diagnostics"]:
        comparisons = diagnostic["comparisons"]
        matched = sum(1 for row in comparisons if row["match"])
        rows.append(
            {
                "task_id": diagnostic["task_id"],
                "adapter": diagnostic["adapter"],
                "manifest": diagnostic["standard_manifest_path"],
                "historical_threshold_pu": diagnostic["historical_threshold_pu"],
                "checksum_matches": f"{matched}/{len(comparisons)}",
            }
        )
    discrepancy_lines: list[str] = []
    for diagnostic in summary["diagnostics"]:
        mismatches = [row for row in diagnostic["comparisons"] if not row["match"]]
        if not mismatches:
            discrepancy_lines.append(f"- {diagnostic['task_id']}: no checksum discrepancies in configured comparisons.")
            continue
        reasons = sorted({row.get("expected_difference", "unexpected checksum difference") for row in mismatches})
        discrepancy_lines.append(f"- {diagnostic['task_id']}: {'; '.join(reasons)}")

    return "\n".join(
        [
            "# E0.S3b ExperimentRunner Compliance Retrofit",
            "",
            "Status: runner reproduction complete for review. This report marks the",
            "standard `experiments/e1_*/manifest.json` files as the active claim-source",
            "manifests while retaining the historical custom evidence for traceability.",
            "",
            "Historical diagnostic thresholds are preserved as executed. In particular,",
            "the E1.S3b import-window diagnostic remains labeled at its configured",
            "`threshold_pu = 1.0`; it is not relabeled as the provisional G0-A3",
            "`1.1 p.u.` working event.",
            "",
            "## Migrated Diagnostics",
            "",
            _markdown_table(rows),
            "",
            "## Discrepancy Summary",
            "",
            "\n".join(discrepancy_lines),
            "",
            "## Boundaries",
            "",
            "- Q-5 remains open before integrated event-based scientific analysis or",
            "  manuscript event results.",
            "- No G0, G0-A3, G1, G2, IC schema, epsilon, or capacity-denominator decision",
            "  is changed by this retrofit.",
            "- Timing diagnostics are fresh wall-clock reproductions, so their numeric",
            "  timing files are expected to differ from retained historical evidence.",
            "",
        ]
    )


def _write_comparison(config: Mapping[str, Any], artifacts: Mapping[str, Path], output_dir: Path) -> Path | None:
    comparisons = config.get("comparisons", [])
    if not comparisons:
        return None
    rows = []
    for comparison in comparisons:
        label = comparison["label"]
        artifact_name = comparison["generated_artifact"]
        if artifact_name not in artifacts:
            raise KeyError(f"Comparison {label!r} references unknown generated artifact {artifact_name!r}")
        generated = artifacts[artifact_name]
        historical = Path(comparison["historical_path"])
        if not generated.is_file():
            raise FileNotFoundError(f"Generated comparison file is missing for {label!r}: {generated}")
        if not historical.is_file():
            raise FileNotFoundError(f"Historical comparison file is missing for {label!r}: {historical}")
        generated_sha = sha256_file(generated)
        historical_sha = sha256_file(historical)
        expected_difference = comparison.get("expected_difference")
        match = generated_sha == historical_sha
        if not match and not expected_difference:
            raise AssertionError(
                f"Comparison {label!r} differs without declared expected_difference: "
                f"generated={generated} historical={historical}"
            )
        rows.append(
            {
                "label": label,
                "generated_path": generated.as_posix(),
                "historical_path": historical.as_posix(),
                "generated_sha256": generated_sha,
                "historical_sha256": historical_sha,
                "match": match,
                "expected_difference": expected_difference,
            }
        )
    comparison_path = output_dir / "comparison.json"
    comparison_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return comparison_path

def _markdown_table(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return "_No rows._"
    columns = list(rows[0].keys())
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_format_markdown(row[column]) for column in columns) + " |")
    return "\n".join(lines)


def _format_markdown(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, (list, tuple)):
        return str(list(value))
    return str(value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a governed ExperimentRunner config.")
    parser.add_argument("config_path", nargs="?", default="configs/bootstrap_manifest.yaml")
    parser.add_argument("--output-dir", default=None, help="Compatibility override for the bootstrap smoke target.")
    args = parser.parse_args(argv)

    config_path = Path(args.config_path)
    if config_path.suffix.lower() in {".yaml", ".yml"}:
        output_dir = args.output_dir or "experiments/bootstrap"
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        smoke_output = Path(output_dir) / "bootstrap_output.txt"
        smoke_output.write_text(
            "bootstrap manifest smoke run; not a scientific experiment\n",
            encoding="utf-8",
        )
        write_manifest(
            output_dir,
            config_path=config_path,
            seeds={"root": 0},
            output_paths=[smoke_output],
            extra={"task": "E0.S3", "scientific_result": False},
        )
        return 0

    manifest = ExperimentRunner().run(config_path)
    print(json.dumps({"manifest_git_commit": manifest["git_commit"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
