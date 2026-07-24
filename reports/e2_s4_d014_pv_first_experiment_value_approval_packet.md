# E2.S4 D-014 PV First-Experiment Value-Approval Packet

Status: proposed PI decision packet only. This work does not approve PV values and does not generate PV output.

## Why this packet exists

The D-014/PV route now has separate proposed packets for the CBS Alkmaar capacity anchor, II3050 2035 growth evidence, statistical orientation/tilt choices, PV-PARAM conversion choices, and future PV component-output artifact shape. The new `D014-PV-FIRST-EXPERIMENT-VALUE-APPROVAL-PACKET` turns those pieces into one compact approval checklist for the PI.

## What the packet asks the PI to sign later

- CBS 85005NED Alkmaar `GM0361` capacity anchor: period, sector/category, capacity field, source row/value, and DC/AC convention.
- II3050 2035 scaling: scenario column, denominator, growth formula/value, and A-016 consistency with EV/HP/PV scenario labels.
- PV-ORIENT-001 statistical orientation/tilt route: source, bins, representative angles, weights, and capacity-weighting convention only; no roof/building/PV-map/3DBAG geometry before the first experiment.
- PV-PARAM conversion: signed conversion route, losses/performance treatment, temperature/clipping treatment, and PVGIS/KNMI boundary.
- Output policies: PV reactive-power convention, repository-relative manifest path/checksum policy, node allocation and normalization, and final paired HP/PV acceptance.

## Fail-closed behavior

The committed metadata packet records `executable_pv_generation_authorized = false`. If future code attempts real PV generation before the required signatures exist, the only valid response is a blocker manifest with no arrays and no component-output manifest.

## Non-claims

No PV capacity value, II3050 growth factor, orientation/tilt value, performance ratio, conversion formula, reactive-power policy, node allocation, net-load/event analysis, `P(E)`, threshold run, capacity screen, manuscript number, or final paired HP/PV acceptance is approved or produced here. PVGIS remains qualitative sanity/provenance context only; KNMI remains the realized WEATHER-001 path.

## Suggested STATUS update

`E2.S4 PV model and weather inputs | C | in-progress | D-014 first-experiment PV value-approval packet added; executable PV remains fail-closed pending signed capacity, II3050/A-016, orientation/tilt, PV-PARAM, reactive-power/path, allocation, and final paired gates | PR: <this PR>`
## Validation

- `python -m pytest -q tests/test_data_sources.py::test_d014_first_experiment_value_approval_packet_is_concise_and_fail_closed tests/test_pv_model.py::test_committed_d014_first_experiment_value_approval_packet_is_fail_closed tests/test_pv_model.py::test_first_experiment_value_approval_packet_rejects_silent_generation tests/test_methods_registry.py`: passed, 7 tests.
- `python -m pytest -q tests/test_data_sources.py tests/test_pv_model.py`: passed, 158 tests.
- `./scripts/task.ps1 ownership`: passed.
- `git diff --check`: passed.
- `./scripts/task.ps1 test-fast`: failed with 786 passed, 1 skipped, 1 failed, 7 deselected. The failing test is `tests/test_ev_model.py::test_committed_ev_generic_loader_manifest_packet_matches_builder`; this branch does not modify EV files, and the failure reproduces as a standalone EV committed-manifest equality mismatch.