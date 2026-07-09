from __future__ import annotations

import json
from pathlib import Path

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
    assert payload["status"] == "metadata-only; pending license and URL verification"
    assert payload["extra"] == {"test": True}


def test_data_register_references_e2_s1_retrieval_scripts() -> None:
    register = Path("registers/DATA_REGISTER.md").read_text(encoding="utf-8")

    for spec in source_specs():
        assert spec.data_id in register
        assert f"`{spec.retrieval_script}`" in register
