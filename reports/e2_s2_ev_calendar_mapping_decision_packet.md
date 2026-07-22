# E2.S2 EV Calendar Mapping Decision Packet

Status: PI decision required before implementation

## Decision Needed

The approved EV source libraries are complete annual ElaadNL profiles on the
2025 Europe/Amsterdam generator calendar. The primary planning layer for
integrated analysis is 2035 under G0-A4. Before Agent A can consume EV profiles
through IC-1, the PI needs to sign a deterministic rule for mapping complete
2025 EV source trajectories onto the common 2035 planning-year calendar.

This packet frames the choice only. It does not implement a mapping, load
profile arrays, inspect held-out batches, aggregate net load, evaluate events,
estimate `P(E)`, or produce manuscript numbers.

## Fixed Inputs

- Source calendar year: 2025.
- Source timezone: `Europe/Amsterdam`.
- Source cadence: 15 minutes.
- Source timestep count: 35,040.
- Source profiles: complete annual home/public candidate members generated
  under EV-004 and EV-008A.
- Target planning year: 2035.
- IC-1 requirement: all components must share exactly one common 15-minute
  calendar.

## Option 1: Ordinal Timestep Mapping

Map source timestep `i` directly to planning-year timestep `i`.

Implications:

- Preserves annual sequence order, seasonality, time-of-day order, and complete
  source trajectories.
- Does not preserve weekday/weekend labels when 2025 and 2035 weekdays differ.
- Simple to audit and deterministic.
- May weaken ALEA-001 weekday/weekend alignment if baseline, HP, and PV are
  keyed to actual 2035 weekdays.

## Option 2: Weekday-Class Calendar Mapping

Map each 2035 local timestamp to a 2025 source timestamp with matching or
nearest matching month/season, time of day, and weekday/weekend class.

Implications:

- Better preserves weekday/weekend semantics for IC-1 alignment.
- Can introduce local reordering or repeated/skipped source days unless the rule
  is carefully specified.
- Requires exact tie-breaking, holiday/leap-day handling, and DST behavior.
- Needs tests proving complete 35,040-step output, deterministic behavior, and
  no hidden event screening.

## Option 3: Source-Year Calendar As Common Calendar

Use the 2025 source calendar as the common computational calendar while labeling
adoption counts and grid state as the 2035 planning layer.

Implications:

- Avoids remapping EV trajectories.
- Keeps source temporal dependence exactly as generated.
- Risks confusing source calendar year with planning year unless all components
  agree to the same convention.
- May be incompatible with baseline, HP, and PV components if they are already
  constructed on an explicit 2035 calendar.

## Agent C Recommendation

Agent C recommends PI review before choosing between Option 1 and Option 2.
Option 1 is the smallest deterministic bridge and preserves complete EV annual
member order. Option 2 is scientifically attractive if weekday/weekend alignment
with baseline and weather-driven components is considered more important, but
it needs a precise signed algorithm before implementation.

Option 3 should be used only if the whole IC-1 common-calendar convention is
explicitly defined around a source-year computational calendar, because it can
otherwise blur the G0-A4 distinction between source-generator year and planning
year.

## Proposed Decision Text

`EV-CAL-001`: Before IC-1 aggregation, map each complete EV candidate source
member from the 2025 ElaadNL Europe/Amsterdam source calendar to the common 2035
planning calendar using [PI-selected deterministic rule]. The mapping must
preserve 35,040 15-minute timesteps, produce no NaT/nonfinite timestamps, keep
selected member IDs traceable, and must not inspect congestion, event, held-out
adequacy, or manuscript-result outputs when choosing or validating the rule.

## Stop Condition

Implementation of any calendar mapping rule should stop until `EV-CAL-001` or
an equivalent PI decision is approved.

