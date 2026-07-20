"""Enforce role-owned paths for agent pull requests.

The policy and exceptions are read from the PR base revision. An agent cannot
authorize its own cross-boundary edit by changing either file in the same PR.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


POLICY_PATH = "configs/agent_ownership.json"
EXCEPTIONS_PATH = "registers/OWNERSHIP_EXCEPTIONS.json"
MAINTAINER_BRANCHES = {"main"}
MAINTAINER_PREFIXES = ("codex/", "pi/")


class OwnershipCheckError(RuntimeError):
    """Raised when the ownership check cannot be evaluated safely."""


@dataclass(frozen=True)
class Violation:
    """One changed path that is not authorized for the branch role."""

    path: str
    reason: str
    owners: tuple[str, ...] = ()


def normalize_path(path: str) -> str:
    """Return a repository-relative POSIX path or reject traversal."""

    normalized = PurePosixPath(path.replace("\\", "/")).as_posix()
    if normalized == "." or normalized.startswith("../") or "/../" in normalized:
        raise OwnershipCheckError(f"invalid repository path: {path!r}")
    return normalized.removeprefix("./")


def role_for_branch(policy: Mapping[str, Any], branch: str) -> str | None:
    """Return the agent role, or ``None`` for an approved maintainer branch."""

    if branch in MAINTAINER_BRANCHES or branch.startswith(MAINTAINER_PREFIXES):
        return None
    matches = [
        role
        for prefix, role in policy["agent_branch_roles"].items()
        if branch.startswith(prefix)
    ]
    if len(matches) != 1:
        raise OwnershipCheckError(
            f"branch {branch!r} must use exactly one approved agent prefix "
            "(agent-a/, agent-b/, or agent-c/) or a maintainer prefix"
        )
    return matches[0]


def evaluate_changes(
    *,
    policy: Mapping[str, Any],
    exception_register: Mapping[str, Any],
    role: str,
    branch: str,
    changed_paths: Sequence[str],
) -> list[Violation]:
    """Return ownership violations for one agent changeset."""

    _validate_documents(policy, exception_register)
    violations: list[Violation] = []
    for raw_path in changed_paths:
        path = normalize_path(raw_path)
        if any(
            fnmatch.fnmatchcase(path, pattern)
            for pattern in policy["maintainer_only_patterns"]
        ):
            # The policy must not let an agent authorize its own future changes.
            violations.append(
                Violation(path=path, reason="reserved for a maintainer PR")
            )
            continue
        matching_rules = [
            rule
            for rule in policy["exclusive_rules"]
            if fnmatch.fnmatchcase(path, rule["pattern"])
        ]
        owners = tuple(
            sorted({owner for rule in matching_rules for owner in rule["owners"]})
        )
        if matching_rules and role in owners:
            continue
        if not matching_rules and any(
            fnmatch.fnmatchcase(path, pattern)
            for pattern in policy["shared_patterns"]
        ):
            continue
        if _has_base_exception(
            exception_register,
            branch=branch,
            role=role,
            path=path,
        ):
            continue
        if matching_rules:
            violations.append(
                Violation(path=path, reason="owned by another role", owners=owners)
            )
        else:
            violations.append(
                Violation(path=path, reason="not assigned or shared by the policy")
            )
    return violations


def check_repository(
    *,
    repo_root: Path,
    base_ref: str,
    head_ref: str,
    head_revision: str = "HEAD",
) -> tuple[str | None, list[str], list[Violation]]:
    """Load base policy, determine role, and evaluate the repository diff."""

    if head_ref in MAINTAINER_BRANCHES or head_ref.startswith(MAINTAINER_PREFIXES):
        return None, [], []
    policy = _load_json_at_ref(repo_root, base_ref, POLICY_PATH)
    exception_register = _load_json_at_ref(repo_root, base_ref, EXCEPTIONS_PATH)
    role = role_for_branch(policy, head_ref)
    if role is None:
        return None, [], []
    changed_paths = _changed_paths(repo_root, base_ref, head_revision)
    violations = evaluate_changes(
        policy=policy,
        exception_register=exception_register,
        role=role,
        branch=head_ref,
        changed_paths=changed_paths,
    )
    return role, changed_paths, violations


def _has_base_exception(
    exception_register: Mapping[str, Any],
    *,
    branch: str,
    role: str,
    path: str,
) -> bool:
    for item in exception_register["exceptions"]:
        required = ("id", "branch", "role", "task_id", "paths", "reason", "approved_by", "approved_on")
        if any(not item.get(field) for field in required):
            raise OwnershipCheckError(
                "every ownership exception must include id, branch, role, task_id, "
                "paths, reason, approved_by, and approved_on"
            )
        if item["branch"] != branch or item["role"] != role:
            continue
        if path in {normalize_path(value) for value in item["paths"]}:
            return True
    return False


def _validate_documents(
    policy: Mapping[str, Any], exception_register: Mapping[str, Any]
) -> None:
    if policy.get("policy_id") != "OWN-001" or policy.get("version") != 1:
        raise OwnershipCheckError("unsupported ownership policy identity or version")
    if not isinstance(policy.get("maintainer_only_patterns"), list):
        raise OwnershipCheckError("maintainer-only patterns must be a list")
    if exception_register.get("policy_id") != policy["policy_id"]:
        raise OwnershipCheckError("exception register does not match the ownership policy")
    if exception_register.get("version") != policy["version"]:
        raise OwnershipCheckError("exception register version does not match the policy")
    if not isinstance(exception_register.get("exceptions"), list):
        raise OwnershipCheckError("ownership exceptions must be a list")


def _load_json_at_ref(repo_root: Path, ref: str, path: str) -> dict[str, Any]:
    text = _git_text(repo_root, "show", f"{ref}:{path}")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OwnershipCheckError(f"invalid JSON at {ref}:{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise OwnershipCheckError(f"expected a JSON object at {ref}:{path}")
    return value


def _changed_paths(repo_root: Path, base_ref: str, head_revision: str) -> list[str]:
    outputs = (
        _git_bytes(
            repo_root,
            "diff",
            "--name-only",
            "--diff-filter=ACDMRTUXB",
            "-z",
            f"{base_ref}...{head_revision}",
        ),
        _git_bytes(
            repo_root,
            "diff",
            "--name-only",
            "--diff-filter=ACDMRTUXB",
            "-z",
            head_revision,
        ),
        _git_bytes(
            repo_root,
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=ACDMRTUXB",
            "-z",
            head_revision,
        ),
        _git_bytes(repo_root, "ls-files", "--others", "--exclude-standard", "-z"),
    )
    # Local preflight must see worktree edits too; CI normally contributes only
    # the first set because its checkout is clean.
    return sorted(
        {
            normalize_path(item.decode("utf-8"))
            for output in outputs
            for item in output.split(b"\0")
            if item
        }
    )


def _current_branch(repo_root: Path) -> str:
    branch = _git_text(repo_root, "branch", "--show-current").strip()
    if not branch:
        raise OwnershipCheckError("detached HEAD requires an explicit --head-ref")
    return branch


def _git_text(repo_root: Path, *args: str) -> str:
    return _git_bytes(repo_root, *args).decode("utf-8")


def _git_bytes(repo_root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise OwnershipCheckError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref")
    parser.add_argument("--head-revision", default="HEAD")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    try:
        head_ref = args.head_ref or _current_branch(repo_root)
        role, changed_paths, violations = check_repository(
            repo_root=repo_root,
            base_ref=args.base_ref,
            head_ref=head_ref,
            head_revision=args.head_revision,
        )
    except OwnershipCheckError as exc:
        print(f"OWNERSHIP CHECK ERROR: {exc}", file=sys.stderr)
        return 2

    if role is None:
        print(f"Ownership check: maintainer branch {head_ref!r}; agent path rules do not apply.")
        return 0
    if not violations:
        print(
            f"Ownership check passed for {role}: {len(changed_paths)} changed path(s) authorized."
        )
        return 0

    print(f"Ownership check failed for {role} on branch {head_ref!r}:", file=sys.stderr)
    for violation in violations:
        owner_text = f"; owner(s): {', '.join(violation.owners)}" if violation.owners else ""
        print(
            f"- {violation.path}: {violation.reason}{owner_text}",
            file=sys.stderr,
        )
    print(
        "Remove the cross-boundary edit or ask the PI to merge an exact-path "
        "exception into main before updating this branch.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
