# E1.S3 Time Series And Critical Weeks

Status: complete for E1.S3 review.

## Scope

This report ingests the SimBench full-year 15-minute profiles for the primary
semi-urban MV grid under scenarios 0, 1, and 2. Scenario 0 remains the G0
primary baseline; scenarios 1 and 2 are appendix cross-checks only.

Loading follows the G0 aggregate decision-transformer definition:
`abs(sum_i S_i(t)) / sum_i S_nom_i`. For this profile-screening story,
the aggregate complex exchange is computed from SimBench absolute load P/Q
and static-generator P profiles. SimBench provides zero static-generator Q
for this grid, so no reactive generator profile is subtracted.

## Evidence

- Input config: `experiments/e1_s3_critical_weeks/runner_config.json`
- Manifest: `experiments/e1_s3_critical_weeks/custom_evidence.json`
- Report: `experiments/e1_s3_critical_weeks/reports/critical_weeks_validation.md`
- Critical-week table: `experiments/e1_s3_critical_weeks/data/critical_weeks.csv`; `experiments/e1_s3_critical_weeks/data/critical_weeks.parquet` was not written because no parquet engine is installed; `experiments/e1_s3_critical_weeks/data/critical_weeks.csv` is the version-controlled table.
- Validation plots: `experiments/e1_s3_critical_weeks/reports/critical_week_loading.png` and
  `experiments/e1_s3_critical_weeks/reports/critical_week_coverage.png`

## Extraction Rule

- Profile calendar: synthetic UTC leap year starting `2016-01-01T00:00:00Z`
- Step length: 15 minutes
- Winter months: 12, 1, 2
- Weeks are ranked by maximum aggregate loading within winter-profile rows.
- Coverage is diagnostic: it reports how many annual top-loading timesteps are
  captured after taking the first N ranked winter weeks.

## Scenario Summary

| scenario | grid_code | steps | rating_mva | annual_max_loading_pu | annual_max_timestamp | annual_top_step_is_winter | winter_week_count | top_winter_week_start | top_winter_week_max_loading_pu |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1-MV-semiurb--0-sw | 35136 | 80 | 0.159145 | 2016-01-27T17:45:00+00:00 | True | 15 | 2016-01-25T00:00:00+00:00 | 0.159145 |
| 1 | 1-MV-semiurb--1-sw | 35136 | 80 | 0.440427 | 2016-07-25T11:30:00+00:00 | False | 15 | 2015-12-28T00:00:00+00:00 | 0.359077 |
| 2 | 1-MV-semiurb--2-sw | 35136 | 80 | 0.533511 | 2016-07-25T11:30:00+00:00 | False | 15 | 2016-02-08T00:00:00+00:00 | 0.430939 |

## Top Ranked Winter Weeks

| scenario | grid_code | week_rank | week_start | week_end_exclusive | max_loading_pu | mean_loading_pu | steps_in_winter_months | top_timestamp | top_step_position |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1-MV-semiurb--0-sw | 1 | 2016-01-25T00:00:00+00:00 | 2016-02-01T00:00:00+00:00 | 0.159145 | 0.0604473 | 672 | 2016-01-27T17:45:00+00:00 | 2567 |
| 0 | 1-MV-semiurb--0-sw | 2 | 2016-01-18T00:00:00+00:00 | 2016-01-25T00:00:00+00:00 | 0.138595 | 0.0573543 | 672 | 2016-01-22T10:00:00+00:00 | 2056 |
| 0 | 1-MV-semiurb--0-sw | 3 | 2016-12-19T00:00:00+00:00 | 2016-12-26T00:00:00+00:00 | 0.136486 | 0.0444872 | 672 | 2016-12-25T17:00:00+00:00 | 34532 |
| 0 | 1-MV-semiurb--0-sw | 4 | 2016-02-15T00:00:00+00:00 | 2016-02-22T00:00:00+00:00 | 0.135066 | 0.0441081 | 672 | 2016-02-17T17:45:00+00:00 | 4583 |
| 0 | 1-MV-semiurb--0-sw | 5 | 2016-02-01T00:00:00+00:00 | 2016-02-08T00:00:00+00:00 | 0.121491 | 0.0466583 | 672 | 2016-02-04T18:30:00+00:00 | 3338 |
| 0 | 1-MV-semiurb--0-sw | 6 | 2016-01-04T00:00:00+00:00 | 2016-01-11T00:00:00+00:00 | 0.120548 | 0.034639 | 672 | 2016-01-07T09:00:00+00:00 | 612 |
| 1 | 1-MV-semiurb--1-sw | 1 | 2015-12-28T00:00:00+00:00 | 2016-01-04T00:00:00+00:00 | 0.359077 | 0.104967 | 288 | 2016-01-01T04:45:00+00:00 | 19 |
| 1 | 1-MV-semiurb--1-sw | 2 | 2016-01-04T00:00:00+00:00 | 2016-01-11T00:00:00+00:00 | 0.358566 | 0.109699 | 672 | 2016-01-06T02:30:00+00:00 | 490 |
| 1 | 1-MV-semiurb--1-sw | 3 | 2016-02-08T00:00:00+00:00 | 2016-02-15T00:00:00+00:00 | 0.354335 | 0.134677 | 672 | 2016-02-10T11:45:00+00:00 | 3887 |
| 1 | 1-MV-semiurb--1-sw | 4 | 2016-12-12T00:00:00+00:00 | 2016-12-19T00:00:00+00:00 | 0.353361 | 0.196946 | 672 | 2016-12-12T04:00:00+00:00 | 33232 |
| 1 | 1-MV-semiurb--1-sw | 5 | 2016-12-19T00:00:00+00:00 | 2016-12-26T00:00:00+00:00 | 0.352593 | 0.13151 | 672 | 2016-12-20T01:00:00+00:00 | 33988 |
| 1 | 1-MV-semiurb--1-sw | 6 | 2016-11-28T00:00:00+00:00 | 2016-12-05T00:00:00+00:00 | 0.350775 | 0.15025 | 384 | 2016-12-04T05:00:00+00:00 | 32468 |
| 2 | 1-MV-semiurb--2-sw | 1 | 2016-02-08T00:00:00+00:00 | 2016-02-15T00:00:00+00:00 | 0.430939 | 0.155955 | 672 | 2016-02-10T11:45:00+00:00 | 3887 |
| 2 | 1-MV-semiurb--2-sw | 2 | 2016-12-05T00:00:00+00:00 | 2016-12-12T00:00:00+00:00 | 0.411801 | 0.233173 | 672 | 2016-12-06T12:15:00+00:00 | 32689 |
| 2 | 1-MV-semiurb--2-sw | 3 | 2015-12-28T00:00:00+00:00 | 2016-01-04T00:00:00+00:00 | 0.407458 | 0.121263 | 288 | 2016-01-01T04:45:00+00:00 | 19 |
| 2 | 1-MV-semiurb--2-sw | 4 | 2016-12-12T00:00:00+00:00 | 2016-12-19T00:00:00+00:00 | 0.404691 | 0.226554 | 672 | 2016-12-12T12:15:00+00:00 | 33265 |
| 2 | 1-MV-semiurb--2-sw | 5 | 2016-12-19T00:00:00+00:00 | 2016-12-26T00:00:00+00:00 | 0.402428 | 0.149837 | 672 | 2016-12-20T01:00:00+00:00 | 33988 |
| 2 | 1-MV-semiurb--2-sw | 6 | 2016-01-04T00:00:00+00:00 | 2016-01-11T00:00:00+00:00 | 0.402094 | 0.124343 | 672 | 2016-01-06T02:30:00+00:00 | 490 |

## Annual Top-Step Coverage By Ranked Winter Windows

| scenario | grid_code | week_rank | top_24_coverage | top_96_coverage | top_672_coverage |
| --- | --- | --- | --- | --- | --- |
| 0 | 1-MV-semiurb--0-sw | 1 | 0.291667 | 0.166667 | 0.123512 |
| 0 | 1-MV-semiurb--0-sw | 2 | 0.5 | 0.322917 | 0.266369 |
| 0 | 1-MV-semiurb--0-sw | 3 | 0.541667 | 0.364583 | 0.285714 |
| 0 | 1-MV-semiurb--0-sw | 4 | 0.583333 | 0.395833 | 0.316964 |
| 0 | 1-MV-semiurb--0-sw | 5 | 0.583333 | 0.427083 | 0.342262 |
| 0 | 1-MV-semiurb--0-sw | 6 | 0.583333 | 0.447917 | 0.364583 |
| 1 | 1-MV-semiurb--1-sw | 1 | 0 | 0 | 0.0431548 |
| 1 | 1-MV-semiurb--1-sw | 2 | 0 | 0 | 0.0684524 |
| 1 | 1-MV-semiurb--1-sw | 3 | 0 | 0 | 0.0863095 |
| 1 | 1-MV-semiurb--1-sw | 4 | 0 | 0 | 0.114583 |
| 1 | 1-MV-semiurb--1-sw | 5 | 0 | 0 | 0.145833 |
| 1 | 1-MV-semiurb--1-sw | 6 | 0 | 0 | 0.205357 |
| 2 | 1-MV-semiurb--2-sw | 1 | 0 | 0 | 0.0267857 |
| 2 | 1-MV-semiurb--2-sw | 2 | 0 | 0 | 0.0401786 |
| 2 | 1-MV-semiurb--2-sw | 3 | 0 | 0 | 0.0654762 |
| 2 | 1-MV-semiurb--2-sw | 4 | 0 | 0 | 0.0818452 |
| 2 | 1-MV-semiurb--2-sw | 5 | 0 | 0 | 0.0922619 |
| 2 | 1-MV-semiurb--2-sw | 6 | 0 | 0 | 0.10119 |

## Validation Finding

- Scenario 0: annual peak is winter; maximum coverage across all ranked winter weeks is top 24: 58.3%, top 96: 45.8%, top 672: 42.9%.
- Scenario 1: annual peak is outside winter; maximum coverage across all ranked winter weeks is top 24: 0.0%, top 96: 0.0%, top 672: 21.7%.
- Scenario 2: annual peak is outside winter; maximum coverage across all ranked winter weeks is top 24: 0.0%, top 96: 0.0%, top 672: 14.9%.
- None of the scenario/window diagnostics reaches the 95% reference line in this SimBench-only screen. E9.S3 still has to perform the full-year screen specified in the plan before any critical-window claim is treated as validated.

## Interpretation For G1

The report exposes whether winter windows contain the annual highest-loading
steps under SimBench baseline scenarios. It does not settle G1 by itself,
does not benchmark the lower-level lightsim2grid TimeSeriesCPP path, and does
not change the G0 overload-event definition.
