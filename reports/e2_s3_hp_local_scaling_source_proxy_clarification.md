# E2.S3 HP-001 Local Scaling Source And Proxy Clarification

Decision packet ID: `E2-S3-HP-SOURCE-PROXY-CLARIFICATION`

Status: PI clarification packet only. The local HP scaling route remains
proposed, and this packet does not retrieve data or approve annual TWh values,
adoption counts, D-004 acceptance, cold-spell tolerances, net-load integration,
event analysis, `P(E)`, capacity-screen results, Q-5-dependent threshold work,
or manuscript results.

## PI Decision Requested

Before Agent C can prepare a source-retrieval/checksum/value-proposal PR, the
PI should answer three linked questions:

1. Should HP-001 use Alkmaar municipality `GM0361` as the local HP scaling
   proxy, matching EV-007A and the D-004 Alkmaar weather/PV point?
2. Should the first HP scaling retrieval bundle use CBS StatLine dwelling stock
   by municipality/type plus PBL Startanalyse 2025 Alkmaar municipality files
   as the local stock, class-crosswalk, and heat-demand/pathway evidence?
3. Should 2035 HP adoption be a separate signed scenario source, with
   Startanalyse pathway/suitability evidence treated as context rather than as
   adoption unless the PI explicitly signs that interpretation?

Agent C recommendation: yes to all three. This keeps geography aligned across
EV, HP, and weather/PV inputs; uses official, downloadable Dutch sources; and
prevents technical heat-transition evidence from being silently converted into
2035 adoption volumes.

## Current Governance State

- HP-001 is approved for residential SFH/MFH space heat plus domestic hot water
  shape/COP source use from D-003.
- D-003 national When2Heat `heat_demand_*` values remain diagnostic anchors,
  not the default local annual scaling source.
- `E2-S3-HP-LOCAL-SCALING-ROUTE-PACKET` is still proposed. It does not yet
  authorize retrieval or executable values.
- D-004 remains proposed; WEATHER-001 is the shared HP/PV weather contract.
- Q-5 still blocks integrated event-based scientific analysis and manuscript
  threshold results.

## Candidate Proxy Choice

### Option A: Alkmaar `GM0361` As HP Proxy

Use the same municipality proxy already accepted for EV local adoption and D-004
weather/PV source selection.

Advantages:

- keeps HP, EV, PV, and weather inputs on one ex ante local geography;
- avoids selecting a heat-specific municipality after inspecting grid results;
- provides a compact first retrieval target because PBL Startanalyse publishes
  municipality ZIP files, including Alkmaar;
- lets later reports compare HP and EV adoption assumptions without explaining
  two different local proxies.

Limitations:

- Alkmaar municipality is still a proxy for a benchmark grid, not the physical
  SimBench service area;
- local heat-demand and dwelling-type evidence may need a source crosswalk to
  HP-001 `SFH/MFH`;
- the choice does not by itself approve any 2035 HP adoption fraction.

### Option B: Separate HP-Specific Proxy

Select another municipality, CBS neighbourhood cluster, or service-area
denominator for heat only.

Advantages:

- may better match a residential heating stock or an eventual feeder-scale
  interpretation if the PI has such an exogenous area in mind.

Limitations:

- adds another geography to explain beside EV-007A and D-004;
- needs a fresh ex ante selection rationale before any integrated results;
- risks making HP and EV local scaling harder to audit side by side.

Recommendation: Option A unless the PI has a pre-existing HP-specific service
area that should override cross-component geographic consistency.

## Candidate Source Bundle

The next retrieval PR should use only sources the PI selects. Agent C proposes
the following first bundle for review.

| Role in HP scaling | Candidate source | Why it fits | What it cannot decide alone |
|---|---|---|---|
| Local dwelling stock and SFH/MFH denominator | CBS StatLine `85035NED`, dwelling stock by type and region | The table reports dwelling stock by municipality and distinguishes single-family and multi-family dwelling types. CBS states the table is based on BAG extracts and that figures are definitive. | It does not provide heat demand, DHW demand, or 2035 HP adoption. |
| Current heat-pump context | CBS StatLine `85523NED`, heat pumps by sector, counts, thermal capacity, and energy flows | Official context for current Dutch heat-pump stock and sectoral energy flows. | It is not local 2035 adoption and should not become the adoption branch by default. |
| Local heat-demand/pathway evidence | PBL Startanalyse aardgasvrije buurten 2025, especially Alkmaar municipality ZIP | PBL describes Startanalyse 2025 as municipality/buurt data from Vesta MAIS for alternative heat strategies, including building stock and energy-use indicators. | It is a modelled heat-transition and cost/pathway dataset, not automatically an observed local adoption forecast. |
| Shape/COP anchor | D-003 When2Heat 2023-07-27 | Already approved by HP-001 for Dutch residential shape/COP source use. | National heat-demand totals are not local HP scaling unless separately signed. |

No source is registered as executable HP scaling evidence by this packet. The
follow-up PR would record exact URLs, licenses, retrieval commands, raw/metadata
paths, checksums, schema fields, and candidate values for PI review.

Official source facts checked for this packet:

- CBS StatLine `85035NED` is a dwelling-stock-by-type-and-region table, changed
  on 2026-04-23, with data available from 2021 and definitive figures. CBS
  says it is based on BAG extracts.
- CBS defines multi-family dwellings in the table as dwellings in buildings
  with two or more residential objects, with examples including flats,
  apartments, gallery-access, porch, upstairs, and downstairs dwellings.
- PBL Startanalyse 2025 publishes municipality data and says it uses the Vesta
  MAIS model to provide buurt-level results for heat-transition alternatives.
- PBL's 2025 data portal states the data can be used with attribution under
  CC BY 4.0 NL.

## Proposed Crosswalk

Use the exact source taxonomy in the retrieval PR, but predeclare this default
mapping for PI review:

- HP-001 `SFH` maps to CBS `Eengezinswoningen totaal`.
- HP-001 `MFH` maps to CBS `Meergezinswoningen totaal`.
- PBL Startanalyse building or dwelling categories should be mapped to
  `SFH/MFH` only if the downloaded Alkmaar files expose a compatible category
  or a documented aggregation field. Otherwise CBS provides the SFH/MFH split
  and PBL provides heat-demand/pathway evidence at municipality or buurt level.
- `COM` remains excluded from the HP-001 primary route, even if PBL files
  include utility-building heat.

If the PBL Alkmaar files cannot separate residential heat demand from utility
buildings or cannot support the SFH/MFH split, the retrieval PR should stop at
schema evidence and bring the ambiguity back to the PI instead of inventing a
split.

## Adoption Boundary Choices

The source/proxy decision must distinguish three concepts:

1. Local heat demand: annual useful heat or final energy that could be served
   by HP-001.
2. Technical/pathway suitability: whether a building or area is assigned to an
   individual-electric heat strategy, a heat-network strategy, or another
   alternative.
3. 2035 adoption: the scenario fraction or count actually served by heat pumps
   in the project year.

Recommended rule:

- use PBL Startanalyse pathway evidence as local suitability/context;
- use a separate signed adoption/electrification scenario for 2035 volumes;
- allow Startanalyse pathway shares to become adoption only if the PI signs
  that interpretation before any values are calculated.

DHW handling also needs an explicit adoption interpretation:

- if the adoption source means full-electric residential HP service, use the
  same adoption fraction for HP-001 space and DHW;
- if it means hybrid space-heating heat pumps, DHW needs a separate source or
  the scenario should not be treated as the HP-001 primary boundary.

## Proposed Follow-Up If PI Approves

After PI approval of the proxy/source/adoption-boundary choices, Agent C can
prepare a retrieval/checksum/value-proposal PR with these non-final artifacts:

- retrieval script support for the selected CBS/PBL files or API responses;
- metadata under `data/metadata/hp_scaling/`;
- ignored raw files under `data/raw/hp_scaling/`;
- a proposed DATA_REGISTER row for the HP scaling source bundle;
- schema report identifying exact fields used for SFH, MFH, space heat, DHW,
  local geography, and any adoption scenario;
- candidate component annual thermal TWh values marked `proposed`, not
  executable;
- tests for parsing, unit conversion, SFH/MFH mapping, and separation of
  space/DHW component values.

No candidate value should be wired into `configs/`, runner inputs, net-load
integration, event analysis, `P(E)`, capacity screens, or manuscript text until
the PI signs the values and the remaining D-004/cold-spell blockers are
resolved.

## Decision Form For PI

Recommended approval wording for a later signed decision, if accepted:

```text
Approve HP scaling source/proxy route: use Alkmaar GM0361 as the local HP
scaling proxy; retrieve CBS StatLine dwelling-stock-by-type evidence and PBL
Startanalyse 2025 Alkmaar municipality files as the first HP scaling source
bundle; use PBL pathway/heat evidence as local heat and suitability context,
not as 2035 adoption unless separately signed; require a separate 2035 HP
adoption/electrification source before annual TWh values become executable.
```

Alternative PI edits should state which proxy, source bundle, or adoption
interpretation replaces the recommended route.

## Suggested STATUS Update

`E2.S3 HP model | C | in-progress | HP-001 source/proxy clarification packet prepared; route, sources, annual TWh/adoption values, D-004 acceptance, and integrated analysis pending | PR: <this PR>`
