# E2.S4 D-014 Statistical PV Orientation/Tilt Packet

Status: proposed packet only. No raw D-014 capacity, PV-map, roof, or geometry data was downloaded, and no numeric PV capacity, orientation/tilt class weight, capacity convention, node allocation, or PV conversion formula is approved.

## Why This Exists

The PI reviewed the heavier external PV-map/building-level geometry direction and judged it too intensive before the first real experiment. This packet pivots the first-experiment PV geometry route to a lightweight statistical orientation/tilt class approach, while keeping building-level and roof-level extraction as a later sensitivity or validation improvement.

## Proposed First-Experiment Route

- Keep PV-CAP-001 separate: installed capacity still comes from the local Alkmaar CBS PV-capacity anchor scaled to 2035 with a signed II3050/scenario growth factor.
- If orientation/tilt heterogeneity is needed before executable PV use, use a signed statistical class table, not per-building roof extraction.
- The future class table must record class ID, declared azimuth basis, tilt, capacity-weight fraction, source or assumption ID, installed-capacity input reference, capacity convention, PV conversion config ID, and provenance.
- PVGIS remains qualitative sanity/provenance only unless a later signed decision changes its role.
- PV-PARAM-001 remains proposed/fail-closed; this packet does not approve `PR = 0.86`, direct-GHI conversion, pvlib, or any plane-of-array formula.

## Deferred Heavy Workflow

3DBAG, DEGO, Zonnedakje, CBS building/geography tables, or other PV-map routes may still support later sensitivity, validation, or allocation work after explicit PI approval, retrieval/checksum registration, license review, and a long-run/checkpoint plan if needed. They are not first-experiment building-level geometry inputs.

## PI Approval Keys Still Needed

- statistical orientation/tilt source;
- orientation class bins;
- tilt class bins;
- class weight values and weighting convention;
- DC/AC capacity convention;
- D-014 capacity value artifact;
- node allocation rule;
- PV conversion formula or pvlib/PVGIS-style route;
- losses, temperature, and clipping parameters;
- PVGIS or other sanity criteria.

Suggested STATUS update:
`E2.S4 PV model and weather inputs | C | in-progress | D-014 now has a proposed lightweight statistical PV orientation/tilt packet; heavy building-level PV-map/3DBAG extraction is deferred from first-experiment scope; PV capacity values, class weights, PV-PARAM conversion, allocation, and final paired validation remain blocked | PR: <this PR>`
