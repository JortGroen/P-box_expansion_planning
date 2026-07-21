# E2.S6 Local EV Adoption Counts

Status: proposed workflow only; not PI-signed and not executable for integrated
EV adoption use.

## Purpose

This report turns Q-7 Option A into an auditable proposed workflow: select a
representative CBS-area cluster before inspecting integrated congestion
results, then derive local 2035 home and public charge-point totals from
ElaadNL Outlook local forecast outputs. No integrated event, congestion,
profile-library adequacy, or EV held-out analysis was run.

## Proposed Cluster

Proposed EV-007 cluster:

- Area type: `municipalities`
- Area identifier: `GM0361`
- Name: Alkmaar
- Province: Noord-Holland
- Network operator: not returned by the local API response
- NAL region: not returned by the local API response
- Status: proposed, not PI-signed

Selection basis:

- Uses a local Outlook municipality endpoint instead of national totals.
- Selects the PI's first-preference municipality before any integrated
  congestion or event-based results were produced.
- The current Outlook API returned complete 2035 low/middle/high home and
  public charge-point forecasts for Alkmaar.
- The previously proposed Lingewaard (`GM1705`) cluster is superseded in this
  PR revision; it was not PI-signed or used for executable adoption scenarios.

Fallback checked:

- Delft (`GM0503`) was also checked because it was the PI's fallback
  preference. The current Outlook API returned complete 2035 low/middle/high
  home and public values for Delft, but Alkmaar remains selected by first
  preference.

Limitation:

- The live Outlook neighbourhood endpoint
  `/filters/municipalities/neighborhoods/GM0361` returned HTTP 500 at
  `2026-07-21T09:32:50.1236021Z`. Individual CBS-neighbourhood rows were
  therefore not accessible through this route during the session. The proposed
  cluster is municipality-level pending PI review.

## Source Provenance

Primary source:

- ElaadNL Outlook Mobiliteit Scenariotool/API, `https://outlook.elaad.nl/scenariotool`
- Scenariotool version: `v1.0.0`
- Site update shown by the app: `Laatst geüpdatet: 9 juni 2026`
- API base used: `https://api-outlook-v2-prd.thankfulrock-fcd5ae60.westeurope.azurecontainerapps.io`
- Legacy proxy note: `https://outlook.elaad.nl/api/proxy_v2` returned HTTP 404
  at `2026-07-21T09:31Z`; the live app exposed the API base above.
- License shown on the Outlook site: CC BY-NC-ND 4.0
- Raw data policy: no raw API responses are committed; checksums identify the
  retrieved JSON payloads.

Metadata:

- Path: `data/metadata/ev_adoption/e2_s6_local_adoption_counts_metadata.json`
- SHA256: `fa4af429fd3da6f017c873801aa08064e2c2220d60ea896c1a4a8d5fd5201daa`

## Proposed 2035 Counts

Rounding rule: round the floating API field `number` to the nearest integer
charge-point count for proposed physical totals. These values are review-only
and do not populate `local_grid_scenarios`.

| Scenario | Location | API number | Proposed rounded count | Retrieved UTC | Response sha256 |
|---|---|---:|---:|---|---|
| low | home | 7991.80830348258 | 7992 | 2026-07-21T09:33:34.9663859Z | `2b91de9e67c0ccddffa5c11293571391886b7a59414ae4549f5a0aad868e9bd4` |
| low | public | 4182.6860541073265 | 4183 | 2026-07-21T09:33:36.3256749Z | `b97e7883c719e726b349ae16f8438d16308762125684d6b871772fac1dcef169` |
| middle | home | 9386.406999563205 | 9386 | 2026-07-21T09:33:36.4313293Z | `7f5e22504bdf98a36b407c2e861d4583dec040ead7d93e29958b625f3b48de46` |
| middle | public | 5127.01005454311 | 5127 | 2026-07-21T09:33:36.5641931Z | `108956322a7a9ef6872aa02bcd6605bbc2aacfc0840c1a4d07974c44364b9243` |
| high | home | 10343.304477753807 | 10343 | 2026-07-21T09:33:36.7211960Z | `3f16acac00eb389bca0105ed1b7ecc899c4cf5a0983d76450ab4bcf8dd519224` |
| high | public | 6137.847745988891 | 6138 | 2026-07-21T09:33:36.9886557Z | `b6c2d52a8baf9f41719fbe4449554a12f06fa292d5ab716781aac5ee15ad0b07` |

Query pattern:

`/charging_infrastructure?area_type=municipalities&area_identifier=GM0361&scenario={low|middle|high}&location={home|public}`

## Delft Fallback Check

Delft (`GM0503`) is also usable at the municipality level if the PI later
prefers it over Alkmaar. The retrieved 2035 rounded counts were home/public:
low `2547`/`2223`, middle `3130`/`2737`, and high `3637`/`3235`. These values
are recorded only in metadata as a fallback availability check and are not the
selected local-count proposal.

## Allocation Basis

A-014 is approved only as a second-stage allocation rule after EV-007 supplies
accepted local totals. If the proposed Alkmaar totals are accepted, the local
totals may then be allocated across the 115 in-service SimBench `net.load` rows
using static `p_mw` weights and deterministic largest-remainder rounding. This
branch does not produce a per-node `K_r` table because the Alkmaar totals are
not PI-signed.

## Guardrails

- `configs/scenarios.yaml` stores proposed counts under `local_count_workflow`,
  not under executable `local_grid_scenarios`.
- `src.ev_model.adoption_scenarios()` still rejects the committed config while
  `local_grid_scenarios.status` is `pending_local_cluster_selection`.
- `src.ev_model.proposed_local_charge_point_counts()` exposes the proposed
  values for audit only.
- Country-level D-010 Outlook queries are rejected if supplied as proposed
  local-count provenance.

## Remaining Decisions

- PI must decide whether Alkmaar (`GM0361`) is an acceptable representative
  local cluster for the SimBench case.
- PI must decide whether municipality-level clustering is acceptable while the
  neighbourhood-list endpoint returns HTTP 500, or whether Agent C should wait
  for/recover neighbourhood-level data.
- The proposed Alkmaar counts remain non-executable until PI acceptance.
- Public charging profile behavior remains separately blocked by the Elaad
  profile-generation specification.
