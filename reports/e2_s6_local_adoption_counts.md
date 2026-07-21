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
- Area identifier: `GM1705`
- Name: Lingewaard
- Province: Gelderland
- Network operator: Liander
- NAL region: Oost
- Status: proposed, not PI-signed

Selection basis:

- Uses a local Outlook area endpoint instead of national totals.
- Uses a non-G4 Liander/Oost municipality cluster as an exogenous local-area
  candidate for the semi-urban SimBench case.
- Lingewaard has prior public-policy traceability to ElaadNL neighbourhood
  forecasts, but that traceability is contextual only; it is not a PI sign-off.
- Selection was made before any integrated congestion or event-based results
  were produced in this session.

Limitation:

- The live Outlook proxy endpoint
  `/filters/municipalities/neighborhoods/GM1705` returned HTTP 500 at
  `2026-07-21T08:34:16.0537604Z`. Individual CBS-neighbourhood rows were
  therefore not accessible through this route during the session. The proposed
  cluster is municipality-level pending PI review.

## Source Provenance

Primary source:

- ElaadNL Outlook Mobiliteit Scenariotool/API, `https://outlook.elaad.nl/scenariotool`
- Scenariotool version: `v1.0.0`
- Site update shown by the app: `Laatst geüpdatet: 9 juni 2026`
- API proxy used: `https://outlook.elaad.nl/api/proxy_v2`
- License shown on the Outlook site: CC BY-NC-ND 4.0
- Raw data policy: no raw API responses are committed; checksums identify the
  retrieved JSON payloads.

Metadata:

- Path: `data/metadata/ev_adoption/e2_s6_local_adoption_counts_metadata.json`
- SHA256: `3f29419f89d4fa643108f594d89c07a9cda3654dfae6a71900aa0236b2aeebad`

## Proposed 2035 Counts

Rounding rule: round the floating API field `number` to the nearest integer
charge-point count for proposed physical totals. These values are review-only
and do not populate `local_grid_scenarios`.

| Scenario | Location | API number | Proposed rounded count | Retrieved UTC | Response sha256 |
|---|---|---:|---:|---|---|
| low | home | 8042.550122943402 | 8043 | 2026-07-21T08:34:14.5328317Z | `850cdbd618ddf9b12b8f48166c26c215ee8c0a8e4299bcf7ebda1f5ea403649d` |
| low | public | 1372.8223658557333 | 1373 | 2026-07-21T08:34:15.3182779Z | `2ba1848017676748c4bc28f082b6d0659e3dbbbefda4ad7cb50fd86400d23fd2` |
| middle | home | 8417.687927695493 | 8418 | 2026-07-21T08:34:15.5335594Z | `a74e8d1d2e3f774cc3b3da99afbd4b2676ac4d0c49e89746a70b5317de882b74` |
| middle | public | 1624.801030181807 | 1625 | 2026-07-21T08:34:15.6213858Z | `0d3bc6c9eb5050e51e21700e8d77943e4fe6f78516ac560af84d68e231bda107` |
| high | home | 8607.135281697223 | 8607 | 2026-07-21T08:34:15.8236116Z | `4f7e1107035dd153f658214d06fc49e682d514eb1dffdf3627a025d4a66c4364` |
| high | public | 1828.6489056790774 | 1829 | 2026-07-21T08:34:15.9525317Z | `58112ea08ec4c6085e9f25496e7e929f346dea5f5bf0e2839ef4431cb950a61f` |

Query pattern:

`/charging_infrastructure?area_type=municipalities&area_identifier=GM1705&scenario={low|middle|high}&location={home|public}`

## Allocation Basis

A-014 remains proposed as a possible second-stage allocation only. If EV-007
and Q-7 are signed, the local totals may then be allocated across the 115
in-service SimBench `net.load` rows using static `p_mw` weights and
deterministic largest-remainder rounding. This branch does not produce a
per-node `K_r` table because local totals and A-014 are not approved.

## Guardrails

- `configs/scenarios.yaml` stores proposed counts under `local_count_workflow`,
  not under executable `local_grid_scenarios`.
- `src.ev_model.adoption_scenarios()` still rejects the committed config while
  `local_grid_scenarios.status` is `blocked`.
- `src.ev_model.proposed_local_charge_point_counts()` exposes the proposed
  values for audit only.
- Country-level D-010 Outlook queries are rejected if supplied as proposed
  local-count provenance.

## Remaining Decisions

- PI must decide whether Lingewaard (`GM1705`) is an acceptable representative
  local cluster for the SimBench case.
- PI must decide whether municipality-level clustering is acceptable while the
  neighbourhood-list endpoint returns HTTP 500, or whether Agent C should wait
  for/recover neighbourhood-level data.
- A-014 remains proposed and cannot allocate counts until EV-007/Q-7 supplies
  signed local totals.
- Public charging profile behavior remains separately blocked by the Elaad
  profile-generation specification.
