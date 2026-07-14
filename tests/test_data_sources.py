from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from data.get_elaad_profiles import build_probe_request
from data.sources import source_specs, write_metadata


def _case_dir(name: str) -> Path:
    root = Path("tests") / "_artifacts" / "data_sources" / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_e2_s1_sources_have_existing_retrieval_scripts() -> None:
    expected_ids = {"D-001", "D-002", "D-003", "D-004", "D-008"}
    specs = source_specs()

    assert {spec.data_id for spec in specs} == expected_ids
    for spec in specs:
        script = Path(spec.retrieval_script)
        assert script.is_file(), spec.retrieval_script
        assert script.as_posix().startswith("data/get_")


def test_metadata_writer_records_no_download_by_default() -> None:
    metadata_dir = _case_dir("metadata")
    path = write_metadata("D-003", metadata_dir, extra={"test": True})

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["data_id"] == "D-003"
    assert payload["download_performed"] is False
    assert payload["status"] == "metadata-only; pending license/API verification and PI sign-off before data use"
    assert payload["extra"] == {"test": True}


def test_data_register_references_e2_s1_retrieval_scripts() -> None:
    register = Path("registers/DATA_REGISTER.md").read_text(encoding="utf-8")

    for spec in source_specs():
        assert spec.data_id in register
        assert f"`{spec.retrieval_script}`" in register


def test_data_register_has_no_e2_s1_placeholders() -> None:
    register = Path("registers/DATA_REGISTER.md").read_text(encoding="utf-8")

    for placeholder in ("TBD", "to check", "URL to verify", "DOI/URL to verify"):
        assert placeholder not in register


def test_elaad_source_uses_profile_generator_route() -> None:
    d002 = next(spec for spec in source_specs() if spec.data_id == "D-002")

    assert "Laadprofielengenerator" in d002.source
    assert d002.retrieval_script == "data/get_elaad_profiles.py"
    assert "elaad_profile_generation_spec.md" in d002.doi_url


def test_elaad_one_profile_probe_request_is_narrow() -> None:
    request = build_probe_request()

    assert request["simulated_year"] == 2033
    assert request["n_profiles"] == 1
    assert request["profile_type"] == "ev"
    assert request["location_type"] == "home"
    assert request["vehicle_types"] == "car"
    assert request["step_size_s"] == 900
    assert request["seed"] == 133001


def test_data_entrypoints_run_directly() -> None:
    scripts = {spec.retrieval_script for spec in source_specs()}
    scripts.add("data/get_elaadnl.py")

    for script in sorted(scripts):
        metadata_dir = _case_dir("entrypoints") / Path(script).stem
        result = subprocess.run(
            [sys.executable, script, "--metadata-dir", str(metadata_dir)],
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert Path(result.stdout.strip()).is_file()