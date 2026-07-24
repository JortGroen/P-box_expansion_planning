# E2.S3 HP-001 Executable Value-Binding Decision Packet

Decision packet ID: `E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET`

Status: proposed approval template only. This packet does not approve annual HP TWh values, 2035 HP adoption/electrification, D-004 paired-weather acceptance, cold-spell tolerances, net-load/event/`P(E)`, capacity-screen conclusions, threshold runs, manuscript numbers, or probability results.

## Why This Exists

The project now has enough source evidence to ask the PI a precise value-binding question: HP-001 approves the When2Heat shape/COP boundary, D-013 public source retrieval/checksum evidence is present, and D013-PBL-MAPPING/A-015 approves the PBL indicator mapping assumption. What remains is not more parsing; it is explicit approval or amendment of the executable binding choices.

## PI Decisions Requested

| Key | Candidate decision | Boundary |
|---|---|---|
| `value_column` | Use PBL `Referentie_2030` from `Alkmaar_strategie.csv`. | Not approved here. |
| `denominator` | Use `I11_woningequivalenten [Woning]` as the intensity denominator. | Not approved here. |
| `unit_conversion` | Convert GJ/year to TWh/year by dividing by `3,600,000`. | Not approved here. |
| `sfh_mfh_split` | Allocate SFH/MFH with CBS 85035NED count shares. | Not approved here. |
| `adoption_electrification` | Provide or approve the 2035 HP service/adoption/electrification scenario for space and DHW. | Still missing; no executable 2035 HP-served values. |
| `d004_paired_weather_acceptance` | Approve later evidence that HP and PV used exact common WEATHER-001 identities and calendars. | Separate from annual value binding. |
| `cold_spell_tolerances` | Approve later numerical coldest-window and near-freezing tolerances before a real cold-spell acceptance run. | Separate from annual value binding. |

## Fail-Closed Handoff

The generated metadata packet is `data/metadata/hp_scaling/hp001_alkmaar_gm0361_executable_value_binding_decision_packet.json`. It contains an unsigned candidate binding record with blank approval IDs and `executable_binding_allowed: false`.

If the PI later signs or amends the five annual value-binding choices, a follow-up PR can change the record status to `approved_for_executable_value_binding`, record approval IDs, and let `src.hp_model.hp001_local_scaling_config_from_value_binding_record(...)` construct a guarded `HP001LocalScalingConfig`. That still would not be enough for integrated HP use until `d004_paired_weather_acceptance` and `cold_spell_tolerances` are also signed.

## Suggested STATUS Update

E2.S3 HP remains scaffold/readiness. A PI-facing executable value-binding approval template exists for the five HP annual scaling choices plus the separate D-004 paired-weather and cold-spell gates; no annual HP TWh values, 2035 adoption/electrification, D-004 final acceptance, integrated analysis, or manuscript results are approved.
## 2026-07-24 Guard Tightening

The executable handoff now requires more than setting the record status and filling approval IDs. A future signed record must also set `approval_state.executable_binding_allowed = true`, declare `missing_approval_keys = []`, preserve the exact five annual value-binding keys, retain the D013-PBL-MAPPING/A-015 indicator-mapping approvals, and mark every SFH/MFH space/DHW component draft with `annual_twh_status = approved_for_executable_value_binding`.

This tightening is fail-closed only. It does not approve `Referentie_2030`, `I11_woningequivalenten [Woning]`, GJ-to-TWh conversion, the CBS SFH/MFH split, 2035 HP service/adoption/electrification, A-016 integrated scenario consistency, D-004 paired-weather acceptance, cold-spell tolerances, annual HP TWh values, net-load/event analysis, `P(E)`, capacity screens, or manuscript results.
