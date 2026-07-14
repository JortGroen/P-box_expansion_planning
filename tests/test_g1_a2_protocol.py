from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_unrelated_radius_arxiv_citation_is_absent() -> None:
    paths = (
        "project_plan_v3_when_can_grid_reinforcement_wait.md",
        "Literature_review_combined.md",
        "reports/G1_A2_GRID_ERROR_AND_CAPACITY_PROTOCOL.md",
    )

    for path in paths:
        assert "2402.15728" not in _read(path)


def test_a013_numerical_values_remain_proposed() -> None:
    assumptions = _read("registers/ASSUMPTIONS.md")
    a013_row = next(line for line in assumptions.splitlines() if line.startswith("| A-013 |"))

    assert "5%" in a013_row
    assert "author-specified scenarios" in a013_row
    assert "| proposed | -- |" in a013_row


def test_g1_a2_freezes_mixed_error_composition() -> None:
    decisions = _read("registers/DECISIONS.md")
    protocol = _read("reports/G1_A2_GRID_ERROR_AND_CAPACITY_PROTOCOL.md")

    for text in (decisions, protocol):
        assert "(1 - epsilon_grid) * L_PP_lower" in text
        assert "(1 + epsilon_grid) * L_PP_upper" in text
        assert "unwidened `P_net`" in text


def test_future_layer_screen_governs_domain_and_capacity_choice() -> None:
    plan = _read("actionable_project_plan_agentic.md")
    status = _read("registers/STATUS.md")

    assert "E3.S2b Future-layer capacity and domain screen" in plan
    assert "raw import/export MVA" in plan
    assert "E3.S2b Future-layer capacity and domain screen" in status
    assert "E2.S2-E2.S6, E3.S1-E3.S2" in status
