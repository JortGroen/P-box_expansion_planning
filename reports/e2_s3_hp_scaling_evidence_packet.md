# E2.S3 HP-001 Alkmaar Scaling Evidence Packet

Status: D-013 public-source retrieval/checksum evidence only. This packet does
not approve annual HP TWh values, 2035 HP adoption, final scaling choices,
D-004 acceptance, paired-weather acceptance, net-load integration, event
analysis, `P(E)`, threshold runs, capacity screens, manuscript numbers, or
probability results.

## Retrieval Summary

Command:

```powershell
.\.venv\Scripts\python.exe data\get_hp_scaling.py --download
```

The run completed in seconds; no long-run notice was required because the
approved route consists of small CBS OData requests and one 215.1 kB PBL ZIP.
Raw files remain ignored under `data/raw/hp_scaling/`.

| Source key | Raw path | Size bytes | SHA-256 | URL |
|---|---:|---:|---|---|
| `cbs_85035ned_dwelling_stock` | `data/raw/hp_scaling/cbs_85035ned_alkmaar_dwelling_stock.json` | 142792 | `3c57f72ff32bebb38cb4a371ba35b0702b840fed3a5ce5639970d733c640606e` | `https://opendata.cbs.nl/ODataApi/OData/85035NED` |
| `pbl_startanalyse_2025_alkmaar` | `data/raw/hp_scaling/pbl_startanalyse_2025_alkmaar.zip` | 220262 | `e022f3cfcc227b41359545e405ba8c194d48731fa802302b8f027ccab01b1ff7` | `https://dataportaal.pbl.nl/data/Startanalyse_aardgasvrije_buurten/2025/Gemeentes/Alkmaar.zip` |
| `cbs_85523ned_heat_pump_context` | `data/raw/hp_scaling/cbs_85523ned_heat_pump_context.json` | 535260 | `739d32fc2f6721c1aabe5919ba8ee1efc8b3e328ffa3de44fd5308f42eba3e7b` | `https://opendata.cbs.nl/ODataApi/OData/85523NED` |

Metadata:

- `data/metadata/hp_scaling/hp001_alkmaar_gm0361_retrieval_manifest.json`
- `data/metadata/hp_scaling/hp001_alkmaar_gm0361_retrieval_checkpoint.json`
- `data/metadata/hp_scaling/cbs_85035ned_alkmaar_dwelling_stock_metadata.json`
- `data/metadata/hp_scaling/pbl_startanalyse_2025_alkmaar_metadata.json`
- `data/metadata/hp_scaling/cbs_85523ned_heat_pump_context_metadata.json`

## Schema Evidence

CBS `85035NED` is usable as dwelling-stock/type evidence for Alkmaar `GM0361`.
The retrieved metadata records table title `Woningvoorraad; woningtype op 1
januari, regio`, modification timestamp `2026-04-23T02:00:00`, periods
`2021JJ00` through `2026JJ00`, and 96 filtered Alkmaar records. The schema
contains `BeginstandWoningvoorraad_1` and `GemiddeldeOppervlakte_2`; D-013 uses
it as stock/type evidence only. The proposed HP crosswalk remains:

- SFH: `Eengezinswoningen totaal`
- MFH: `Meergezinswoningen totaal`

PBL `Alkmaar.zip` contains four files: `Alkmaar_bebouwing.csv`,
`Alkmaar_strategie.csv`, `Alkmaar_totaalbebouwing.csv`, and
`README_gemeentebestanden.txt`. The cheap schema inspection reads the ZIP
member table and the first 64 KiB of each CSV. It found semicolon-delimited CSV
headers. `Alkmaar_totaalbebouwing.csv` includes residential stock fields such
as `I09_aantal_woningen`, `Woning_Typegebouw`, `Vrijstaande_woning`,
`2_onder_1_kap`, `Rijwoning_hoek`, `Rijwoning_tussen`,
`Meersgezinswoning_laag_midden`, and `Meersgezinswoning_hoog`. `Alkmaar_strategie.csv`
includes strategy/pathway columns such as `Referentie_2023`, `Referentie_2030`,
`Strategie_1` through `Strategie_4`, and variants including lucht/water-source
heat-pump options. This is pathway/suitability evidence until the PI signs a
source-use interpretation for scaling.

CBS `85523NED` is complete context evidence in this packet: 672 retrieved
records, table modification timestamp `2026-04-30T02:00:00`, and columns for
in-use heat-pump counts, thermal capacity, heat production, and energy flows.
The retrieved sector dimension includes `Woningen`, `Utiliteitsgebouwen, kassen
en stallen`, and `Totaal gebouwen`. It remains national/current context only,
not a local Alkmaar 2035 adoption source.

## HP-001 Traceability

The later value proposal must preserve these four components separately before
aggregation:

| Component | Building class | End use | Shape column | COP column | Annual scaling status |
|---|---|---|---|---|---|
| `sfh_space` | SFH | space | `NL_heat_profile_space_SFH` | `NL_COP_ASHP_radiator` | unsigned |
| `mfh_space` | MFH | space | `NL_heat_profile_space_MFH` | `NL_COP_ASHP_radiator` | unsigned |
| `sfh_dhw` | SFH | water | `NL_heat_profile_water_SFH` | `NL_COP_ASHP_water` | unsigned |
| `mfh_dhw` | MFH | water | `NL_heat_profile_water_MFH` | `NL_COP_ASHP_water` | unsigned |

## Remaining PI Decisions

- Whether PBL Startanalyse 2025 Alkmaar may be used as heat-demand scaling
evidence, or only as suitability/pathway context.
- Whether the PBL files provide a defensible space/DHW split. The current cheap
schema inspection does not by itself sign such a split.
- Which source or scenario signs 2035 HP adoption/electrification fractions for
SFH/MFH and space/DHW.
- Whether DHW adoption follows space-heat adoption or requires a separate signed
assumption.
- Whether any annual thermal TWh values can be proposed from these files in the
next PR, and under which formulas.

## Boundaries

The PI-supplied private student thesis was not used as citation, committed
source, or value provenance. Commercial heat remains outside HP-001 primary use.
D-004 source acceptance, paired-weather cold-spell acceptance, and all
integrated analysis remain blocked separately.

## Suggested STATUS Update

E2.S3 HP local scaling: D-013 public CBS/PBL source files retrieved and
checksummed for Alkmaar `GM0361`; schema evidence packet prepared for PI review.
Annual HP TWh values, 2035 HP adoption, final scaling choices, D-004 acceptance,
paired-weather acceptance, and integrated results remain unsigned/not run.
