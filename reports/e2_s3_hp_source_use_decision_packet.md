# E2.S3 HP-001 D-013 Source-Use Decision Packet

Decision packet ID: `E2-S3-HP-SOURCE-USE-DECISION-PACKET`

Status: proposed PI source-use packet only. D-013 retrieval/checksum route is approved, and HP-001 shape/COP source use is approved, but this packet does not sign annual HP TWh values, 2035 heat-pump adoption, D-004 acceptance, cold-spell tolerances, net-load integration, event analysis, `P(E)`, capacity screens, threshold runs, manuscript numbers, or probability results.

## PI Decision Requested

Decide whether the retrieved D-013 bundle can support local HP-001 annual scaling values, and if so under which limited role:

1. Use CBS `85035NED` as the signed Alkmaar `GM0361` SFH/MFH dwelling-stock denominator and class crosswalk.
2. Treat PBL Startanalyse 2025 Alkmaar primarily as pathway/suitability and local building-stock context unless the PI signs a specific heat-demand interpretation for named columns.
3. Keep CBS `85523NED` as national/current heat-pump context only, not as local Alkmaar 2035 adoption.
4. Require a separate signed 2035 HP adoption/electrification source or scenario before any annual component TWh values become executable.

Agent C recommendation: approve item 1 now if the PI accepts the municipality proxy; keep item 2 as context pending deeper documentation of heat-demand columns and units; retain item 3 as context only; request a separate adoption source for item 4.

## Source Classification

| Source | What the retrieved schema supports | What it does not support by itself | Recommended source-use status |
|---|---|---|---|
| CBS `85035NED` dwelling stock/type | Alkmaar municipality `GM0361`; periods `2021JJ00`-`2026JJ00`; `BeginstandWoningvoorraad_1`; dwelling-type titles including `Eengezinswoningen totaal` and `Meergezinswoningen totaal`; proposed HP-001 crosswalk `SFH = Eengezinswoningen totaal`, `MFH = Meergezinswoningen totaal`. | Annual heat demand, DHW demand, heat-pump adoption, and 2035 projection. | Usable as local SFH/MFH stock denominator after PI signs the proxy/year rule. |
| PBL Startanalyse 2025 Alkmaar ZIP | Municipality ZIP with semicolon CSVs. `Alkmaar_bebouwing.csv` exposes dwelling/building stock by type, construction period, and label. `Alkmaar_strategie.csv` exposes neighbourhood identifiers, woning/utiliteit counts, reference years, strategy columns, and variants including lucht/water and hybrid heat-pump pathways. `Alkmaar_totaalbebouwing.csv` exposes neighbourhood totals and residential building-type columns including detached, semi-detached, row, and multi-family categories. | The cheap inspection does not prove useful-thermal annual space heat, domestic hot water heat, or 2035 HP adoption values. Strategy/pathway columns are not adoption without PI interpretation. The current schema evidence does not establish a direct space/DHW split. | Pathway/suitability and class/context evidence now; heat-demand scaling only if the PI signs exact columns, units, and formulas after documentation review. |
| CBS `85523NED` heat-pump context | National/current table with sectors including `Woningen`; in-use counts, thermal capacity, heat production, electricity/gas use, and fossil-energy/emission context. | Local Alkmaar counts, 2035 adoption, SFH/MFH split, and space/DHW split. | Context and uncertainty framing only. |

## Proposed Component Route After PI Approval

The guarded HP model now supports the four HP-001 residential components separately before aggregation:

| Component | Building class | End use | Shape column | COP column | Annual value status |
|---|---|---|---|---|---|
| `sfh_space` | SFH | space | `NL_heat_profile_space_SFH` | `NL_COP_ASHP_radiator` | unsigned |
| `mfh_space` | MFH | space | `NL_heat_profile_space_MFH` | `NL_COP_ASHP_radiator` | unsigned |
| `sfh_water` | SFH | water | `NL_heat_profile_water_SFH` | `NL_COP_ASHP_water` | unsigned |
| `mfh_water` | MFH | water | `NL_heat_profile_water_MFH` | `NL_COP_ASHP_water` | unsigned |

Executable integrated HP loads should require all four component records to carry signed annual-scaling provenance, including an approval ID. Until then, the code may build scaffold profiles for parser/calendar/component-readiness tests, but those profiles remain non-executable for integration.

## PBL Ambiguities To Resolve

- Geography: Alkmaar `GM0361` is consistent with EV and D-004, but still needs PI confirmation as a heat-demand proxy if not already accepted for values.
- Heat-demand basis: Startanalyse may contain Vesta MAIS modeled pathway and cost outputs; the current cheap schema evidence does not by itself identify a signed useful-thermal heat-demand field.
- Space versus DHW: no explicit signed field mapping exists yet for splitting annual heat into HP-001 `space` and `water` components.
- SFH/MFH mapping: CBS gives a clean total SFH/MFH denominator; PBL exposes more detailed dwelling/building-type categories that need a signed crosswalk before class-specific heat intensity is calculated from PBL.
- Adoption: Startanalyse strategy or variant assignment is technical/pathway evidence unless the PI explicitly signs it as the 2035 adoption scenario. National/current CBS heat-pump context is not local 2035 adoption.
- Units: PBL column names include bracketed units for several stock/count fields; any energy or cost columns selected later must record the exact unit text and conversion formula before use.

## What Becomes Executable Later

After PI approval, a follow-up PR can materialize proposed annual component values, still separate from integrated analysis, by:

1. selecting signed source columns and units for local heat demand or per-dwelling intensity;
2. selecting a signed 2035 adoption/electrification source or branch;
3. producing `space_heat_twh_by_class` and `water_heat_twh_by_class` maps for `SFH` and `MFH` only;
4. recording approval IDs in each component provenance record;
5. using the executable HP builder guard, which rejects unsigned component scales; and
6. keeping D-004 paired-weather acceptance and cold-spell tolerance signoff separate.

## Boundaries

No raw data is committed. The existing D-013 raw files remain ignored under `data/raw/hp_scaling/`. The confidential PI-supplied thesis is not cited, quoted, committed, or used as value provenance. Commercial heat remains outside HP-001 primary use and may enter only through a later signed sensitivity.

## Suggested STATUS Update

`E2.S3 HP model | C | in-progress | HP-001 source-use packet and guarded component-readiness code prepared; annual TWh/adoption values, D-004 acceptance, cold-spell tolerances, and integrated analysis pending | PR: <this PR>`
