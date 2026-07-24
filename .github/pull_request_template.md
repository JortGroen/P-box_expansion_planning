## Summary

- **Why this PR exists:** <one or two sentences of project context, written for the PI/reviewer>
- **What changes for the project:** <the practical/scientific outcome, not a file list>
- **What this does not decide or claim:** <gates, values, data-use, or result claims still out of scope>
- **Reviewer focus:** <the 1-3 things the PI/reviewer should judge before merge>

## Changes

-

## Validation

- `.\scripts\task.ps1 ownership`:
- `.\scripts\task.ps1 test-fast`:
- `.\scripts\task.ps1 test` or manual Full Validation workflow, if applicable:

## Evidence

-

## Risks and decisions

- None.

## Suggested STATUS update

- `Story | Owner | Status | Tasks | Blocked-by | PR`

## Checklist

- [ ] `.\scripts\task.ps1 ownership` green locally (or base-branch PI exception linked)
- [ ] `.\scripts\task.ps1 test-fast` green locally
- [ ] Full validation run or explicitly not applicable for this PR
- [ ] Invariant suite green (if math touched)
- [ ] Manifest(s) attached for every produced result
- [ ] Repeated/API/download/profile/checksum/sweep work is scripted, tested, and resumable before scale-up
- [ ] Registers updated (`ASSUMPTIONS`/`DATA_REGISTER` rows `proposed` where needed)
- [ ] Methods paragraph registry updated for every changed decision, assumption, or data/protocol choice
- [ ] No interface-contract or schema change (or: gate approval linked)
- [ ] Task report/log updated and suggested STATUS update included in PR body
