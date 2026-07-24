# E2.S4 D-014 PV Orientation/Tilt Source-Choice Packet

Status: proposed packet only. No raw D-014 capacity, PV-map, roof, building, location-level, PVOutput, PVGIS, or geometry data was downloaded. No source, class bins, class weights, capacity value, conversion formula, or allocation is approved.

## Why This Exists

PV-ORIENT-001 approves the first-experiment scope: represent PV orientation and tilt with a typical/statistical distribution, not building-level or roof-level PV-map extraction. This packet turns that scope into the next PI decision: which source should define the statistical class distribution.

## Candidate Source Order For PI Review

1. `killinger_2018_pv_system_characteristics`: primary empirical candidate if the required country/cluster distribution parameters are accessible and citable. It is source-backed for PV-system metadata and distribution-function framing, but values still need extraction and PI signoff.
2. `utrecht_rooftop_pv_observed_systems`: Dutch regional plausibility context. Useful for checking whether proposed classes look locally credible, but not enough by itself for Alkmaar/2035 fleet weights unless the PI accepts the sample limitation.
3. `ramadhani_2023_rooftop_uncertainty_method`: open method template for statistical azimuth/tilt uncertainty. It is not Dutch installed-PV evidence, so using its distribution form would be a transfer assumption.
4. `pi_declared_simple_class_prior`: transparent fallback only if the PI prefers a signed expert prior over more source work before the first experiment.

PVGIS can support qualitative or later signed class-wise sanity checks. pvlib or an equivalent formula can support implementation if PV-PARAM is amended. JRC/DBSM, 3DBAG, and other building-level routes remain future improvements after the first experiment.

## Required Before Executable PV Generation

- signed orientation/tilt distribution source;
- source access/citation or license boundary;
- orientation and tilt class bin definitions;
- class weights and whether they are capacity-, installation-, area-, or assumption-weighted;
- azimuth and tilt angle conventions;
- signed PV conversion treatment for classes;
- PV-PARAM-001 or amended conversion decision;
- signed D-014 capacity value artifact;
- signed node allocation rule.

## What Remains Blocked

This packet does not approve numerical orientation/tilt distribution values, `PR = 0.86`, direct-GHI conversion, a plane-of-array formula, capacity convention, per-node allocation, net-load/event analysis, `P(E)`, thresholds, capacity screens, manuscript results, or final paired HP/PV acceptance.

Suggested STATUS update:
`E2.S4 PV model and weather inputs | C | in-progress | D-014/PV-ORIENT-001 now has a proposed statistical orientation/tilt source-choice packet; heavy building-level PV-map/3DBAG work remains deferred until after the first real experiment; class source, bins, weights, PV-PARAM conversion, D-014 capacity values, allocation, and final paired validation remain blocked | PR: <this PR>`
