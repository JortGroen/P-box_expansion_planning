
# E2.S4 D-014 PV Orientation/Tilt Value-Choice Packet

## Purpose

This packet advances PV-ORIENT-001 from a source-choice scaffold to a PI-reviewable statistical orientation/tilt value choice for the first real experiment. It remains fail-closed: no class table, class weight, PV capacity value, DC/AC convention, conversion formula, or node allocation is executable from this packet.

## Source-Backed Context

- PV-ORIENT-001 is approved: first-experiment PV orientation and tilt must use statistical classes only; building-level, roof-level, location-specific, 3DBAG, and heavy PV-map workflows are deferred.
- Killinger et al. (2018) remains the preferred empirical source candidate because it analyzes PV-system metadata, including tilt and azimuth distributions, across a large international installed-PV dataset.
- Publicly available source snippets support the existence of distribution fitting and broad representative ranges, but this PR does not extract a Netherlands/Alkmaar class-weight table. Those values need a cited table/figure trace or a PI-signed assumption.
- PVGIS can support class-wise sanity/provenance later, but not statistical class weights or the realized WEATHER-001 path.

## Proposed Unsigned Fallback Candidate

The committed metadata packet proposes `pi_prior_5_class_symmetric_rooftop_candidate_v1` only as an assumption fallback if the PI prefers a transparent first-screen prior over additional empirical extraction before the first experiment. Its candidate capacity-weight fractions are:

| Class | Candidate azimuth convention | Candidate tilt | Candidate weight | Status |
| --- | --- | ---: | ---: | --- |
| south_mid_tilt | 0 degrees from south | 35 degrees | 0.40 | assumption-only, unsigned |
| southeast_low_mid_tilt | -60 degrees from south | 25 degrees | 0.15 | assumption-only, unsigned |
| southwest_low_mid_tilt | +60 degrees from south | 25 degrees | 0.15 | assumption-only, unsigned |
| east_west_low_tilt | -90/+90 degrees from south split | 15 degrees | 0.20 | assumption-only, unsigned |
| flat_low_tilt | placeholder 0 degrees from south | 10 degrees | 0.10 | assumption-only, unsigned |

The weights sum to 1.0 and are capacity-weight candidates, not final PV capacity allocation.

## PI Decisions Still Needed

- Choose empirical extraction versus explicit PI-prior fallback.
- Sign source/assumption ID, class bins, representative angles, weights, angle convention, and capacity-weighting convention.
- Decide whether classes alter PV conversion through a plane-of-array/pvlib route or remain blocked until a later PV-PARAM amendment.
- Sign D-014 capacity value artifact, DC/AC convention, II3050 growth factor, and node allocation separately.

## Boundaries

No raw D-014 data was downloaded. No final PV values, net-load/event/P(E), threshold run, capacity screen, manuscript number, or final paired HP/PV acceptance is produced.
