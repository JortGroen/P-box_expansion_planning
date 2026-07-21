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


def test_status_and_legacy_logs_are_maintainer_dashboard_files(
    policy: dict[str, object], empty_exceptions: dict[str, object]
) -> None:
    allowed = ownership.evaluate_changes(
        policy=policy,
        exception_register=empty_exceptions,
        role="agent-b",
        branch="agent-b/E5.S3-schema",
        changed_paths=(
            "paper/methods_decisions_and_assumptions.md",
            "reports/E5_S3_SCHEMA.md",
            "reports/agent_logs/agent-b/E5.S3-schema.md",
        ),
    )
    reserved = ownership.evaluate_changes(
        policy=policy,
        exception_register=empty_exceptions,
        role="agent-b",
        branch="agent-b/E5.S3-schema",
        changed_paths=("registers/STATUS.md", "reports/AGENT_B_LOG.md"),
    )

    assert allowed == []
    assert reserved == [
        ownership.Violation(
            path="registers/STATUS.md",
            reason="reserved for a maintainer PR",
        ),
        ownership.Violation(
            path="reports/AGENT_B_LOG.md",
            reason="reserved for a maintainer PR",
        ),
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
        additional_paths=("tests/test_rng.py",),
    )

    assert calls == [
        ("base-sha", ownership.POLICY_PATH),
        ("base-sha", ownership.EXCEPTIONS_PATH),
    ]
    assert role == "agent-a"
    assert changed == ["src/rng.py", "tests/test_rng.py"]
    assert violations == []


def test_planned_cross_boundary_path_fails_before_any_edit(
    monkeypatch: pytest.MonkeyPatch,
    policy: dict[str, object],
    empty_exceptions: dict[str, object],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        ownership,
        "_load_json_at_ref",
        lambda _root, _ref, path: (
            policy if path == ownership.POLICY_PATH else empty_exceptions
        ),
    )
    monkeypatch.setattr(ownership, "_changed_paths", lambda *_args: [])

    _role, changed, violations = ownership.check_repository(
        repo_root=tmp_path,
        base_ref="base-sha",
        head_ref="agent-a/E3.S4-crn-harness",
        additional_paths=("src/pbox.py",),
    )

    assert changed == ["src/pbox.py"]
    assert violations == [
        ownership.Violation(
            path="src/pbox.py",
            reason="owned by another role",
            owners=("agent-b",),
        )
    ]


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


def test_initial_policy_branch_bootstraps_only_before_base_policy_exists(
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


def test_nonbootstrap_maintainer_prefix_is_loaded_from_base_policy(
    monkeypatch: pytest.MonkeyPatch,
    policy: dict[str, object],
    empty_exceptions: dict[str, object],
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def fake_load(_root: Path, _ref: str, path: str) -> dict[str, object]:
        calls.append(path)
        return policy if path == ownership.POLICY_PATH else empty_exceptions

    def fail_changed_paths(*_args: object) -> list[str]:
        raise AssertionError("maintainer paths must not be evaluated")

    monkeypatch.setattr(ownership, "_load_json_at_ref", fake_load)
    monkeypatch.setattr(ownership, "_changed_paths", fail_changed_paths)

    role, changed, violations = ownership.check_repository(
        repo_root=tmp_path,
        base_ref="base-with-policy",
        head_ref="codex/future-maintenance",
    )

    assert calls == [ownership.POLICY_PATH, ownership.EXCEPTIONS_PATH]
    assert role is None
    assert changed == []
    assert violations == []


def test_maintainer_prefixes_have_no_hidden_code_default(
    policy: dict[str, object]
) -> None:
    policy_with_different_prefix = {
        **policy,
        "maintainer_branch_prefixes": ["maintenance/"],
    }

    assert (
        ownership.role_for_branch(
            policy_with_different_prefix, "maintenance/governance"
        )
        is None
    )
    with pytest.raises(ownership.OwnershipCheckError):
        ownership.role_for_branch(
            policy_with_different_prefix, "codex/not-policy-authorized"
        )


def test_pr_template_matches_the_mandated_checklist_verbatim() -> None:
    instructions = (ROOT / "agent_instructions.md").read_text(encoding="utf-8")
    template = (ROOT / ".github/pull_request_template.md").read_text(
        encoding="utf-8"
    )
    checklist_section = instructions.split("- **PR checklist:**", maxsplit=1)[1]
    mandated = [
        line.strip()
        for line in checklist_section.splitlines()
        if line.startswith("  - [ ] ")
    ]
    rendered = [
        line
        for line in template.splitlines()
        if line.startswith("- [ ] ")
    ]

    assert mandated
    assert rendered == mandated
