# E2.S2 EV Calendar Mapping Decision Packet

Status: PI decision required before implementation
Machine-readable route: `data/metadata/ev_adoption/e2_s2_ev_calendar_mapping_decision_route.json`

## Decision Needed

The approved EV source libraries are complete annual ElaadNL profiles on the
2025 Europe/Amsterdam generator calendar. The primary planning layer for
integrated analysis is 2035 under G0-A4. Before Agent A can consume EV profiles
through IC-1, the PI needs to sign a deterministic rule for mapping complete
2025 EV source trajectories onto the common 2035 planning-year calendar.

This packet frames the scientific route only. It does not implement a mapping,
load profile arrays, inspect held-out batches, aggregate net load, evaluate
events, estimate `P(E)`, certify finite-library adequacy, or produce manuscript
numbers.

## Fixed Inputs

| Field | Value |
|---|---|
| source calendar year | 2025 |
| source timezone | `Europe/Amsterdam` |
| source cadence | 900 seconds |
| source timestep count | 35,040 |
| target planning year | 2035 |
| target IC-1 cadence | 900 seconds |
| source libraries | EV-004 home Set A and EV-008A public Set B candidate libraries |
| candidate artifact | `data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json` |

IC-1 requires all component outputs in one realization to share one calendar.
ALEA-001 also asks EV and baseline to retain complete temporal paths and common
weekday/season alignment. The mapping rule therefore needs to state explicitly
which temporal properties are preserved exactly and which are approximated.

## Required Provenance Fields

Every mapped EV member should later record:

- `component_id`: `ev_home` or `ev_public`;
- `library_id`: home Set A or public Set B library ID;
- `source_member_id`: `profile_<batch_seed>_<returned_profile_index:03d>`;
- `batch_seed`;
- `returned_profile_index`;
- `candidate_processed_path`;
- `candidate_processed_sha256_file`;
- `component_stream_id` from RNG-001;
- `calendar_mapping_rule_id`;
- `calendar_mapping_rule_version`;
- `source_calendar_id`, e.g. `elaad-2025-europe-amsterdam-15min`;
- `target_calendar_id`, e.g. `planning-2035-europe-amsterdam-15min`;
- `source_timestamp_index_policy`;
- `unmapped_or_repeated_source_timestep_count`;
- `dst_policy`;
- `holiday_policy`;
- `mapping_created_by_code_sha` or equivalent code identity.

These fields preserve member/seed traceability without expanding the finite
source-library adequacy question into a hidden Monte Carlo parameter.

## Option A: Ordinal Timestep Mapping

Map source timestep `i` directly to planning-year timestep `i`.

Preserves:

- complete 35,040-step source trajectory order;
- source serial dependence;
- source season and time-of-day sequence;
- one-to-one source timestep usage.

Does not preserve:

- actual weekday/weekend labels when 2025 and 2035 weekdays differ;
- exact 2035 public-holiday labels;
- compatibility with components whose behavior is explicitly keyed to 2035
  weekdays.

Checks before implementation:

- source and target calendars have exactly 35,040 timesteps;
- source index vector is exactly `0..35039`;
- mapped output timestamps equal the canonical 2035 IC-1 calendar;
- source demand values are neither sorted nor shuffled by magnitude;
- annual energy per member is unchanged by mapping;
- mapping metadata states weekday preservation is `false`.

## Option B: Weekday-Class Calendar Mapping

Map each 2035 local timestamp to a 2025 source timestamp with matching or
nearest matching season/month, local time of day, and weekday/weekend class.

Preserves:

- target 2035 weekday/weekend semantics;
- target 2035 local timestamp identity;
- local time-of-day alignment;
- closer ALEA-001 alignment with baseline and weather-dependent components if
  they use an explicit 2035 calendar.

Risks:

- source days may be repeated or skipped unless the algorithm is tightly
  specified;
- local chronological order within the original source trajectory may be broken
  at remapped day boundaries;
- DST and holiday behavior need exact policy text;
- annual energy may change if timesteps are repeated/skipped unless corrected.

Checks before implementation:

- deterministic mapping table for all 35,040 target timestamps;
- no `NaT`, duplicate target timestamp, or non-900-second target cadence;
- explicit counts of repeated and omitted source timesteps;
- weekday/weekend preservation rate reported and expected to be exact for the
  chosen class definition;
- local time-of-day preservation rate reported and expected to be exact except
  where DST policy says otherwise;
- annual-energy conservation either exact or explicitly corrected by a signed
  scaling rule;
- mapping is independent of EV demand magnitudes, congestion, and event labels.

## Option C: Source-Year Computational Calendar

Use the 2025 ElaadNL source calendar as the common computational calendar while
labeling adoption counts and grid state as the 2035 planning layer.

Preserves:

- source EV temporal dependence exactly;
- no EV remapping;
- no repeated/skipped EV source timesteps.

Risks:

- can blur the G0-A4 distinction between 2030/2025 source-generator calendars
  and the 2035 planning layer;
- requires baseline, HP, PV, and flexibility components to adopt the same
  source-year computational calendar;
- may conflict with existing IC-1 documentation that names a canonical 2035
  calendar.

Checks before implementation:

- PI-signed common-calendar convention for all components, not only EV;
- proof that all component adapters use identical 2025 timestamps;
- manifest text clearly separates `planning_year = 2035` from
  `computational_calendar_year = 2025`.

## Option D: Weather-Year Matched Calendar

Map EV profiles onto the same selected weather-member calendar used by HP/PV in
each Monte Carlo realization.

Preserves:

- exact common calendar with weather-driven HP/PV components;
- weather member calendar identity.

Risks:

- may create an unintended physical dependence between EV behavior and
  weather-year identity;
- complicates RNG-001 provenance because the same EV source member may map
  differently across weather years;
- is likely more machinery than needed before IC-1 consumes EV candidates.

Checks before implementation:

- signed rule explaining whether weather-year identity is an intended physical
  driver for EV mapping;
- mapping provenance includes weather member ID;
- common-calendar checks pass for every weather year in scope.

## Agent C Recommendation

Agent C recommends that the PI choose between Option A and Option B before any
mapping code is implemented.

Option A is the smallest deterministic bridge and best preserves complete EV
member order. It is easiest to audit, but it knowingly sacrifices exact
weekday/weekend alignment between EV and 2035 baseline/weather components.

Option B better satisfies the ALEA-001 language about common weekday/weekend
alignment, but only if the PI signs a precise algorithm for repeated/skipped
source days, DST, holidays, and energy conservation. It should not be improvised
inside an implementation PR.

Option C should be used only if the PI wants the whole IC-1 stack to use a
source-year computational calendar. Option D should remain an escalation unless
the PI wants weather-year identity to drive EV calendar mapping.

## Proposed Decision Text

`EV-CAL-001`: Before IC-1 aggregation, map each complete EV candidate source
member from the 2025 ElaadNL Europe/Amsterdam source calendar to the common
planning calendar using [PI-selected deterministic rule: Option A/B/C/D plus
exact parameters]. The mapping must preserve 35,040 15-minute target timesteps,
produce no `NaT`, keep selected member IDs traceable through component ID,
library ID, batch seed, returned profile index, RNG-001 stream identity, and
mapping-rule ID, and must not inspect congestion, event, held-out adequacy, or
manuscript-result outputs when choosing or validating the rule.

## Minimum Test Plan Before Implementation

Any implementation PR should include tests for:

- source calendar validation: timezone-aware Europe/Amsterdam/UTC metadata,
  35,040 timesteps, 900-second cadence;
- target calendar validation: canonical 2035 calendar, 35,040 timesteps,
  900-second cadence, no `NaT`;
- deterministic mapping table generation from rule ID and parameters;
- source index bounds and integer dtype;
- no demand-value sorting, percentile compression, or event-aware selection;
- member provenance fields for component, library, seed, returned index,
  processed checksum, RNG stream, and mapping rule;
- annual-energy preservation or signed energy-correction metadata;
- explicit weekday/weekend, season/month, time-of-day, DST, and holiday
  preservation diagnostics;
- rejection when the mapping rule is unsigned or absent;
- rejection of held-out or quarantined profile partitions.

## Stop Condition

Implementation of any calendar mapping rule should stop until `EV-CAL-001` or
an equivalent PI decision is approved.
