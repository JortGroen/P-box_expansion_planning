# E2.S3 HP-001 Alkmaar Scaling Retrieval Route

Status: proposed source-binding route only. This packet does not retrieve raw
files, select checksums, approve D-013, make annual TWh values executable, sign
2035 HP adoption, or authorize D-004 acceptance, paired-weather acceptance,
net-load integration, event analysis, `P(E)`, threshold runs, capacity screens,
manuscript numbers, or probability results.

## Why This Exists

HP-001 approves the Dutch When2Heat shape/COP boundary for residential space
heat plus domestic hot water, but it does not approve local annual heat-pump
volumes. The next step needs an auditable public-source route for Alkmaar
`GM0361` that keeps three things separate:

- local residential heat demand or denominators;
- suitability/pathway evidence for heat-transition options;
- unsigned 2035 heat-pump adoption or electrification volume.

The PI-supplied private student thesis is treated only as confidential
source-discovery guidance. It is not quoted, cited, committed, or used as value
provenance.

## Proposed Public Source Bundle

| Role | Source | Exact route | Expected size/runtime | Proposed use | Boundary |
|---|---|---|---|---|---|
| SFH/MFH dwelling denominator | CBS StatLine `85035NED`, "Woningvoorraad; woningtype op 1 januari, regio" | Table page `https://www.cbs.nl/nl-nl/cijfers/detail/85035NED`; OData endpoint `https://opendata.cbs.nl/ODataApi/OData/85035NED` | Small filtered OData request; expected seconds to a few minutes | Alkmaar `GM0361` dwelling stock by woningtype, mapping `Eengezinswoningen totaal` to SFH and `Meergezinswoningen totaal` to MFH | Stock/type evidence only; not heat demand, DHW demand, or adoption |
| Local heat-demand and pathway context | PBL Startanalyse aardgasvrije buurten 2025 Alkmaar | Municipality download listing `https://dataportaal.pbl.nl/Startanalyse_aardgasvrije_buurten/2025/Gemeentes`, visible `Alkmaar.zip` link | PBL listing reports `Alkmaar.zip` as 215.1 kB; expected seconds | Inspect public CSV schema for local residential heat-demand fields, neighbourhood coverage, and pathway/suitability indicators | Pathway/cost/suitability output is not adoption evidence unless the PI signs that interpretation |
| HP context only | CBS StatLine `85523NED`, "Warmtepompen; aantallen, thermisch vermogen en energiestromen" | Table page `https://www.cbs.nl/nl-nl/cijfers/detail/85523NED`; OData endpoint `https://opendata.cbs.nl/ODataApi/OData/85523NED` | Small filtered national/context request; expected seconds to a few minutes | Current/national heat-pump categories, sector split, capacity, and energy-flow context | Not a local Alkmaar 2035 adoption source |

Current assessment: this route is not expected to exceed 15 minutes because it
uses small CBS filtered requests and one small PBL municipality ZIP. If a later
full-table pull, bulk archive, or slow source test is expected to exceed 15
minutes, Agent C must post the project long-run notice before launch.

## Checksum And Resume Workflow

Future retrieval command after PI approval:

```powershell
.\.venv\Scripts\python.exe data\get_hp_scaling.py --download --resume
```

Planned checkpoint:

```text
data/metadata/hp_scaling/hp001_alkmaar_gm0361_retrieval_checkpoint.json
```

Planned metadata:

```text
data/metadata/hp_scaling/hp001_alkmaar_gm0361_source_route_v1_plan.json
data/metadata/hp_scaling/cbs_85035ned_alkmaar_dwelling_stock_metadata.json
data/metadata/hp_scaling/pbl_startanalyse_2025_alkmaar_metadata.json
data/metadata/hp_scaling/cbs_85523ned_heat_pump_context_metadata.json
```

Planned raw paths, all ignored and uncommitted:

```text
data/raw/hp_scaling/cbs_85035ned_alkmaar_dwelling_stock.json
data/raw/hp_scaling/pbl_startanalyse_2025_alkmaar.zip
data/raw/hp_scaling/cbs_85523ned_heat_pump_context.json
```

Resume behavior to implement before retrieval:

- write each response first to a `.tmp` file under `data/raw/hp_scaling/`;
- compute SHA-256 and byte size before replacing the final raw file;
- update the checkpoint after each completed source with URL, byte size,
  SHA-256, retrieval timestamp, and the next pending source;
- on `--resume`, skip a completed source only if the raw file still matches the
  checkpoint byte size and SHA-256;
- fail closed if a file exists but does not match checkpoint metadata.

## Value-Proposal Route

After PI approval of the source route and after concrete checksums exist, the
follow-up value proposal should produce four still-reviewable annual thermal
inputs:

| Component | Shape column | COP column | Local-scaling evidence still needed |
|---|---|---|---|
| SFH space heat | `NL_heat_profile_space_SFH` | `NL_COP_ASHP_radiator` | SFH local space-heat demand or signed proxy |
| MFH space heat | `NL_heat_profile_space_MFH` | `NL_COP_ASHP_radiator` | MFH local space-heat demand or signed proxy |
| SFH domestic hot water | `NL_heat_profile_water_SFH` | `NL_COP_ASHP_water` | SFH local DHW demand or signed proxy |
| MFH domestic hot water | `NL_heat_profile_water_MFH` | `NL_COP_ASHP_water` | MFH local DHW demand or signed proxy |

The proposal should record formulas in this shape, with all terms source-backed
and unsigned until PI review:

```text
annual_thermal_twh(component)
  = local_heat_demand_or_proxy(component)
    * signed_2035_hp_adoption_or_electrification_fraction(component)
```

If the public PBL Alkmaar schema does not expose a defensible space/DHW split,
the value proposal must escalate that ambiguity rather than infer a hidden
split. If a 2035 adoption source is not signed, the route can prepare candidate
sensitivity axes but must not write executable annual TWh values.

## Ambiguities For PI Review

- Whether Alkmaar `GM0361` is the final HP service-area proxy or only the first
  public-source retrieval geography.
- Whether PBL Startanalyse 2025 Alkmaar contains directly usable residential
  heat-demand fields, and if so whether they represent space heat, DHW, or a
  combined heat demand.
- Whether the PBL neighbourhood/pathway outputs should be used only for
  suitability/pathway context or also as a source for annual heat-demand
  scaling.
- Which public source, scenario, or sensitivity should define unsigned 2035 HP
  adoption/electrification fractions for SFH/MFH and space/DHW.
- Whether DHW adoption should follow the same electrification fraction as space
  heat, or a separately signed domestic-hot-water assumption.

## Suggested STATUS Update

E2.S3 HP local scaling: proposed public-source retrieval/checksum route
prepared for Alkmaar `GM0361` using CBS dwelling-stock/type evidence, PBL
Startanalyse 2025 Alkmaar evidence, and CBS heat-pump context. No source files,
checksums, annual TWh values, 2035 HP adoption, D-004 acceptance, paired-weather
acceptance, or integrated results are signed.
