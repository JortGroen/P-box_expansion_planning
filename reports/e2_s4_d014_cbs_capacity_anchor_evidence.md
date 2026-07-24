
# E2.S4 D-014 CBS Alkmaar PV Capacity Anchor Evidence

## Purpose

This packet advances PV-CAP-001 by retrieving the smallest source-backed CBS evidence bundle for the local Alkmaar PV-capacity anchor. It remains fail-closed: the packet records source rows and schema, but it does not approve a PV installed-capacity value or any executable convention.

## Retrieved Evidence

- CBS table: `85005NED`, `Zonnestroom; vermogen en vermogensklasse, bedrijven en woningen, regio`.
- Geography filter: Alkmaar municipality `GM0361`.
- Exact row query: `https://opendata.cbs.nl/ODataApi/OData/85005NED/TypedDataSet?%24filter=RegioS+eq+%27GM0361%27`.
- Raw ignored bundle: `data/raw/pv_capacity/d014_cbs_85005ned_alkmaar_gm0361_anchor_evidence.json`.
- Raw bundle SHA-256: `b2efd245a974ccd462ebedb340a48d399d65a454b2aef4caa7a09cea91341963`.
- Raw bundle size: 46844 bytes.
- CBS table modified timestamp in retrieved metadata: `2026-06-12T02:00:00`.
- Retrieved Alkmaar rows: 63.

## Schema and Candidate Choices

CBS exposes these relevant fields: `Installaties_1` in `aantal`, `OpgesteldVermogenVanZonnepanelen_2` in `kWp`, `OpgesteldVermogenOmvormers_3` in `kW`, and `ProductieVanZonnestroom_4` in `mln kWh`. The retrieved periods are 2019-2023 definitive and 2024-2025 nader voorlopig. Exact row candidates are recorded for latest definitive all-activity-plus-homes, latest definitive homes-only sensitivity, latest provisional all-activity-plus-homes, and latest provisional homes-only sensitivity.

## Still Unsigned

The PI still needs to choose the source period, sector/category key, capacity field, capacity unit/DC-vs-AC convention, II3050 scenario and growth factor, node allocation rule, statistical orientation/tilt source and weights, and PV-PARAM conversion treatment before executable PV capacity or PV output can be produced.

## Boundaries

No II3050 retrieval was performed in this PR. No roof/building/3DBAG/PV-map geometry was retrieved. No final PV value, net-load/event/P(E), threshold analysis, capacity screen, manuscript number, or final paired HP/PV acceptance was produced.
