# E2.S4 Shared Weather Contract Plan

Status: blocked on shared-weather Q-8 ownership. PR #43 has merged, so this
PR is now a clean follow-up plan on top of `origin/main`, not a stacked PV
implementation branch. The neutral implementation path
`src/weather_model.py` plus `tests/test_weather_model.py` failed Agent C
ownership preflight on branch `agent-c/E2.S4-shared-weather-contract-plan`.
This report is the fallback deliverable requested by the PI. It does not
implement code and does not claim real-source PVGIS/KNMI validation.

Dashboard files and legacy aggregate logs are maintainer-only. This branch
does not propose direct
`registers/STATUS.md` or `reports/AGENT_C_LOG.md` edits. The suggested
`registers/STATUS.md` update is listed near the end for the PR body/PI
dashboard.

## Contract Location

Target paths after shared-weather Q-8 resolution:

- `src/weather_model.py`
- `tests/test_weather_model.py`

The already-merged `src/pv_model.py` and `src/hp_model.py` should be migrated
to import the shared contract from `src.weather_model` once Q-8 ownership is
resolved. They should not keep separate HP-local or PV-local weather-member
classes in the final ALEA-001-compliant shape.

## Planned Types

The intended implementation is a small frozen dataclass model with
JSON-serializable records:

```python
@dataclass(frozen=True)
class WeatherProvenance:
    source: str
    temperature_source: str
    irradiance_source: str
    retrieval_metadata_paths: tuple[str, ...]
    source_file_records: tuple[Mapping[str, object], ...] = ()
    license: str | None = None
    notes: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class WeatherMember:
    member_id: str
    shared_weather_driver_id: str
    provenance: WeatherProvenance
    timestamps_utc: tuple[datetime, ...]
    timestamps_local: tuple[datetime, ...]
    temperature_c: tuple[float, ...]
    ghi_w_per_m2: tuple[float, ...]
    pv_weather_fields: Mapping[str, tuple[float, ...]] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)
    local_timezone: str = "Europe/Amsterdam"
```

`WeatherProvenance`:

- `source`: human-readable source label.
- `temperature_source`: source identifier for the temperature channel.
- `irradiance_source`: source identifier for irradiance/PV weather channels.
- `retrieval_metadata_paths`: tuple of committed metadata manifest paths.
- `source_file_records`: tuple of JSON-serializable records with path, role,
  source URL where allowed, size, and SHA-256 checksum when a concrete local
  file exists.
- `license`: source/license note from the D-004/D-003 register rows.
- `notes`: optional JSON-serializable metadata.

`WeatherMember`:

- `member_id`: unique weather-member identity within the source library.
- `shared_weather_driver_id`: stable whole-realization identity stored by HP
  and PV outputs to prove common-driver use.
- `provenance`: `WeatherProvenance`.
- `timestamps_utc`: timezone-aware UTC timestamps.
- `timestamps_local`: timezone-aware local timestamps for the same instants.
- `local_timezone`: expected local timezone, default `Europe/Amsterdam`.
- `temperature_c`: one-dimensional ambient temperature in degrees Celsius.
- `ghi_w_per_m2`: one-dimensional global horizontal irradiance in W/m2.
- `pv_weather_fields`: optional mapping of additional one-dimensional PV
  weather channels, for example `dni_w_per_m2`, `dhi_w_per_m2`,
  `poa_global_w_per_m2`, or `cell_temperature_c` when supplied by an approved
  source pipeline.
- `metadata`: JSON-serializable source-selection metadata, including calendar
  ID, member-selection method, source channel names, and any data-register or
  retrieval-manifest IDs.

Derived records:

- `calendar_record()`: first/last UTC and local timestamp, timestep count,
  cadence seconds, local timezone, and local year if validated.
- `identity_record()`: member ID, shared driver ID, provenance summary,
  calendar record, required channel names, metadata, and a deterministic
  `weather_content_sha256`.
- `usage_record(component)`: identity record plus consuming component label
  such as `hp` or `pv`. HP and PV profile builders should persist this record.

## Planned Invariants

- `member_id`, `shared_weather_driver_id`, and provenance `source` are
  non-empty.
- UTC and local timestamp vectors are non-empty, have the same length, are
  timezone-aware, represent the same instants, are strictly chronological, and
  have one constant cadence.
- Canonical annual members used for HP/PV integration must match a complete
  15-minute Europe/Amsterdam local calendar. For 2025 this is 35,040 steps;
  leap years are accepted only through the generated canonical calendar.
- `temperature_c`, `ghi_w_per_m2`, and every `pv_weather_fields` array are
  one-dimensional, finite, immutable after validation, and length-aligned to
  the timestamp vectors.
- Irradiance fields are non-negative. Temperature fields may be negative but
  must be finite.
- `shared_weather_driver_id` is independent of HP/PV model configuration and
  must not change across HP and PV consumers for the same realization.
- `weather_content_sha256` is computed from canonical UTC timestamps,
  temperature, GHI, sorted optional PV weather fields, and provenance/metadata
  identity fields. It is used for audit comparison, not as a scientific result.
- PVGIS typical-year references may be represented only as calibration or
  validation references, never as realized `WeatherMember` paths unless the PI
  signs a later D-004 amendment.
- No timestep shuffling, calendar truncation, or separate HP/PV weather
  sampling is allowed under ALEA-001.

## Planned Tests

`tests/test_weather_model.py` should cover:

- canonical 15-minute Europe/Amsterdam calendar generation, including DST and
  leap-year timestep counts;
- acceptance of a valid paired weather member with UTC/local timestamp pairs,
  temperature, GHI, optional PV fields, provenance, metadata, and stable
  identity/content records;
- rejection of naive timestamps, UTC/local mismatches, duplicate or
  non-chronological timestamps, irregular cadence, missing timesteps, array
  length mismatches, non-finite temperature/irradiance, and negative irradiance;
- deterministic equality of `identity_record()` and `weather_content_sha256`
  when HP and PV consume the same object;
- failure of a helper such as `assert_same_weather_realization(hp_record,
  pv_record)` when either member ID, shared driver ID, calendar record, or
  content checksum differs;
- rejection or explicit non-realization marking for PVGIS typical-year
  reference payloads;
- JSON serializability of provenance, metadata, calendar records, and usage
  records.

Integration migration tests after shared-weather Q-8 should cover:

- `src.pv_model` imports `WeatherMember` from `src.weather_model` and no longer
  owns a separate class;
- `src.hp_model` imports the same `WeatherMember` class and records
  `shared_weather_driver_id` and the shared usage record in `HeatPumpProfile`;
- a synthetic HP/PV fixture produces matching weather usage records from one
  weather member;
- mismatched HP/PV weather identities fail before any net-load integration.

## Blocker

The neutral implementation path is currently blocked by OWN-001. Running

```powershell
.\scripts\task.ps1 ownership -Paths src/weather_model.py,tests/test_weather_model.py
```

on the previous stacked branch failed because both paths were unassigned. The
current `origin/main` ownership policy still does not assign those neutral
paths to Agent C. Implementation should resume only after shared-weather Q-8 is
resolved by a maintainer-owned path-policy update or exact merged ownership
exception.

## Ownership Policy Amendment Needed

The recommended maintainer change is to assign the neutral shared contract to
Agent C:

```json
{
  "pattern": "src/weather_model.py",
  "owners": ["agent-c"]
},
{
  "pattern": "tests/test_weather_model.py",
  "owners": ["agent-c"]
}
```

An exact merged exception for only `agent-c/E2.S4-shared-weather-contract-plan`
would unblock this branch, but a durable policy rule is cleaner because the
merged PV and HP model scaffolds must converge on the same import path.

## HP/PV Compatibility Plan

1. After the ownership rule or exception is merged, Agent C implements
   `src/weather_model.py` and `tests/test_weather_model.py` on a follow-up
   branch.
2. PV code imports `WeatherMember` from `src.weather_model`; the PV-local
   member representation is removed or reduced to a compatibility alias with
   no independent identity fields.
3. HP code imports the same `WeatherMember`; the HP-local temperature-only
   representation is removed, and HP output records persist `member_id`,
   `shared_weather_driver_id`, calendar record, and `weather_content_sha256`.
4. HP and PV fixtures assert matching `usage_record()` values before any
   downstream net-load integration can consume their outputs.
5. E2.S4 and HP/PV weather integration remain scaffold/review-limited until
   concrete D-003/D-004 files, versions, checksums, and acceptance evidence
   exist. Synthetic tests prove only interface behavior.

## Suggested STATUS Update

Suggested `registers/STATUS.md` line after PI review:

```markdown
| E2.S4 PV model | C | blocked | 2/3 scaffold + shared-contract plan | Shared-weather Q-8 ownership; real-source acceptance evidence pending | #43 merged; follow-up #48 |
```

This remains blocked/review-limited until the shared weather contract is
implemented and real D-003/D-004 file checksums plus acceptance evidence exist.
