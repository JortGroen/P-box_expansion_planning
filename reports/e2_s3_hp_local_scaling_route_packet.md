# E2.S3 HP-001 Local Annual Scaling Route Packet

Decision packet ID: `E2-S3-HP-LOCAL-SCALING-ROUTE-PACKET`

Status: PI decision packet only. HP-001 approves the D-003 When2Heat Dutch
residential shape/COP boundary, but not local annual thermal TWh values or
2035 heat-pump adoption volumes. This packet proposes a source-backed route
for those inputs; it does not sign any data source, final value, D-004
acceptance, cold-spell tolerance, net-load integration, event analysis,
`P(E)`, capacity screen, Q-5-dependent threshold result, or manuscript number.

## Purpose

The HP model now supports the approved HP-001 residential components:

- SFH space heat: `NL_heat_profile_space_SFH` with `NL_COP_ASHP_radiator`.
- MFH space heat: `NL_heat_profile_space_MFH` with `NL_COP_ASHP_radiator`.
- SFH domestic hot water: `NL_heat_profile_water_SFH` with
  `NL_COP_ASHP_water`.
- MFH domestic hot water: `NL_heat_profile_water_MFH` with
  `NL_COP_ASHP_water`.

The remaining blocker is the annual thermal scale for those four components.
D-003 supplies normalized shape and COP trajectories. It must not silently
supply local 2035 annual heat volumes because HP-001 explicitly keeps national
When2Heat `heat_demand_*` totals as diagnostic/source anchors rather than the
default local scaling source.

## Recommended Primary Route

Agent C recommends a bottom-up local adoption-and-heat route:

1. Select a PI-signed local service-area proxy for HP scaling before any
   integrated congestion result is inspected. The EV layer already uses
   Alkmaar municipality `GM0361`; using the same proxy for HP would be tidy but
   still needs an explicit HP scaling decision because EV-007A did not sign a
   heat-demand boundary.
2. Source local residential stock or local residential heat-demand denominators
   for `SFH` and `MFH` from official Dutch statistics or a registered local
   heat-transition dataset.
3. Source or sign a 2035 heat-pump adoption/electrification scenario for each
   class. The scenario should state whether it counts full-electric HP homes,
   hybrid HP homes, all homes assigned to an individual-electric transition
   pathway, or another boundary.
4. Compute annual thermal TWh for the four HP-001 components, preserving
   `SFH/MFH` and `space/DHW` separately.
5. Pass only the signed component annual TWh values into
   `hp001_residential_when2heat_components`, with provenance that identifies
   the source files, geography, class mapping, adoption scenario, units, and
   approval IDs.

This route keeps the executable HP inputs local, auditable, and compatible
with HP-001 while avoiding direct use of national historical When2Heat totals
as the SimBench/local 2035 volume.

## Candidate Source Classes

The following sources are candidates for the future source bundle. They are
not yet D-registered for executable HP scaling, and no values from them are
approved in this packet.

| Input need | Recommended source class | Candidate source examples | Review point |
|---|---|---|---|
| Local geography and dwelling stock | Official Dutch regional housing statistics | CBS StatLine or CBS open-data tables for dwelling stock by municipality, dwelling type, and building characteristics | Needed to map local dwellings to SFH/MFH without using SimBench load rows as a demographic denominator. |
| Current heat-pump stock or heating system prevalence | Official Dutch heat-pump/heating-system statistics | CBS StatLine/maatwerk heat-pump and main-heating-installation tables; RVO built-environment monitor products | Useful as calibration/context; current stock alone is not a 2035 adoption scenario. |
| Local heat-transition pathway or technical suitability | Official local heat-transition datasets | PBL Startanalyse/Aardgasvrije Buurten datasets or a municipal heat-transition plan if PI selects one | Can supply a source-backed individual-electric or heat-network split, but it is a pathway/suitability input unless explicitly used as adoption. |
| National future adoption scenario | Official scenario/projection source | PBL Klimaat- en Energieverkenning, RVO monitor/forecast products, national policy scenario documents | Can provide low/middle/high trajectory context; needs downscaling and scenario-boundary approval. |
| Annual space and DHW heat intensity | Official local heat-demand or energy-use data | CBS/Klimaatmonitor local residential gas/heat use, PBL/Vesta or Startanalyse heat-demand fields, or a signed external building-energy source | Must distinguish useful thermal heat from gas final energy and must split space heat from DHW. |
| Shape/COP and diagnostic national anchors | Already approved D-003 for HP-001 shape/COP | When2Heat `NL_heat_profile_*`, `NL_COP_*`, and diagnostic `NL_heat_demand_*` evidence | Shape/COP are approved by HP-001; national heat-demand totals are not default local scaling. |

Minimum registration before execution: a future source PR should add or update
`DATA_REGISTER.md` rows for any external HP scaling source bundle, record URLs,
licenses, retrieval scripts or API calls, checksums/metadata, units, and
status. This packet itself does not retrieve or checksum those sources.

## Formulas For PI Review

Let `c` be `SFH` or `MFH`, `u` be `space` or `water`, and `s` be the signed
2035 HP adoption scenario.

Preferred thermal-demand formula when local heat demand is available:

```text
H_hp_TWh[c,u,s] =
    H_local_thermal_TWh[c,u]
  * f_hp_service[c,u,s]
```

where:

- `H_local_thermal_TWh[c,u]` is source-backed local annual useful heat demand
  for class `c` and end use `u`;
- `f_hp_service[c,u,s]` is the signed fraction of that class/end use served by
  the HP-001 heat-pump boundary in scenario `s`.

Fallback dwelling-intensity formula when the source gives per-dwelling heat
intensity:

```text
H_hp_TWh[c,u,s] =
    N_dwellings[c]
  * f_hp_dwellings[c,s]
  * q_thermal_kWh_per_dwelling_year[c,u]
  / 1,000,000,000
```

where:

- `N_dwellings[c]` is the local source-backed dwelling count for class `c`;
- `f_hp_dwellings[c,s]` is the signed 2035 HP adoption fraction for class `c`;
- `q_thermal_kWh_per_dwelling_year[c,u]` is source-backed annual useful heat
  per adopted dwelling for class `c` and end use `u`;
- division by `1,000,000,000` converts kWh to TWh.

Gas-final-energy conversion, if used, requires separately signed assumptions:

```text
H_local_thermal_TWh[c,u] =
    gas_final_m3[c]
  * kWh_per_m3_gas
  * eta_useful_heat
  * end_use_share[c,u]
  / 1,000,000,000
```

This conversion should be a fallback because `kWh_per_m3_gas`,
`eta_useful_heat`, and `end_use_share` are scientific assumptions unless they
come directly from a registered source.

The executable HP component maps would be:

```text
space_heat_twh_by_class = {
    "SFH": H_hp_TWh["SFH","space",s],
    "MFH": H_hp_TWh["MFH","space",s],
}

water_heat_twh_by_class = {
    "SFH": H_hp_TWh["SFH","water",s],
    "MFH": H_hp_TWh["MFH","water",s],
}
```

No `COM` key is allowed in the HP-001 primary route.

## Building-Class Mapping

Proposed mapping for PI review:

- `SFH`: detached, semi-detached, row, corner, terraced, or other
  ground-bound single-family dwellings, depending on the exact source
  taxonomy.
- `MFH`: apartment, flat, maisonette, gallery-access, and other multi-family
  dwellings.
- Excluded from primary: `COM` and mixed commercial/service heat.

If the source cannot separate `SFH` and `MFH`, the packet recommends one of
two PI choices before execution:

- approve a documented crosswalk from source dwelling types to `SFH/MFH`; or
- approve a class-aggregate HP sensitivity rather than pretending class-specific
  inputs exist.

## Domestic Hot Water Boundary

HP-001 includes domestic hot water in the primary residential boundary. The
local scaling route should therefore include water heat for the same adopted
residential classes unless the PI signs a different service boundary.

Recommended rule:

```text
f_hp_service[c,"water",s] = f_hp_service[c,"space",s]
```

only when the selected adoption source describes full residential heat
electrification or all-electric HP adoption. If the source describes hybrid
space-heating heat pumps only, DHW needs a separate adoption/service fraction
or the scenario must be labeled hybrid and not used as the HP-001 primary
boundary.

## Uncertainty And Sensitivity Options

The packet recommends predeclared scenario branches rather than tuning a single
annual TWh value after seeing grid results.

Candidate uncertainty axes:

- Adoption volume: low/middle/high 2035 HP adoption fractions or counts from a
  signed source. If only a national trajectory is available, downscale it by a
  signed local denominator and keep the branch label.
- Geography: primary signed local proxy; sensitivity using another
  predeclared municipality or service-area denominator if the PI wants a
  robustness check.
- Heat intensity: source-provided low/middle/high or year-range variation. The
  existing D-003 2008-2015 `heat_demand_*` min/mean/max evidence may be used
  as a diagnostic comparison, not as the default local scaling source unless
  separately signed.
- DHW service: HP-001 primary uses space plus DHW. A space-only diagnostic can
  be retained for comparison but would not represent the signed HP-001 primary
  boundary unless HP-001 is amended.
- Technology/COP: HP-001 fixes ASHP radiator for space and ASHP water for DHW.
  Floor, GSHP, WSHP, or mixed-technology alternatives require separate signed
  sensitivities.

Sensitivity branches must be declared before E3.S2b/E3.S3 threshold-based
integrated screens or any probabilistic work. They are not selected after
inspecting congestion.

## What Becomes Executable After PI Approval

After the PI signs the source bundle, local geography, class mapping, adoption
scenario(s), heat-intensity boundary, and formulas, Agent C can implement a
small deterministic HP scaling materialization step that:

1. retrieves/checksums the approved HP scaling source files or API responses;
2. records a proposed or approved `DATA_REGISTER.md` row as appropriate;
3. writes a machine-readable HP scaling metadata file with source identity,
   geography, class mapping, scenario IDs, formulas, units, and component TWh;
4. calls `hp001_residential_when2heat_components` with the approved
   `space_heat_twh_by_class` and `water_heat_twh_by_class` maps;
5. preserves the component provenance through `When2HeatCsvMetadata` and the
   later HP profile manifest; and
6. keeps WEATHER-001 member identity and D-004 paired-weather acceptance
   separate from annual scaling.

The resulting HP component would be source-ready for downstream integration
only after D-004/WEATHER-001 paired-weather acceptance and cold-spell tolerance
requirements are also satisfied. It would still not authorize event analysis,
`P(E)`, capacity-screen conclusions, Q-5-dependent threshold results, or
manuscript claims without the relevant downstream gates and manifests.

## Decision Request

Recommended PI choices to make next:

1. Confirm whether Alkmaar `GM0361` is also the local HP scaling proxy, or
   select a different service-area denominator before integrated results.
2. Select the primary source class for local annual heat:
   local heat-demand data, local dwelling-count times heat-intensity data, or a
   registered external building-energy source.
3. Select the 2035 adoption/electrification source and branch structure.
4. Confirm whether full-electric HP adoption is required for HP-001 DHW, or
   whether hybrid HP scenarios are sensitivity-only.
5. Authorize a future retrieval/checksum PR for the selected source bundle.

Agent C recommendation: approve the bottom-up route structure first, then
choose concrete sources and values in a follow-up source-retrieval PR. This
keeps the current packet useful without smuggling unsigned numbers into the
model.

## Suggested STATUS Update

`E2.S3 HP model | C | in-progress | HP-001 local annual scaling route packet proposed; annual TWh/adoption values, D-004 acceptance, cold-spell tolerances, and integrated analysis pending | PR: <this PR>`
