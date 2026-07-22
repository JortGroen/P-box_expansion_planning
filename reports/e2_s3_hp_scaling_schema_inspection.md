# E2.S3 D-013 HP Scaling Schema Inspection

Decision packet ID: `E2-S3-HP-SCALING-SCHEMA-INSPECTION`

Status: source-readiness evidence only. This packet refreshes D-013 schema metadata from already-retrieved ignored raw files. It does not download new data, approve annual HP TWh values, sign 2035 HP adoption, sign D-004, run paired-weather or cold-spell acceptance, run net-load/event/`P(E)`, produce capacity-screen conclusions, or create manuscript numbers.

## Command

```powershell
.\.venv\Scripts\python.exe data\get_hp_scaling.py --inspect-existing
```

The command performs no network access. It reads the existing ignored raw files under `data/raw/hp_scaling/`, refreshes source metadata under `data/metadata/hp_scaling/`, and writes `data/metadata/hp_scaling/hp001_alkmaar_gm0361_schema_inspection_packet.json`.

## What Was Deepened

The earlier D-013 retrieval packet captured ZIP members and the first 64 KiB of each PBL CSV. This follow-up records full small-file schema/indicator-unit metadata for the already retrieved PBL Startanalyse Alkmaar ZIP:

| PBL file | Rows inspected | New evidence |
|---|---:|---|
| `Alkmaar_bebouwing.csv` | 726 | Confirms building/dwelling stock schema only; no `Code_Indicator`/`Eenheid` pair table. |
| `Alkmaar_strategie.csv` | 5346 | Records 81 unique `Code_Indicator`/`Eenheid` pairs, including 39 heat/energy-like pairs. Examples include `H01_Vraag_totaal`, `H02_Vraag_RV`, and `H03_Vraag_TW`, each with unit `[GJ/weq/jaar]`. |
| `Alkmaar_totaalbebouwing.csv` | 67 | Confirms residential building-type columns usable for PI-reviewed class crosswalk evidence: `Vrijstaande_woning`, `2_onder_1_kap`, `Rijwoning_hoek`, `Rijwoning_tussen`, `Meersgezinswoning_laag_midden`, and `Meersgezinswoning_hoog`. |

The script also records column classifications for candidate SFH, MFH, residential-stock, strategy/pathway, heat/energy, and DHW-like fields. These are schema candidates only, not selected source-use values.

## Interpretation For PI Review

The refreshed schema strengthens the case that PBL Startanalyse contains heat-demand-like indicators in `Alkmaar_strategie.csv`, but it still does not by itself sign a local HP annual scaling formula. The PI still needs to decide:

1. whether `H01_Vraag_totaal`, `H02_Vraag_RV`, `H03_Vraag_TW`, or another exact PBL indicator can be interpreted as useful thermal heat demand for HP-001 scaling;
2. whether `[GJ/weq/jaar]` should be converted through dwelling-equivalent counts, and which `weq` denominator is appropriate;
3. whether `H02` and `H03` provide the required HP-001 space/DHW split or require documentation-backed reinterpretation;
4. whether PBL strategy or variant columns are pathway/suitability only or signed adoption/electrification evidence; and
5. which separate 2035 HP adoption source or scenario remains required before executable component TWh values are produced.

Agent C recommendation: treat this as stronger PBL source-use evidence for PI review, but keep annual values unsigned until exact indicators, units, denominators, conversions, and 2035 adoption are signed.

## Boundaries

No annual component values are computed. No raw files are committed. The D-013 source bundle remains public-source-only, and the confidential thesis remains excluded from citation, value provenance, and committed data.

## Suggested STATUS Update

`E2.S3 HP model | C | in-progress | D-013 PBL/CBS schema inspection deepened for PI source-use review; annual TWh/adoption values, D-004 acceptance, cold-spell tolerances, and integrated analysis pending | PR: <this PR>`
