# E2.S4 D-014 First-Experiment PV Value-Decision Packet

## Purpose

This packet turns the merged D-014/PV approval packets into a concise PI review surface before executable first-experiment PV generation. It is metadata-only and remains fail-closed: it narrows what the PI must choose, but it does not approve any PV value or formula.

## What The Packet Consumes

- `D014-PV-CAPACITY-VALUE-CHOICE-PACKET` for CBS Alkmaar anchor plus II3050 growth equation candidates.
- `D014-PV-ORIENTATION-TILT-VALUE-CHOICE-PACKET` for unsigned statistical orientation/tilt source-backed and assumption-fallback candidates.
- `D014-PV-PARAM-CONVERSION-SOURCE-CHOICE-PACKET` for pvlib-style POA versus direct-GHI fallback choices.
- `D014-PV-FIRST-EXPERIMENT-APPROVAL-PACKET` for the existing approval checklist.
- `D014-PV-EXECUTABLE-PREFLIGHT-GUARD` for fail-closed executable behavior.

The committed metadata packet records paths, sizes, SHA-256 values, and statuses for those inputs.

## PI Choices Narrowed

Recommended review route, still unsigned: use the later signed D-014/PV-CAP capacity artifact, a later signed statistical orientation/tilt class distribution, and a signed lightweight conversion treatment. The preferred conversion route for review is statistical plane-of-array if the PI signs decomposition/transposition/albedo and parameter choices; direct KNMI-GHI scalar conversion remains only an explicit fallback if signed.

The packet keeps separate approval keys for capacity convention, losses/performance ratio, temperature coefficient, clipping rule, node allocation, A-016 scenario consistency, PVGIS qualitative-only provenance, and final paired HP/PV acceptance.

## Non-Claims

No PV capacity value, II3050 growth factor, capacity convention, orientation/tilt bin or weight, performance ratio, loss value, temperature coefficient, clipping rule, conversion formula, node allocation, PV output, net-load/event analysis, `P(E)`, threshold run, capacity screen, manuscript number, roof/building/3DBAG/PV-map geometry, or final paired HP/PV acceptance is approved or produced.

## Artifacts

- Metadata: `data/metadata/weather_pv/d014_pv_first_experiment_value_decision_packet.json`
- Loader/guard: `src/pv_model.py::PVFirstExperimentValueDecisionPacket`
- Generator: `data/get_pv_capacity.py --write-d014-pv-first-experiment-value-decision`

## Validation

- `./.venv/Scripts/python.exe -m pytest -q tests/test_data_sources.py tests/test_pv_model.py tests/test_methods_registry.py`: 133 passed in 85.07s.
- `./scripts/task.ps1 ownership`: passed for Agent C changed paths.
- `git diff --check`: passed; Git reported line-ending warnings only.
- `./scripts/task.ps1 test-fast`: 702 passed, 1 skipped, 7 deselected in 195.18s.
