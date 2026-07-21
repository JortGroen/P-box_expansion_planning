# E2.S4 Q-8 Shared Weather Contract

Status: implementation scaffold for PI review. This report covers only the
neutral shared weather contract needed by HP and PV under ALEA-001.

## Implemented Contract

`src/weather_model.py` adds a neutral `WeatherMember` with:

- `member_id`
- `shared_weather_driver_id`
- `source`
- paired `timestamps_utc` and `timestamps_local`
- `temperature_c`
- `pv_weather_fields`, including required `ghi_w_per_m2`
- JSON-serializable `provenance` and `metadata`
- stable `content_sha256`
- `identity_record()` for HP/PV manifest comparison

The contract validates timezone-aware UTC/local timestamp alignment, strict
chronology, constant cadence, finite temperature, finite nonnegative PV weather
fields, and JSON-serializable audit metadata. It also provides canonical
15-minute local-year calendar helpers and `assert_same_weather_realization()`.

## Compatibility

The tests demonstrate that the same neutral `WeatherMember` can feed:

- `src.hp_model.align_heat_pump_profile`, preserving `member_id`,
  `shared_weather_driver_id`, timestamps, temperature, PV field names, and
  provenance in the HP weather identity record.
- `src.pv_model.generate_pv_profile`, preserving the same
  `shared_weather_driver_id`, member ID, source, and UTC/local timestamps while
  using the same `ghi_w_per_m2` irradiance channel.

This resolves the contract shape without moving the implementation into either
`hp_model.py` or `pv_model.py`.

## Boundaries

No Q-8 implementation work in component-owned weather classes was attempted.
No net-load, congestion, threshold, event, `P(E)`, or manuscript-result
analysis was run. Real D-004 weather completeness and acceptance remain
separate PI-review tasks.
