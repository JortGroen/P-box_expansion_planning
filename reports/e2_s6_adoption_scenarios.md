# E2.S6 Adoption Scenarios

Status: proposed; blocks integrated scientific use until PI signs D-009/D-010 and A-014.

## Source Evidence

Sourced values:

- D-009, ElaadNL Outlook Mobiliteit 2026 scenariotool, accessed 2026-07-20.
  - Home endpoint: `https://outlook.elaad.nl/api/proxy_v2?endpoint=/charging_infrastructure?area_type=country&scenario={scenario}&location=home`
  - Public endpoint: `https://outlook.elaad.nl/api/proxy_v2?endpoint=/charging_infrastructure?area_type=country&scenario={scenario}&location=public`
  - Dashboard provenance: `https://outlook.elaad.nl/` states the scenariotool provides projections to CBS-neighbourhood level, links the full report/model background, flags the outlook as assumption-based/indicative with 24-month validity, and licenses the site as CC BY-NC-ND 4.0.
  - API fields used: `type=charging_infrastructure`, `year={2030,2033,2035}`, `month=12`, `scenario={low,middle,high}`, `location={home,public}`.
- D-010, Netbeheer Nederland II3050 edition 2, 2023-10-12 publication page `https://www.netbeheernederland.nl/publicatie/ii3050-eindrapport`.
  - Used for 2030-2050 infrastructure-scenario framing only.
  - No numeric charge-point counts are copied from II3050 in this E2.S6 config.

Derived values:

- `configs/scenarios.yaml` rounds the D-009 floating API `number` fields to integer physical charge-point counts.
- Public charge-point counts are recorded for adoption provenance, but public profile behavior remains blocked by the Set B decision in `reports/elaad_profile_generation_spec.md`.

Assumption:

- A-014 proposes allocating national charge-point counts over the SimBench primary grid's 115 in-service `net.load` rows in proportion to static `p_mw`, using deterministic largest-remainder rounding. This gives EV-005 the required `K_r` ranges but is not yet signed as a local feeder-scaling rule.

## National Counts

| Year | Scenario | K_home | K_public |
|---:|---|---:|---:|
| 2030 | low | 1,634,178 | 314,336 |
| 2030 | middle | 1,767,963 | 374,749 |
| 2030 | high | 1,885,471 | 433,760 |
| 2033 | low | 1,870,267 | 459,410 |
| 2033 | middle | 2,014,740 | 562,418 |
| 2033 | high | 2,135,098 | 649,640 |
| 2035 | low | 1,984,323 | 570,314 |
| 2035 | middle | 2,138,672 | 695,942 |
| 2035 | high | 2,252,661 | 808,049 |

Total ranges by year:

| Year | K_home range | K_public range |
|---:|---:|---:|
| 2030 | 1,634,178-1,885,471 | 314,336-433,760 |
| 2033 | 1,870,267-2,135,098 | 459,410-649,640 |
| 2035 | 1,984,323-2,252,661 | 570,314-808,049 |

## Proposed Nodal Allocation

The proposed A-014 allocation uses 115 in-service SimBench load nodes with total static load weight 31.64 MW. Per-node `K_r` ranges below are grouped by identical `p_mw`; every node in a row receives the same range under largest-remainder rounding.

| p_mw | Nodes | Home K_r min-max | Public K_r min-max |
|---:|---:|---:|---:|
| 0.080 | 6 | 4,132-5,696 | 795-2,043 |
| 0.085 | 1 | 4,390-6,051 | 845-2,171 |
| 0.202 | 25 | 10,433-14,382 | 2,007-5,159 |
| 0.210 | 1 | 10,846-14,951 | 2,086-5,363 |
| 0.235 | 1 | 12,138-16,731 | 2,335-6,002 |
| 0.243 | 36 | 12,551-17,301 | 2,414-6,206 |
| 0.245 | 1 | 12,654-17,443 | 2,434-6,257 |
| 0.331 | 18 | 17,096-23,566 | 3,289-8,453 |
| 0.340 | 1 | 17,561-24,207 | 3,378-8,683 |
| 0.409 | 23 | 21,125-29,119 | 4,063-10,446 |
| 0.441 | 2 | 22,777-31,397 | 4,381-11,263 |

## Governance Notes

- EV-004 remains intact: the residential behavior source is the fixed ElaadNL 2030 home `cp` library, and the planning-year variation here changes only physical charge-point counts.
- EV-005 replacement governance is still open. These proposed `K_home`/`K_r` values are far larger than the candidate source library size `M=1000`, so downstream sampling cannot claim unique source profiles per physical charge point.
- The within-realization replacement rule remains unresolved until PI answers Q-7 and E3.S2a freezes its adequacy criterion.
- No held-out EV batches were opened, used, summarized, or analyzed for this task.
