# E2.S4 PV-PARAM-001 Decision Packet

Status: proposed PI decision packet only. This packet proposes a first-pass PV conversion parameter set, but `PVSystemConfig` remains fail-closed until the PI signs `PV-PARAM-001` and a separate signed capacity artifact such as PV-CAP-001 supplies `installed_capacity_kw`. It does not run final paired HP/PV acceptance, cold-spell acceptance, net-load aggregation, event detection, `P(E)`, threshold analysis, capacity screens, or manuscript results.

## Proposed Primary First-Pass Rule

For each accepted D-004 WEATHER-001 member, use KNMI `Q`-derived `ghi_w_per_m2` directly as a simplified irradiance index:

`pv_kw[t] = min(installed_capacity_kw, max(0, installed_capacity_kw * 0.86 * ghi_w_per_m2[t] / 1000.0))`

The proposed template is `pv_param_001_first_pass_ghi_pr086_no_temp_clipped_v1`.

## Parameter Choices For PI Approval

- Installed capacity: outside PV-PARAM-001. PV-CAP-001 is the separate capacity-source route using a CBS Alkmaar local PV capacity anchor scaled to 2035 with a signed II3050/scenario growth factor; this packet only consumes a signed `installed_capacity_kw` per node/fleet once supplied.
- Performance ratio: propose `0.86`, traced only to the approved PVGIS reference request `loss_percent=14.0` as `1 - 14/100`.
- Irradiance basis: use WEATHER-001 `ghi_w_per_m2` directly. This is not a plane-of-array transposition claim.
- Tilt/aspect: keep PVGIS 35 degree south-facing geometry as qualitative sanity/provenance only in the primary first pass.
- Temperature: propose `temperature_coefficient_per_c=0.0` and `reference_temperature_c=25.0`, disabling temperature correction until a module-specific coefficient is signed.
- Clipping: propose `clip_to_capacity=true` after nonnegative conversion.

## Traceability And Boundaries

KNMI station 249 remains the realized weather source. PVGIS-SARAH3 remains qualitative sanity/provenance and the source of the normalized 14% loss setting only; it is not a realized weather path and does not provide installed capacity. PV-PARAM-001 does not decide numeric capacity, capacity convention, 2035 scaling, or per-node allocation. The proposed direct-GHI rule is a first-screen simplification. A later signed transposition/module model may replace it.

## PI Questions

1. Approve or amend the proposed first-pass formula and `performance_ratio=0.86`.
2. Confirm that executable installed capacity is supplied separately through PV-CAP-001 or an amended signed capacity artifact, not by PV-PARAM-001.
3. Confirm that PVGIS tilt/aspect remains provenance-only until a plane-of-array treatment is separately signed.
4. Confirm that temperature correction is disabled for the primary first pass pending a signed module coefficient.

## Suggested STATUS Update

`E2.S4 PV model and weather inputs | C | in-progress | PV-PARAM-001 proposed first-pass parameter choices and methods wording prepared; executable PV remains fail-closed pending PI signoff, installed-capacity source, exact HP/PV weather identity, and cold-spell tolerances | PR: <this PR>`
