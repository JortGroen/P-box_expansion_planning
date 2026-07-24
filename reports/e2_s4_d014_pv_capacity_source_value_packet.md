# E2.S4 D-014 PV Capacity Source/Value Packet

Status: proposed packet only. No raw D-014 data was downloaded, no PV installed-capacity value is approved, and executable PV remains fail-closed.

## Why This Exists

PV-CAP-001 approves the route concept: use a local Alkmaar CBS PV-capacity anchor and scale it to the frozen 2035 planning layer with a signed Netbeheer Nederland II3050/scenario growth factor. The next step is to make that route concrete enough for PI approval before any retrieval or value binding.

## Proposed Source Route

- CBS anchor: CBS StatLine/OData table `85005NED`, Alkmaar municipality `GM0361`, with schema probes for table info, fields, periods, regions, and sector/size-class codes.
- CBS row template: filter `TypedDataSet` by `RegioS eq 'GM0361'`, a PI-selected period key, and a PI-selected sector/size-class key.
- Capacity field candidates: panel capacity / paneelvermogen, inverter capacity / omvormervermogen, and installation count as diagnostic only. Exact field keys must come from `DataProperties` after retrieval/schema inspection.
- II3050 growth source: Netbeheer Nederland II3050 edition 2 appendices, Table A.1 row `Zon PV* GW`, with the 2035 scenario column and denominator still requiring PI approval.
- Optional geometry/allocation: 3DBAG roof geometry, DEGO, Zonnedakje, and CBS building/geography data remain source-discovery or allocation/geometry candidates until concrete data and licenses are registered.

## Fail-Closed Approval Keys

Executable PV capacity remains blocked until all of these are signed: CBS source checksum, Alkmaar geography, CBS source period, CBS capacity field, capacity unit and DC/AC convention, II3050 source checksum or page evidence, II3050 scenario column, II3050 growth-factor value, node allocation rule, and PV-PARAM-001 or an amended conversion decision.

## Boundaries

This packet does not approve numeric PV capacity, the `PR = 0.86` direct-GHI conversion proposal, capacity convention, growth factor, per-node allocation, net-load/event analysis, `P(E)`, threshold analysis, capacity screens, or manuscript results.

## Files

- Metadata packet: `data/metadata/weather_pv/d014_pv_capacity_source_value_packet.json`
- Helper: `data/get_pv_capacity.py`
- Guard model: `src/pv_model.py::PVCapacitySourcePacket`