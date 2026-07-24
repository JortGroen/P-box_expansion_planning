# E2.S2 EV IC-1 Candidate Component Output Manifest

Status: candidate-only EV component-output materialization for Agent A IC-1 preflight consumption. The generated NPZ outputs are ignored local files under `data/processed/elaad_profiles/component_outputs/`; this PR commits only the manifest and report.

## Boundary

This materialization reverified candidate processed-profile SHA-256 hashes before loading arrays, summed only EV candidate selections to node-level EV active-power trajectories, and wrote one EV-only output file per declared 2035 branch. It did not open held-out or quarantined batches, certify `M = 1000` or `M = 1200`, select the final low/middle/high branch, run net-load/event/`P(E)`, run capacity screens, or produce manuscript numbers.

## Outputs

| Scenario | Selected rows | Home | Public | Duplicate selected rows | Ignored output path | SHA-256 |
|---|---:|---:|---:|---:|---|---|
| high | 16481 | 10343 | 6138 | 16436 | `data/processed/elaad_profiles/component_outputs/ev_ic1_candidate_component_output_high.npz` | `dd95f30d74da00b6fb87c2ced8f402b4d612c59a28e7d1d33e9e82fcd7a805d5` |
| low | 12175 | 7992 | 4183 | 12041 | `data/processed/elaad_profiles/component_outputs/ev_ic1_candidate_component_output_low.npz` | `a896794ddd9f004fe945c62a5b84b2b1b6e9381cbecd80b17ca7c749de68ce65` |
| middle | 14513 | 9386 | 5127 | 14435 | `data/processed/elaad_profiles/component_outputs/ev_ic1_candidate_component_output_middle.npz` | `38081c7f849bb679a19560d1a7f7fd6d8428e35ef6cad2087e4d82a46c1e568d` |

## Provenance

The manifest preserves EV-005B replacement provenance, EV-CAL-001 ordinal source-to-2035 calendar mapping, RNG-001 stream identities from the selection manifests, EV-007A/A-014 node allocations, EV-008A public capacity strata, source member IDs, batch seeds, returned indices, duplicate/multiplicity records, and candidate processed-file checksums.

Agent A should load the ignored output files only by the committed manifest checksums and keep this EV-only artifact separate from net-load assembly and event analysis.
