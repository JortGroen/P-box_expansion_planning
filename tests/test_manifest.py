from __future__ import annotations

import json
from pathlib import Path

from src.manifest import build_manifest, sha256_file, write_manifest


def _case_dir(name: str) -> Path:
    root = Path("tests") / "_artifacts" / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_sha256_file_is_stable() -> None:
    case_dir = _case_dir("sha256")
    path = case_dir / "value.txt"
    path.write_text("same bytes\n", encoding="utf-8")

    assert sha256_file(path) == sha256_file(path)


def test_manifest_records_config_and_output_checksums() -> None:
    case_dir = _case_dir("checksums")
    config = case_dir / "config.yaml"
    output = case_dir / "result.txt"
    config.write_text("seed: 7\n", encoding="utf-8")
    output.write_text("result\n", encoding="utf-8")

    manifest = build_manifest(
        config_path=config,
        seeds={"root": 7},
        output_paths=[output],
        packages=[],
    )

    assert manifest["config_hash"] == sha256_file(config)
    assert manifest["seeds"] == {"root": 7}
    assert manifest["output_checksums"] == {output.as_posix(): sha256_file(output)}


def test_identical_manifest_inputs_produce_identical_manifest_json() -> None:
    case_dir = _case_dir("stable_json")
    config = case_dir / "config.yaml"
    output = case_dir / "result.txt"
    config.write_text("run_id: stable\n", encoding="utf-8")
    output.write_text("42\n", encoding="utf-8")

    first = write_manifest(
        case_dir / "first",
        config_path=config,
        seeds={"root": 1},
        output_paths=[output],
        packages=[],
    )
    second = write_manifest(
        case_dir / "second",
        config_path=config,
        seeds={"root": 1},
        output_paths=[output],
        packages=[],
    )

    assert json.loads(first.read_text(encoding="utf-8")) == json.loads(
        second.read_text(encoding="utf-8")
    )
