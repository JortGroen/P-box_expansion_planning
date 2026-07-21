# E2.S6 Adoption Scenarios

Status: local scaling method approved by EV-007; integrated EV adoption use still waits for Agent C to predeclare a representative CBS neighbourhood cluster, retrieve ElaadNL local forecast outputs, and derive local home/public charge-point totals.

## Source Evidence

Sourced national values:

- D-010, ElaadNL Outlook Mobiliteit 2026 scenariotool/API, retrieved 2026-07-20T14:52:59Z through 2026-07-20T14:53:01Z.
  - Home endpoint: `https://outlook.elaad.nl/api/proxy_v2?endpoint=/charging_infrastructure?area_type=country&scenario={scenario}&location=home`
  - Public endpoint: `https://outlook.elaad.nl/api/proxy_v2?endpoint=/charging_infrastructure?area_type=country&scenario={scenario}&location=public`
  - Dashboard provenance: `https://outlook.elaad.nl/` states the scenariotool provides projections to CBS-neighbourhood level, links the full report/model background, flags the outlook as assumption-based/indicative with 24-month validity, and licenses the site as CC BY-NC-ND 4.0.
  - API fields used: `type=charging_infrastructure`, `year={2030,2033,2035}`, `month=12`, `scenario={low,middle,high}`, `location={home,public}`.
  - Rounding rule: the floating API field `number` is rounded to the nearest integer for provenance tables only.
- D-011, Netbeheer Nederland II3050 edition 2, publication page dated 2023-10-11, `https://www.netbeheernederland.nl/publicatie/ii3050-eindrapport`.
  - Used for 2030-2050 infrastructure-scenario framing only.
  - No numeric charge-point counts are copied from II3050 in this E2.S6 config.

Derived values:

- `configs/scenarios.yaml` records national D-010 API values and their rounded integers as national Outlook projections.
- These values are not physical charge-point counts for SimBench and must not enter nodal allocation directly.

Pending local values:

- Local SimBench-grid home and public charge-point totals are not selected in this report.
- Public charging requires its own local basis and is not inferred from the home-charge-point scaling.
- E2.S6 T2/T3 remain incomplete for integrated use until the EV-007 cluster route produces local totals and A-014 per-node allocations.

## National Outlook Projections

These national values are retained as source provenance only.

| Year | Scenario | Location | API number | Rounded national count | Response sha256 |
|---:|---|---|---:|---:|---|
| 2030 | low | home | 1,634,177.7449595847 | 1,634,178 | `cdcdf135240c32cdb8cfa542cc6d71ee41876b429377e48e19c38678c82d2cb9` |
| 2033 | low | home | 1,870,266.7429415546 | 1,870,267 | `cdcdf135240c32cdb8cfa542cc6d71ee41876b429377e48e19c38678c82d2cb9` |
| 2035 | low | home | 1,984,323.4950302262 | 1,984,323 | `cdcdf135240c32cdb8cfa542cc6d71ee41876b429377e48e19c38678c82d2cb9` |
| 2030 | low | public | 314,335.9035997926 | 314,336 | `22af52bec13d927d485d2b496bf4931fc30612b037cf48435f46183bb1b000c0` |
| 2033 | low | public | 459,410.09530765587 | 459,410 | `22af52bec13d927d485d2b496bf4931fc30612b037cf48435f46183bb1b000c0` |
| 2035 | low | public | 570,314.1329274195 | 570,314 | `22af52bec13d927d485d2b496bf4931fc30612b037cf48435f46183bb1b000c0` |
| 2030 | middle | home | 1,767,963.1122278408 | 1,767,963 | `777423434d9e0f5963137e4e66ab7481fe4368dee4580d83b64a705630a02ec2` |
| 2033 | middle | home | 2,014,739.6849298074 | 2,014,740 | `777423434d9e0f5963137e4e66ab7481fe4368dee4580d83b64a705630a02ec2` |
| 2035 | middle | home | 2,138,671.7452869583 | 2,138,672 | `777423434d9e0f5963137e4e66ab7481fe4368dee4580d83b64a705630a02ec2` |
| 2030 | middle | public | 374,749.2559221372 | 374,749 | `de3f28a73a6261a87c9aaa54edbe64544ff2656ba4086f33c323695ee6763546` |
| 2033 | middle | public | 562,418.2211790042 | 562,418 | `de3f28a73a6261a87c9aaa54edbe64544ff2656ba4086f33c323695ee6763546` |
| 2035 | middle | public | 695,942.1030282071 | 695,942 | `de3f28a73a6261a87c9aaa54edbe64544ff2656ba4086f33c323695ee6763546` |
| 2030 | high | home | 1,885,470.9511492967 | 1,885,471 | `c789b73c05d330dc539bd8c104c44566e552f576de59f53dfdce10b472faa2d9` |
| 2033 | high | home | 2,135,097.773705465 | 2,135,098 | `c789b73c05d330dc539bd8c104c44566e552f576de59f53dfdce10b472faa2d9` |
| 2035 | high | home | 2,252,661.058461302 | 2,252,661 | `c789b73c05d330dc539bd8c104c44566e552f576de59f53dfdce10b472faa2d9` |
| 2030 | high | public | 433,759.695192586 | 433,760 | `c8357fbdf99dc0606c671969994a8aa931d8969192dea0a78c4fa688ae1eed4c` |
| 2033 | high | public | 649,640.3622993053 | 649,640 | `c8357fbdf99dc0606c671969994a8aa931d8969192dea0a78c4fa688ae1eed4c` |
| 2035 | high | public | 808,048.9252578203 | 808,049 | `c8357fbdf99dc0606c671969994a8aa931d8969192dea0a78c4fa688ae1eed4c` |

## Local-Grid Scaling Options

EV-007 resolves Q-7 by selecting Option A as the primary local scaling method:

- Option A: select a predeclared representative CBS neighbourhood or cluster using ElaadNL's local forecasts. This directly uses the source's local projection capability and avoids interpreting national totals as feeder counts.
- Option B: derive local counts from national adoption rates multiplied by a sourced SimBench-equivalent household or service-area denominator. Home and public charging need separate denominators; public charging cannot simply inherit the home basis. EV-007 keeps this only as a fallback or sensitivity if local forecast retrieval or justification fails.

## Possible Second-Stage Allocation

A-014 is approved only as a second-stage allocation after EV-007 local totals exist. The project may allocate each approved local total across the 115 in-service SimBench `net.load` rows using static `p_mw` weights and deterministic largest-remainder rounding. No national-total-derived `K_r` table is reported or permitted.

## Governance Notes

- EV-004 remains intact: the residential behavior source is the fixed ElaadNL 2030 home `cp` library, and planning-year variation will change only physical charge-point counts after local totals are approved.
- EV-005 replacement governance remains open because local cohort sizes `K_home`, `K_public`, and per-node `K_r` are not yet established.
- No held-out EV batches were opened, used, summarized, or analyzed for this task.
