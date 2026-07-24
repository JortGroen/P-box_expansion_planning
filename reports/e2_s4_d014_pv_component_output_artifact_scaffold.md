# E2.S4 D-014 PV Component-Output Artifact Scaffold

## Purpose

This PR prepares the PV-owned side of future first-experiment PV component-output artifact generation. It does not generate real PV output. It records the manifest and NPZ shape that a later signed PV run can emit for IC-1, and it keeps the current committed D-014/PV packets fail-closed because the values and formulas remain unsigned.

## Current Behavior

`data/metadata/weather_pv/d014_pv_component_output_artifact_scaffold.json` consumes checksummed metadata for:

- `D014-PV-FIRST-EXPERIMENT-VALUE-DECISION-PACKET`
- `D014-PV-EXECUTABLE-PREFLIGHT-GUARD`
- the accepted D-004 WEATHER-001 source/member input artifact

The scaffold records that current committed D-014 packets are not executable and that invoking component-output generation must abort with a blocker manifest until signed PV capacity, orientation/tilt values, PV-PARAM conversion, allocation, A-016, paired HP/PV acceptance, and reactive-power policy artifacts exist.

## Future Artifact Shape

The future IC-1-compatible PV output manifest must carry `artifact_id`, `artifact_status`, `kind = pv`, component/node/member/source/calendar identity, `shared_weather_driver_id`, `array_path`, `array_sha256`, `timestep_count`, and provenance. The NPZ must include `p_kw`, `q_kvar`, and `timestamps` plus scalar metadata checked by the IC-1 loader. PV export is represented as negative `p_kw`; nonnegative `generation_kw` remains an internal PV diagnostic.

The proposed runner contract records deterministic config identity inputs and checkpoint/resume behavior: one signed weather member and node allocation per work unit, skip only checksum-verified outputs, and abort on changed config identity, missing checksums, unsigned approval IDs, or placeholder tokens in executable fields.

## Synthetic Fixture Coverage

`src.pv_model.write_pv_component_output_npz_artifact` can write a tiny `synthetic_fixture` PV output in tests. The test fixture is loaded through IC-1's existing NPZ artifact loader with `allow_synthetic_fixture=True`; loading it without that flag fails. Accepted specs reject unsigned/proposed/synthetic approval tokens.

## Non-Claims

No real PV array, PV capacity value, II3050 growth factor, orientation/tilt weight, conversion formula, loss value, temperature coefficient, clipping rule, reactive-power policy, node allocation, net-load/event analysis, `P(E)`, threshold run, capacity screen, manuscript number, roof/building/3DBAG/PV-map workflow, or final paired HP/PV acceptance is approved or produced.

## Validation

- Focused PV/data/methods tests:
  `.\.venv\Scripts\python.exe -m pytest -q tests/test_data_sources.py::test_d014_pv_component_output_artifact_scaffold_is_metadata_only tests/test_pv_model.py::test_committed_d014_pv_component_output_artifact_scaffold_fails_closed tests/test_pv_model.py::test_pv_component_output_artifact_scaffold_rejects_silent_generation_claim tests/test_pv_model.py::test_pv_component_output_writer_emits_ic1_compatible_synthetic_fixture tests/test_pv_model.py::test_pv_component_output_accepted_spec_rejects_unsigned_tokens tests/test_methods_registry.py`
  passed: 9 tests.
- `.\scripts\task.ps1 ownership` passed for Agent C-owned paths.
- `.\scripts\task.ps1 test-fast` passed: 728 passed, 1 skipped, 7 deselected.
- `git diff --check origin/main...HEAD` passed.
