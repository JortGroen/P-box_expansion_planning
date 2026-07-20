from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import check_agent_ownership as ownership


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def policy() -> dict[str, object]:
    return json.loads((ROOT / ownership.POLICY_PATH).read_text(encoding="utf-8"))


@pytest.fixture
def empty_exceptions() -> dict[str, object]:
    return {
        "policy_id": "OWN-001",
        "version": 1,
        "exceptions": [],
    }


def test_role_owner_can_edit_owned_source_and_test(
    policy: dict[str, object], empty_exceptions: dict[str, object]
) -> None:
    violations = ownership.evaluate_changes(
        policy=policy,
        exception_register=empty_exceptions,
        role="agent-a",
        branch="agent-a/E3.S4-crn-harness",
        changed_paths=("src/rng.py", "tests/test_rng.py"),
    )

    assert violations == []


def test_cross_boundary_source_edit_is_rejected(
    policy: dict[str, object], empty_exceptions: dict[str, object]
) -> None:
    violations = ownership.evaluate_changes(
        policy=policy,
        exception_register=empty_exceptions,
        role="agent-a",
        branch="agent-a/E3.S4-crn-harness",
        changed_paths=("src/pbox.py",),
    )

    assert violations == [
        ownership.Violation(
            path="src/pbox.py",
            reason="owned by another role",
            owners=("agent-b",),
        )
    ]


def test_shared_governance_paths_are_allowed_but_logs_remain_exclusive(
    policy: dict[str, object], empty_exceptions: dict[str, object]
) -> None:
    shared = ownership.evaluate_changes(
        policy=policy,
        exception_register=empty_exceptions,
        role="agent-b",
        branch="agent-b/E5.S3-schema",
        changed_paths=(
            "registers/STATUS.md",
            "paper/methods_decisions_and_assumptions.md",
            "reports/E5_S3_SCHEMA.md",
            "reports/AGENT_B_LOG.md",
        ),
    )
    wrong_log = ownership.evaluate_changes(
        policy=policy,
        exception_register=empty_exceptions,
        role="agent-b",
        branch="agent-b/E5.S3-schema",
        changed_paths=("reports/AGENT_A_LOG.md",),
    )

    assert shared == []
    assert wrong_log == [
        ownership.Violation(
            path="reports/AGENT_A_LOG.md",
            reason="owned by another role",
            owners=("agent-a",),
        )
    ]


def test_unassigned_repository_governance_file_is_rejected(
    policy: dict[str, object], empty_exceptions: dict[str, object]
) -> None:
    violations = ownership.evaluate_changes(
        policy=policy,
        exception_register=empty_exceptions,
        role="agent-c",
        branch="agent-c/E2.S2-library",
        changed_paths=("agent_instructions.md",),
    )

    assert violations[0].reason == "not assigned or shared by the policy"


def test_agent_c_cannot_edit_the_policy_that_authorizes_agent_c(
    policy: dict[str, object], empty_exceptions: dict[str, object]
) -> None:
    violations = ownership.evaluate_changes(
        policy=policy,
        exception_register=empty_exceptions,
        role="agent-c",
        branch="agent-c/E2.S2-home-profile-library",
        changed_paths=("configs/agent_ownership.json",),
    )

    assert violations == [
        ownership.Violation(
            path="configs/agent_ownership.json",
            reason="reserved for a maintainer PR",
        )
    ]


def test_base_exception_is_exact_to_branch_role_and_path(
    policy: dict[str, object], empty_exceptions: dict[str, object]
) -> None:
    approved = {
        **empty_exceptions,
        "exceptions": [
            {
                "id": "OWN-EX-001",
                "branch": "agent-a/E3.S4-crn-harness",
                "role": "agent-a",
                "task_id": "E3.S4",
                "paths": ["src/pbox.py"],
                "reason": "PI-approved integration",
                "approved_by": "PI",
                "approved_on": "2026-07-17",
            }
        ],
    }

    allowed = ownership.evaluate_changes(
        policy=policy,
        exception_register=approved,
        role="agent-a",
        branch="agent-a/E3.S4-crn-harness",
        changed_paths=("src/pbox.py",),
    )
    wrong_branch = ownership.evaluate_changes(
        policy=policy,
        exception_register=approved,
        role="agent-a",
        branch="agent-a/E3.S5-other",
        changed_paths=("src/pbox.py",),
    )

    assert allowed == []
    assert len(wrong_branch) == 1


def test_repository_check_reads_policy_and_exceptions_from_base(
    monkeypatch: pytest.MonkeyPatch,
    policy: dict[str, object],
    empty_exceptions: dict[str, object],
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, str]] = []

    def fake_load(_root: Path, ref: str, path: str) -> dict[str, object]:
        calls.append((ref, path))
        return policy if path == ownership.POLICY_PATH else empty_exceptions

    monkeypatch.setattr(ownership, "_load_json_at_ref", fake_load)
    monkeypatch.setattr(ownership, "_changed_paths", lambda *_args: ["src/rng.py"])

    role, changed, violations = ownership.check_repository(
        repo_root=tmp_path,
        base_ref="base-sha",
        head_ref="agent-a/E3.S4-crn-harness",
    )

    assert calls == [
        ("base-sha", ownership.POLICY_PATH),
        ("base-sha", ownership.EXCEPTIONS_PATH),
    ]
    assert role == "agent-a"
    assert changed == ["src/rng.py"]
    assert violations == []


def test_changed_paths_include_branch_worktree_index_and_untracked_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    outputs = iter(
        (
            b"src/rng.py\0deleted.py\0",
            b"src/pbox.py\0",
            b"tests/test_rng.py\0",
            b"new_file.py\0src/rng.py\0",
        )
    )
    monkeypatch.setattr(ownership, "_git_bytes", lambda *_args: next(outputs))

    changed = ownership._changed_paths(tmp_path, "origin/main", "HEAD")

    assert changed == [
        "deleted.py",
        "new_file.py",
        "src/pbox.py",
        "src/rng.py",
        "tests/test_rng.py",
    ]


def test_maintainer_branch_bypasses_agent_policy_before_base_policy_load(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail_load(*_args: object) -> dict[str, object]:
        raise AssertionError("maintainer branch must not need a base policy")

    monkeypatch.setattr(ownership, "_load_json_at_ref", fail_load)

    role, changed, violations = ownership.check_repository(
        repo_root=tmp_path,
        base_ref="base-without-policy",
        head_ref="codex/ownership-enforcement",
    )

    assert role is None
    assert changed == []
    assert violations == []
