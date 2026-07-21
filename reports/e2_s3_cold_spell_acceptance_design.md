# E2.S3 Cold-Spell And Paired-Weather Acceptance Design

Protocol ID: `E2-S3-COLD-SPELL-ACCEPTANCE-DESIGN`

Status: predeclared PI design packet only. D-003 remains proposed and unsigned.
This packet defines how E2.S3 should later check whether When2Heat-derived heat
pump profiles are acceptable under ALEA-001 once Q-8 shared-weather ownership is
resolved and concrete D-004 weather members exist. It does not run the check,
sign D-003, run net-load integration, run event analysis, estimate `P(E)`, or
produce manuscript results.

## Purpose

The current HP scaffold can parse D-003 When2Heat profiles, downscale hourly
average power to 15 minutes, and preserve a supplied weather identity. The open
scientific question is whether a When2Heat-derived HP profile is acceptable as
the HP component in an ALEA-001 sample when PV is driven by the same paired
weather member.

This design predeclares the future source-level acceptance check before any
integrated congestion or probability result is inspected. The check is a
component/source-use acceptance gate, not a downstream adequacy or congestion
test.

## Governing Constraints

- ALEA-001: HP and PV must consume one paired weather member per realization,
  with a common UTC/local calendar and complete temporal paths.
- Q-8: the neutral shared weather contract path remains unresolved. The planned
  target remains `src/weather_model.py` and `tests/test_weather_model.py` once
  the PI or maintainer authorizes ownership.
- D-003: When2Heat `when2heat.csv` from OPSD package `2023-07-27` remains
  proposed. Its raw file is ignored; metadata records byte size `328400976` and
  SHA-256 `f1f71790158d1de08403eea32dea7a2732050870c499938135606d9d7faac0fa`.
- D-004: the shared weather/PV source remains proposed until concrete KNMI/PVGIS
  files, checksums, and completeness checks exist.
- No isolated HP or PV source diagnostic certifies downstream congestion
  adequacy under ALEA-002.

## Inputs Required Before Running The Check

The acceptance check may run only after these prerequisites are present:

1. A shared `WeatherMember` contract approved or otherwise authorized under
   Q-8, with one implementation consumed by both HP and PV.
2. At least one concrete D-004 weather member with:
   - `member_id`;
   - `shared_weather_driver_id`;
   - source/provenance record;
   - complete chronological 15-minute `timestamps_utc`;
   - matching `timestamps_local` in `Europe/Amsterdam`;
   - finite `temperature_c`;
   - at least one finite nonnegative irradiance/PV weather field such as
     `ghi_w_per_m2`;
   - retrieval metadata paths and source-file checksums where applicable.
3. A D-003 HP build record with:
   - When2Heat package/file identity and checksum metadata;
   - selected Dutch heat-profile columns;
   - selected COP columns;
   - selected annual TWh scaling values and their proposed source boundary;
   - hourly-to-15-minute method
     `hourly_zero_order_hold_to_15min_energy_preserving`;
   - local/UTC timestamp mapping used to align the selected When2Heat year to
     the weather member.
4. A PV build record from the same `WeatherMember`, including PV configuration
   ID and PV weather fields consumed.

If any prerequisite is missing, the acceptance status is `not runnable`; D-003
must remain proposed/review-limited.

## Fields To Check

### Identity And Provenance

The HP profile and PV profile must carry matching weather usage records:

- `member_id`;
- `shared_weather_driver_id`;
- weather `source`;
- weather provenance source label and retrieval metadata paths;
- `weather_content_sha256` or equivalent deterministic content identity once
  the shared contract implements it;
- first/last UTC timestamp;
- first/last local timestamp;
- timestep count;
- cadence seconds;
- local timezone;
- consumed temperature field name;
- consumed irradiance/PV field names.

Required identity outcome:

- Pass: HP and PV records match exactly for weather identity, calendar record,
  and content identity.
- Fail: HP and PV use different `member_id`, `shared_weather_driver_id`,
  calendar, or weather-content checksum.
- Escalate: the shared contract lacks enough fields to prove common-driver use.

### Calendar And Completeness

Check the shared weather member, HP profile, and PV profile against one
canonical local-year calendar:

- all timestamps are timezone-aware;
- UTC timestamps are strictly chronological;
- local timestamps represent the same instants as UTC timestamps;
- cadence is exactly 900 seconds after HP downscaling;
- timestep count matches the canonical local year, including DST and leap-year
  handling;
- no duplicated, missing, repaired-without-metadata, or shuffled timestamps;
- HP electric, HP thermal, HP COP, temperature, and PV fields align one-to-one
  with the same timestamp vector.

Required calendar outcome:

- Pass: all arrays share the exact canonical calendar and shape.
- Fail: any mismatch, gap, duplicate, irregular step, or independent HP/PV
  timestamp axis.
- Escalate: an approved source has missing or ambiguous timestamps requiring a
  PI-approved repair rule.

### Cold-Spell Diagnostics

For each candidate weather member, compute diagnostics on the shared 15-minute
calendar:

- coldest rolling 7-day window by mean `temperature_c`;
- coldest rolling 3-day window by mean `temperature_c`;
- minimum hourly or 15-minute temperature timestamp;
- HP electric peak timestamp and value;
- HP thermal peak timestamp and value;
- lowest-COP timestamp and value for the selected HP technology;
- maximum HP electric load inside and outside the coldest 7-day window;
- maximum HP electric load inside and outside the coldest 3-day window;
- rank of the coldest 7-day window in HP electric weekly energy;
- rank of the coldest 3-day window in HP electric 3-day energy.

The primary cold-spell diagnostic should remain the rolling 7-day window because
the current scaffold implements that check and it is less sensitive to one-hour
noise. The 3-day and minimum-temperature diagnostics are secondary diagnostics
to expose short cold snaps.

### Temperature-Response Diagnostics

When2Heat profiles and COPs are already derived from OPSD reanalysis rather
than from the future D-004 weather member temperature. The check must therefore
not pretend that D-004 temperature mechanically generated the D-003 HP load.
Instead, it checks whether the aligned HP profile is directionally consistent
with the shared weather member:

- Spearman correlation between temperature and HP electric load over the winter
  season, expected to be negative for space-heating dominated profiles.
- Spearman correlation between temperature and COP, expected to be positive for
  ASHP space-heating COP columns.
- Winter share of annual HP electric energy.
- HP peak local month and season.
- Fraction of the top 1%, top 5%, and top 10% HP electric timesteps that fall
  in meteorological winter and in the coldest rolling windows.
- Side-by-side comparison of temperature, HP electric load, HP COP, and PV
  irradiance over the coldest 7-day window.

These diagnostics are evidence for source-use consistency only. They are not
event probabilities and must not be used as congestion conclusions.

## Required Plots

The future acceptance report should include these plots for each reviewed
weather member or for a predeclared representative subset if the member library
is large:

1. Full-year local-time panel with temperature, HP electric load, COP, and PV
   irradiance/PV generation, with the coldest 7-day window highlighted.
2. Zoomed coldest 7-day panel with the same fields and HP/PV shared weather
   identity printed in the caption or plot metadata.
3. Scatter plot of temperature versus HP electric load, colored by season.
4. Scatter plot of temperature versus COP for the selected HP technology.
5. Ranked weekly-energy plot showing where the coldest week sits in HP electric
   weekly-energy rank.
6. Calendar heatmap or monthly boxplot of HP electric load and temperature.

Plots must be generated from committed code and versioned source metadata. If a
plot build would scan many full years and exceed 15 minutes, the long-run notice
and checkpoint protocol applies before launch.

## Required Tables

The future acceptance report should include:

1. Weather identity table: HP and PV `member_id`, `shared_weather_driver_id`,
   weather content checksum, source/provenance, first/last timestamps, timestep
   count, cadence, and consumed weather fields.
2. D-003 source table: When2Heat file/version/checksum, selected heat-profile
   columns, selected COP columns, annual TWh scaling values, units, and
   downscaling method.
3. Calendar validation table: expected versus observed timestep count, first
   and last UTC/local timestamp, DST/leap-year status, and any timestamp repair
   metadata.
4. Cold-spell metric table: coldest 7-day and 3-day windows, mean temperatures,
   HP peak timestamps, HP max inside/outside windows, COP minimum, and peak
   inside-window flags.
5. Temperature-response table: winter correlations, seasonal HP energy shares,
   top-load overlap fractions, and diagnostic pass/fail/escalate labels.
6. Decision table: per-member and aggregate status for identity, calendar,
   cold-spell behavior, temperature response, and D-003 signoff implication.

## Predeclared Acceptance Outcomes

The PI should later choose any numerical tolerances before the first real
acceptance run. Until tolerances are signed, the executable check can classify
only structural outcomes and produce diagnostics for PI review.

Structural pass:

- HP and PV usage records prove the same weather realization through matching
  `member_id`, `shared_weather_driver_id`, calendar record, source/provenance,
  and weather content identity.
- HP, PV, temperature, and irradiance arrays align exactly to one canonical
  15-minute UTC/local calendar.
- D-003 source/version/checksum, selected columns, annual scaling, and
  downscaling method are recorded.
- The HP peak or high-load window is visibly and diagnostically associated with
  the coldest weather period under the PI-signed tolerance.
- Temperature/COP and temperature/load diagnostics are directionally consistent
  with heating behavior under the PI-signed tolerance.

Structural fail:

- HP and PV cannot be proven to use the same weather realization.
- HP or PV uses an independently sampled, truncated, repaired-without-metadata,
  or shuffled weather/calendar path.
- Required D-003 file, checksum, selected columns, scaling, or downscaling
  metadata is absent.
- The HP profile is materially decoupled from cold weather under the PI-signed
  tolerance.
- COP behavior contradicts the selected HP technology under the PI-signed
  tolerance.

Escalate for PI decision:

- D-004 temperature and D-003 When2Heat source years differ in a way that makes
  cold-spell interpretation ambiguous.
- The profile passes identity/calendar checks but has weak or mixed cold-spell
  diagnostics.
- A short cold snap is captured by 3-day/minimum-temperature diagnostics but not
  by the 7-day window.
- Country-level Dutch When2Heat profiles look directionally plausible but are
  not convincing for the local benchmark weather member.
- The shared weather contract lacks `weather_content_sha256` or equivalent
  content identity.

## Implications For D-003 Signoff

This acceptance check is necessary but not sufficient for D-003 signoff.

D-003 should remain proposed if:

- Q-8 is unresolved;
- no concrete D-004 weather member/checksum exists;
- HP/PV shared weather identity is not auditable;
- the cold-spell design has not been run on real paired weather;
- annual heat scaling or HP technology defaults remain unsigned; or
- the PI has not reviewed OPSD citation/license wording.

D-003 may be considered for PI signoff only after:

- the shared weather contract is implemented or otherwise approved;
- real D-003 and D-004 source files have concrete checksum metadata;
- the PI-signed cold-spell tolerances are recorded before inspection;
- the acceptance report is generated from committed code and source metadata;
- HP and PV records prove common-driver use for the reviewed member(s);
- calendar, cold-spell, and temperature-response diagnostics pass or have a
  signed escalation resolution; and
- the accepted source boundary states whether When2Heat supplies shape/COP
  only or also supplies annual scaling.

Even if D-003 is signed later, this check does not approve net-load integration,
event-based congestion results, `P(E)`, capacity-screen results, or manuscript
claims. Those remain governed by downstream gates and manifests.

## Suggested Future Execution Outline

1. Resolve Q-8 and migrate HP/PV to the shared weather contract.
2. Retrieve and checksum the approved D-004 weather/PV files.
3. Select the reviewed weather member(s), including at least one design-cold
   full-year member if available under ALEA-001.
4. Build HP profiles from D-003 with PI-reviewed columns, annual scaling, and
   technology/COP choices.
5. Build PV profiles from the same weather member(s).
6. Produce identity, calendar, cold-spell, temperature-response, and source
   tables plus the predeclared plots.
7. Classify each member as pass, fail, or escalate using PI-signed tolerances.
8. Bring the evidence back to the PI for D-003/D-004 source-use decisions.

## Suggested STATUS Update

`E2.S3 HP model | C | in-progress | cold-spell/paired-weather acceptance design prepared; D-003 unsigned; Q-8 shared-weather implementation and real D-004 evidence pending | PR: <this PR>`
