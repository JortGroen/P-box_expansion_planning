from __future__ import annotations

from collections import Counter
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
REGISTER_PATHS = (
    ROOT / "registers" / "DECISIONS.md",
    ROOT / "registers" / "ASSUMPTIONS.md",
    ROOT / "registers" / "DATA_REGISTER.md",
)
METHODS_PATH = ROOT / "paper" / "methods_decisions_and_assumptions.md"
ROW_ID_RE = re.compile(r"^\|\s*([A-Z][A-Z0-9-]*)\s*\|", re.MULTILINE)
METHOD_ID_RE = re.compile(r"<!--\s*methods-id:\s*([A-Z][A-Z0-9-]*)\s*-->")


def _registered_ids() -> set[str]:
    ids: set[str] = set()
    for path in REGISTER_PATHS:
        ids.update(ROW_ID_RE.findall(path.read_text(encoding="utf-8")))
    ids.discard("ID")
    return ids


def test_every_registered_choice_has_one_methods_block() -> None:
    methods_text = METHODS_PATH.read_text(encoding="utf-8")
    methods_ids = METHOD_ID_RE.findall(methods_text)
    counts = Counter(methods_ids)

    assert {item for item, count in counts.items() if count > 1} == set()
    assert set(methods_ids) == _registered_ids()


def test_every_methods_block_declares_its_status() -> None:
    methods_text = METHODS_PATH.read_text(encoding="utf-8")
    matches = list(METHOD_ID_RE.finditer(methods_text))

    for index, match in enumerate(matches):
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(methods_text)
        block = methods_text[match.end() : block_end]
        assert "**Status:" in block, f"methods block {match.group(1)} lacks a status label"
        assert len(block.split()) >= 20, f"methods block {match.group(1)} is only a placeholder stub"


def _assumption_register_ids() -> set[str]:
    text = (ROOT / "registers" / "ASSUMPTIONS.md").read_text(encoding="utf-8")
    return {item for item in ROW_ID_RE.findall(text) if item.startswith("A-")}


def test_formal_assumption_inventory_lists_every_assumption_row() -> None:
    methods_text = METHODS_PATH.read_text(encoding="utf-8")
    start = "<!-- assumption-inventory-start -->"
    end = "<!-- assumption-inventory-end -->"
    assert start in methods_text
    assert end in methods_text
    inventory = methods_text.split(start, 1)[1].split(end, 1)[0]

    listed = set(re.findall(r"`(A-\d{3})`", inventory))
    assert listed == _assumption_register_ids()


def test_methods_inventory_flags_inferred_pbl_hp_indicator_mapping() -> None:
    methods_text = METHODS_PATH.read_text(encoding="utf-8")
    assert "H23_Vraag_RV_w" in methods_text
    assert "H24_Vraag_TW_w" in methods_text
    assert "currently inferred" in methods_text
    assert "explicit PBL evidence" in methods_text
