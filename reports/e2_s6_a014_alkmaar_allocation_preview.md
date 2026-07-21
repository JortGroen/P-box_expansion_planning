# E2.S6 A-014 Alkmaar Allocation Preview

Status: proposed preview only; not PI-signed and not executable for integrated
EV adoption use.

## Purpose

This report applies the approved A-014 second-stage allocation rule to the
proposed Alkmaar (`GM0361`) 2035 home/public charge-point totals from PR #66.
It is a nodal allocation preview only. No EV held-out profiles were opened, no
net-load integration was run, and no congestion/event, `P(E)`, adequacy, or
manuscript result was produced.

## Inputs

- Local-count source: `configs/scenarios.yaml` / D-010 local Outlook workflow.
- Selected cluster: Alkmaar (`GM0361`), status `proposed_not_pi_signed`.
- Counts: low 7992 home / 4183 public; middle 9386 home / 5127 public; high 10343 home / 6138 public.
- Allocation rule: A-014 static `p_mw` weights over in-service SimBench `net.load` rows, deterministic largest-remainder rounding with ties by node ID.
- Grid: `simbench_semiurb`, code `1-MV-semiurb--0-sw`.

## Verification

- Node count: 115.
- Total weight: 31.64 p_mw.
- Node IDs unique: yes.
- Weights finite and nonnegative: yes.
- Rounded totals preserved: yes.

| Scenario | Home total | Public total |
|---|---:|---:|
| low | 7992 | 4183 |
| middle | 9386 | 5127 |
| high | 10343 | 6138 |

## Top High-Scenario Nodes

| Node | p_mw | Home high | Public high | Home range | Public range |
|---|---:|---:|---:|---:|---:|
| `load_001` | 0.441 | 144 | 86 | 112-144 | 58-86 |
| `load_083` | 0.441 | 144 | 86 | 112-144 | 58-86 |
| `load_002` | 0.409 | 134 | 80 | 103-134 | 54-80 |
| `load_003` | 0.409 | 134 | 80 | 103-134 | 54-80 |
| `load_006` | 0.409 | 134 | 80 | 103-134 | 54-80 |
| `load_011` | 0.409 | 134 | 80 | 103-134 | 54-80 |
| `load_012` | 0.409 | 134 | 80 | 103-134 | 54-80 |
| `load_013` | 0.409 | 134 | 80 | 103-134 | 54-80 |
| `load_014` | 0.409 | 134 | 80 | 103-134 | 54-80 |
| `load_015` | 0.409 | 134 | 80 | 103-134 | 54-80 |

## Artifact

- Metadata/allocation JSON: `data/metadata/ev_adoption/e2_s6_a014_alkmaar_allocation_preview.json`
- Metadata SHA256 (LF-normalized): `4f68ce69d1d76e67577c52efa698de2044764b7c746dd8e81cea4d7d5ef48a25`

## Guardrails

- The committed `local_grid_scenarios` block remains pending and empty.
- This preview does not authorize `adoption_scenarios()` or
  `adoption_node_allocations(config)` for the committed config.
- The proposed Alkmaar local totals still require PI acceptance before they can
  become executable local scenarios.
- Public charging behavior profiles remain separately unresolved.
