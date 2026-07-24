# E2.S4 D-014 PV Capacity Value-Choice Packet

Status: proposed recommendation packet only. No final PV capacity value, growth factor, capacity convention, allocation, PV generation, or integrated result is approved.

## Purpose

PV-CAP-001 has two evidence inputs on main: CBS Alkmaar `85005NED` anchor evidence and Netbeheer Nederland II3050 appendix growth evidence. This packet combines them into a concise PI decision aid for choosing a later executable PV capacity artifact.

## Candidate Equations

- Source-year matched DC route, recommended for PI review only: `pv_capacity_2035_kwp_dc = cbs_panel_capacity_kwp(period_key, sector_key) * ii3050_zon_pv_gw(2035, scenario_column) / ii3050_zon_pv_gw(2019_reference)`.
- Latest-definitive DC route: `pv_capacity_2035_kwp_dc = cbs_panel_capacity_kwp(2023JJ00, sector_key) * signed_ii3050_growth_factor_from_2023_to_2035`; blocked until a 2023-to-2035 denominator/crosswalk is signed.
- AC inverter variant: `pv_capacity_2035_kw_ac = cbs_inverter_capacity_kw(period_key, sector_key) * signed_ii3050_growth_factor_same_convention`; blocked until the PI signs AC/grid-facing capacity convention and PV-PARAM handling.

## Recommendation For PI Review

The packet recommends using a DC panel-capacity convention labelled `installed_capacity_kwp_dc` for the capacity-value artifact, with PV-PARAM-001 or an amendment later deciding how that maps to `PVSystemConfig.installed_capacity_kw`. The source-year matched equation is the cleanest first PI choice because it avoids silently applying a 2019-to-2035 national II3050 ratio to a 2023 local CBS anchor. The latest-definitive 2023 CBS anchor remains a useful alternative if the PI signs a denominator/crosswalk from 2023 to 2035.

## Scenario Consistency

A-016 remains blocking. II3050 `KA`/`ND`/`IA` columns cannot be silently equated with ElaadNL EV branches or HP/PBL/CBS choices. Before executable integrated use, the manifest needs the PV CBS source year, capacity field/convention, II3050 scenario column, growth factor, and signed scenario-consistency decision ID.

## Still Unsigned

The PI still needs to approve the CBS period, sector/category, field, unit and DC/AC convention, II3050 scenario column, growth denominator, formula and value, A-016 scenario mapping, node allocation, statistical orientation/tilt source and weights, and PV-PARAM conversion before executable PV can be produced.

## Boundaries

No final PV capacity value, PV generation, net-load/event/P(E), threshold analysis, capacity screen, manuscript number, roof/building/3DBAG/PV-map work, or final paired HP/PV acceptance was produced.
