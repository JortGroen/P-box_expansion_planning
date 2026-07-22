# E2.S4 D-004 WEATHER-001 Input Artifact

Status: accepted for D-004 source/member executable-input use; final paired HP/PV and cold-spell acceptance pending.

This follow-up exposes the PI-approved `D004-SOURCE-MEMBER-ACCEPTANCE` decision as a committed WEATHER-001 member index that downstream executable-input gates can inspect without opening raw KNMI/PVGIS files. The artifact is `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json`.

The artifact preserves the approval ID, member IDs, shared weather-driver IDs, source string, content SHA-256 values, UTC/local timestamp spans, `calendar_id`, 900-second cadence, timestep counts, member metadata paths, and the KNMI `T`/`Q` conversions used for temperature and GHI. It marks `ready_for_executable_input_gate=true` and `accepted_for_source_member_use=true` only for the source/member layer.

The source-use boundary remains unchanged. KNMI station 249 Berkhout is the realized weather path for 2014-2023 WEATHER-001 members. PVGIS-SARAH3 remains qualitative seasonal/peak sanity and provenance/calibration context only, with `pvgis_realized_weather_path=false`.

The artifact deliberately keeps final gates blocked: final paired HP/PV acceptance, HP cold-spell acceptance, and integrated net-load/event/`P(E)`/capacity-screen/manuscript analysis all remain unauthorized. Tests check both the generated artifact builder and the committed artifact so a later executable-input consumer can rely on the accepted source/member identity while still seeing the pending gates.
