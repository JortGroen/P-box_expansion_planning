# E3.S2a EV Component-Output Recovery Preflight

## Purpose

This packet makes the candidate-only EV component-output handoff recoverable in a clean IC-1 consuming worktree without relying on hidden local state. It extends `data/get_ev_component_outputs.py` so a reviewer or future Agent A preflight can either verify the ignored EV component-output NPZ files, or rebuild them from manifest-declared candidate processed-profile NPZs restored from an explicit local artifact root.

## Source Availability Check

The clean EV task worktree initially lacked all 22 candidate processed-profile NPZ files and the three ignored EV component-output NPZ files. A manifest-directed check, using only the expected paths from `data/metadata/ev_adoption/e2_s2_ev_candidate_profile_checksum_preflight.json`, found all 22 candidate processed-profile NPZs in the main Agent C worktree local artifact store. No recursive data scan, ElaadNL API call, held-out access, quarantined access, or integrated analysis was performed.

## Recovery Command

The successful local recovery/rebuild command was:

```powershell
.\.venv\Scripts\python.exe data\get_ev_component_outputs.py rebuild --candidate-source-root <verified-local-artifact-root> --checkpoint-path data\metadata\ev_adoption\e3_s2a_ev_component_output_recovery_preflight.json --timestamp-utc 2026-07-24T15:15:00Z
```

The command hashes each candidate processed-profile source file before copying, hashes existing target files before skipping them on resume, fails closed on missing or mismatched files, writes `data/metadata/ev_adoption/e3_s2a_ev_component_output_recovery_preflight.json` as a durable checkpoint, and then rebuilds the three candidate-only component outputs.

## Verification Result

The rebuild restored 22 candidate processed-profile NPZs and verified the three ignored component-output NPZs against the committed manifest:

| Scenario | Output path | SHA-256 |
|---|---|---|
| high | `data/processed/elaad_profiles/component_outputs/ev_ic1_candidate_component_output_high.npz` | `dd95f30d74da00b6fb87c2ced8f402b4d612c59a28e7d1d33e9e82fcd7a805d5` |
| low | `data/processed/elaad_profiles/component_outputs/ev_ic1_candidate_component_output_low.npz` | `a896794ddd9f004fe945c62a5b84b2b1b6e9381cbecd80b17ca7c749de68ce65` |
| middle | `data/processed/elaad_profiles/component_outputs/ev_ic1_candidate_component_output_middle.npz` | `38081c7f849bb679a19560d1a7f7fd6d8428e35ef6cad2087e4d82a46c1e568d` |

The generated NPZ files remain ignored under `data/processed/`; only code, tests, metadata, and this report are intended for commit.

## Non-Claims

This does not open held-out or quarantined EV batches, does not certify `M = 1000` or `M = 1200`, does not choose the final low/middle/high branch, and does not run net-load aggregation, event detection, `P(E)`, capacity screens, or manuscript-result analysis.
