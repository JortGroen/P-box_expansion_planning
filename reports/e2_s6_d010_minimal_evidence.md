# D-010 ElaadNL Outlook Minimal Evidence Freeze

Task: E2.S6 / E2.S2 EV provenance cleanup
Status: source-approved for EV-007A local-count support
Artifact: `data/metadata/ev_adoption/d010_elaad_outlook_minimal_evidence.json`
Artifact SHA-256: `3bed5e741f5816e5c6fb11d59beb315f908d0029460654fcdd43fa9aa90d8952`

## Purpose

This packet freezes the minimal committed evidence needed to support the EV-007A approved 2035 Alkmaar home/public EV adoption counts. It is derived from already committed D-010 metadata and does not make new API calls or commit raw dashboard responses.

## Source Boundary

- Source: ElaadNL Outlook Mobiliteit Scenariotool/API
- App URL: `https://outlook.elaad.nl/scenariotool`
- API base used during retrieval: `https://api-outlook-v2-prd.thankfulrock-fcd5ae60.westeurope.azurecontainerapps.io`
- Scenariotool version: `ElaadNL Scenariotool v1.0.0`
- Site update: `2026-06-09`
- License noted by source site: `CC BY-NC-ND 4.0 as stated on https://outlook.elaad.nl/`
- Raw-data policy: response SHA-256 hashes are recorded; raw JSON payload bytes are not redistributed.

## Approved EV-007A Counts

| Scenario | Location | API number | Rounded count | Retrieved UTC | Response SHA-256 |
| --- | --- | ---: | ---: | --- | --- |
| low | home | 7991.80830348258 | 7992 | 2026-07-21T09:33:34.9663859Z | `2b91de9e67c0ccddffa5c11293571391886b7a59414ae4549f5a0aad868e9bd4` |
| low | public | 4182.6860541073265 | 4183 | 2026-07-21T09:33:36.3256749Z | `b97e7883c719e726b349ae16f8438d16308762125684d6b871772fac1dcef169` |
| middle | home | 9386.406999563205 | 9386 | 2026-07-21T09:33:36.4313293Z | `7f5e22504bdf98a36b407c2e861d4583dec040ead7d93e29958b625f3b48de46` |
| middle | public | 5127.01005454311 | 5127 | 2026-07-21T09:33:36.5641931Z | `108956322a7a9ef6872aa02bcd6605bbc2aacfc0840c1a4d07974c44364b9243` |
| high | home | 10343.304477753807 | 10343 | 2026-07-21T09:33:36.7211960Z | `3f16acac00eb389bca0105ed1b7ecc899c4cf5a0983d76450ab4bcf8dd519224` |
| high | public | 6137.847745988891 | 6138 | 2026-07-21T09:33:36.9886557Z | `b6c2d52a8baf9f41719fbe4449554a12f06fa292d5ab716781aac5ee15ad0b07` |

## Schema Evidence

The approved local-count queries use `/charging_infrastructure` with `area_type=municipalities`, `area_identifier=GM0361`, one scenario, and one location. Each response returned 26 rows. The selected evidence row is filtered to `year = 2035` and `month = 12` and preserves `scenario`, `location`, `variant`, and floating `number` before nearest-integer rounding.

## Guardrails

- National D-010 Outlook totals remain context/provenance only and must not flow directly into SimBench physical counts.
- D-010 supports adoption counts only; public profile capacity behavior remains governed by EV-008A.
- Delft (`GM0503`) remains a checked fallback, not the selected EV-007A proxy.
- No EV profile generation, held-out access, net-load/event analysis, `P(E)`, capacity screen, or manuscript number was produced.
