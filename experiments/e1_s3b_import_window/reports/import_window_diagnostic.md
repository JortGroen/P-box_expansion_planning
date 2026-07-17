# E1.S3b G0-A1 Import-Window Diagnostic

Status: complete for E1.S3b review. This is evidence for G1 only; it does
not mark G1 passed.

## Scope

This diagnostic applies the approved G0-A1 import/export split to the
SimBench full-year 15-minute scenario profiles. The apparent-power
magnitude `abs(S_net) / S_nom,agg` remains the loading quantity, while
`P_net > 0` gates import loading, `P_net < 0` gates export loading, and
`P_net = 0` belongs to neither direction.

Direction flips reset overload episode counters because the direction-gated
loading series is zero outside its direction. Export/feed-in exceedance is
reported separately and remains out of scope for the consumption-deferral
event.

## Evidence

- Input config: `experiments/e1_s3b_import_window/runner_config.json`
- Standard claim-source manifest: `experiments/e1_s3b_import_window/manifest.json`
- Retained/custom evidence: `experiments/e1_s3b_import_window/custom_evidence.json`
- Report: `experiments/e1_s3b_import_window/reports/import_window_diagnostic.md`
- Output tables: `experiments/e1_s3b_import_window/data/import_windows.csv`, `experiments/e1_s3b_import_window/data/import_window_coverage.csv`, `experiments/e1_s3b_import_window/data/import_window_proposal.csv`, `experiments/e1_s3b_import_window/data/export_direction_exceedance.csv`
- Coverage plot: `experiments/e1_s3b_import_window/reports/import_window_coverage.png`

## Adaptive Import-Window Proposal

The coverage target is 95% of the annual
top-672 import-loading steps. The proposed critical windows are
the smallest top-K annual import-ranked weeks reaching the target, plus
1 margin week.

| scenario | grid_code | annual_top_import_loading_pu | annual_top_import_timestamp | base_k_for_target | margin_weeks | selected_k_with_margin | selected_coverage | coverage_target | target_feasible | selected_window_starts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1-MV-semiurb--0-sw | 0.159145 | 2016-01-27T17:45:00+00:00 | 24 | 1 | 25 | 0.964286 | 0.95 | True | 2016-01-25T00:00:00+00:00; 2016-01-18T00:00:00+00:00; 2016-12-19T00:00:00+00:00; 2016-02-15T00:00:00+00:00; 2016-03-07T00:00:00+00:00; 2016-11-21T00:00:00+00:00; 2016-11-14T00:00:00+00:00; 2016-02-01T00:00:00+00:00; 2016-01-04T00:00:00+00:00; 2016-10-24T00:00:00+00:00; 2016-02-08T00:00:00+00:00; 2015-12-28T00:00:00+00:00; 2016-11-07T00:00:00+00:00; 2016-05-09T00:00:00+00:00; 2016-10-17T00:00:00+00:00; 2016-01-11T00:00:00+00:00; 2016-03-14T00:00:00+00:00; 2016-04-18T00:00:00+00:00; 2016-02-29T00:00:00+00:00; 2016-02-22T00:00:00+00:00; 2016-08-22T00:00:00+00:00; 2016-10-31T00:00:00+00:00; 2016-03-28T00:00:00+00:00; 2016-11-28T00:00:00+00:00; 2016-08-29T00:00:00+00:00 |
| 1 | 1-MV-semiurb--1-sw | 0.150356 | 2016-01-29T13:00:00+00:00 | 21 | 1 | 22 | 0.970238 | 0.95 | True | 2016-01-25T00:00:00+00:00; 2016-11-21T00:00:00+00:00; 2016-01-18T00:00:00+00:00; 2016-11-14T00:00:00+00:00; 2016-03-07T00:00:00+00:00; 2016-10-24T00:00:00+00:00; 2016-10-17T00:00:00+00:00; 2016-02-08T00:00:00+00:00; 2016-03-14T00:00:00+00:00; 2016-02-15T00:00:00+00:00; 2016-02-22T00:00:00+00:00; 2016-01-04T00:00:00+00:00; 2016-05-09T00:00:00+00:00; 2016-02-01T00:00:00+00:00; 2016-02-29T00:00:00+00:00; 2016-11-07T00:00:00+00:00; 2016-03-28T00:00:00+00:00; 2016-08-22T00:00:00+00:00; 2016-12-19T00:00:00+00:00; 2015-12-28T00:00:00+00:00; 2016-10-31T00:00:00+00:00; 2016-01-11T00:00:00+00:00 |
| 2 | 1-MV-semiurb--2-sw | 0.188443 | 2016-01-28T19:45:00+00:00 | 18 | 1 | 19 | 0.974702 | 0.95 | True | 2016-01-25T00:00:00+00:00; 2016-01-18T00:00:00+00:00; 2016-02-15T00:00:00+00:00; 2016-10-24T00:00:00+00:00; 2016-11-21T00:00:00+00:00; 2016-10-17T00:00:00+00:00; 2016-03-14T00:00:00+00:00; 2016-02-08T00:00:00+00:00; 2016-11-14T00:00:00+00:00; 2016-03-07T00:00:00+00:00; 2016-02-22T00:00:00+00:00; 2016-02-29T00:00:00+00:00; 2015-12-28T00:00:00+00:00; 2016-01-04T00:00:00+00:00; 2016-02-01T00:00:00+00:00; 2016-10-31T00:00:00+00:00; 2016-03-28T00:00:00+00:00; 2016-11-07T00:00:00+00:00; 2016-09-26T00:00:00+00:00 |

## Top Import-Ranked Annual Weeks

| scenario | grid_code | week_rank | week_start | week_end_exclusive | max_import_loading_pu | mean_loading_pu | steps_in_week | top_timestamp | top_step_position |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1-MV-semiurb--0-sw | 1 | 2016-01-25T00:00:00+00:00 | 2016-02-01T00:00:00+00:00 | 0.159145 | 0.0585642 | 672 | 2016-01-27T17:45:00+00:00 | 2567 |
| 0 | 1-MV-semiurb--0-sw | 2 | 2016-01-18T00:00:00+00:00 | 2016-01-25T00:00:00+00:00 | 0.138595 | 0.056215 | 672 | 2016-01-22T10:00:00+00:00 | 2056 |
| 0 | 1-MV-semiurb--0-sw | 3 | 2016-12-19T00:00:00+00:00 | 2016-12-26T00:00:00+00:00 | 0.136486 | 0.0304102 | 672 | 2016-12-25T17:00:00+00:00 | 34532 |
| 0 | 1-MV-semiurb--0-sw | 4 | 2016-02-15T00:00:00+00:00 | 2016-02-22T00:00:00+00:00 | 0.135066 | 0.0415068 | 672 | 2016-02-17T17:45:00+00:00 | 4583 |
| 0 | 1-MV-semiurb--0-sw | 5 | 2016-03-07T00:00:00+00:00 | 2016-03-14T00:00:00+00:00 | 0.132006 | 0.0327721 | 672 | 2016-03-09T18:45:00+00:00 | 6603 |
| 0 | 1-MV-semiurb--0-sw | 6 | 2016-11-21T00:00:00+00:00 | 2016-11-28T00:00:00+00:00 | 0.131316 | 0.048331 | 672 | 2016-11-22T15:00:00+00:00 | 31356 |
| 0 | 1-MV-semiurb--0-sw | 7 | 2016-11-14T00:00:00+00:00 | 2016-11-21T00:00:00+00:00 | 0.126752 | 0.0422726 | 672 | 2016-11-16T17:00:00+00:00 | 30788 |
| 0 | 1-MV-semiurb--0-sw | 8 | 2016-02-01T00:00:00+00:00 | 2016-02-08T00:00:00+00:00 | 0.121491 | 0.0442697 | 672 | 2016-02-04T18:30:00+00:00 | 3338 |
| 0 | 1-MV-semiurb--0-sw | 9 | 2016-01-04T00:00:00+00:00 | 2016-01-11T00:00:00+00:00 | 0.120548 | 0.0242086 | 672 | 2016-01-07T09:00:00+00:00 | 612 |
| 0 | 1-MV-semiurb--0-sw | 10 | 2016-10-24T00:00:00+00:00 | 2016-10-31T00:00:00+00:00 | 0.119349 | 0.0272633 | 672 | 2016-10-29T19:15:00+00:00 | 29069 |
| 1 | 1-MV-semiurb--1-sw | 1 | 2016-01-25T00:00:00+00:00 | 2016-02-01T00:00:00+00:00 | 0.150356 | 0.0546206 | 672 | 2016-01-29T13:00:00+00:00 | 2740 |
| 1 | 1-MV-semiurb--1-sw | 2 | 2016-11-21T00:00:00+00:00 | 2016-11-28T00:00:00+00:00 | 0.145294 | 0.0362392 | 672 | 2016-11-22T15:00:00+00:00 | 31356 |
| 1 | 1-MV-semiurb--1-sw | 3 | 2016-01-18T00:00:00+00:00 | 2016-01-25T00:00:00+00:00 | 0.143745 | 0.0446971 | 672 | 2016-01-21T13:45:00+00:00 | 1975 |
| 1 | 1-MV-semiurb--1-sw | 4 | 2016-11-14T00:00:00+00:00 | 2016-11-21T00:00:00+00:00 | 0.137935 | 0.035038 | 672 | 2016-11-16T16:45:00+00:00 | 30787 |
| 1 | 1-MV-semiurb--1-sw | 5 | 2016-03-07T00:00:00+00:00 | 2016-03-14T00:00:00+00:00 | 0.136821 | 0.0199307 | 672 | 2016-03-09T18:45:00+00:00 | 6603 |
| 1 | 1-MV-semiurb--1-sw | 6 | 2016-10-24T00:00:00+00:00 | 2016-10-31T00:00:00+00:00 | 0.136608 | 0.0139528 | 672 | 2016-10-29T19:15:00+00:00 | 29069 |
| 1 | 1-MV-semiurb--1-sw | 7 | 2016-10-17T00:00:00+00:00 | 2016-10-24T00:00:00+00:00 | 0.131514 | 0.0144484 | 672 | 2016-10-17T19:00:00+00:00 | 27916 |
| 1 | 1-MV-semiurb--1-sw | 8 | 2016-02-08T00:00:00+00:00 | 2016-02-15T00:00:00+00:00 | 0.129286 | 0.0225025 | 672 | 2016-02-13T19:00:00+00:00 | 4204 |
| 1 | 1-MV-semiurb--1-sw | 9 | 2016-03-14T00:00:00+00:00 | 2016-03-21T00:00:00+00:00 | 0.125903 | 0.0158329 | 672 | 2016-03-16T19:15:00+00:00 | 7277 |
| 1 | 1-MV-semiurb--1-sw | 10 | 2016-02-15T00:00:00+00:00 | 2016-02-22T00:00:00+00:00 | 0.125834 | 0.0209735 | 672 | 2016-02-17T17:45:00+00:00 | 4583 |
| 2 | 1-MV-semiurb--2-sw | 1 | 2016-01-25T00:00:00+00:00 | 2016-02-01T00:00:00+00:00 | 0.188443 | 0.0636283 | 672 | 2016-01-28T19:45:00+00:00 | 2671 |
| 2 | 1-MV-semiurb--2-sw | 2 | 2016-01-18T00:00:00+00:00 | 2016-01-25T00:00:00+00:00 | 0.168884 | 0.0493077 | 672 | 2016-01-21T13:00:00+00:00 | 1972 |
| 2 | 1-MV-semiurb--2-sw | 3 | 2016-02-15T00:00:00+00:00 | 2016-02-22T00:00:00+00:00 | 0.168396 | 0.0245971 | 672 | 2016-02-20T19:00:00+00:00 | 4876 |
| 2 | 1-MV-semiurb--2-sw | 4 | 2016-10-24T00:00:00+00:00 | 2016-10-31T00:00:00+00:00 | 0.158764 | 0.0136489 | 672 | 2016-10-29T19:15:00+00:00 | 29069 |
| 2 | 1-MV-semiurb--2-sw | 5 | 2016-11-21T00:00:00+00:00 | 2016-11-28T00:00:00+00:00 | 0.158139 | 0.0381193 | 672 | 2016-11-22T15:00:00+00:00 | 31356 |
| 2 | 1-MV-semiurb--2-sw | 6 | 2016-10-17T00:00:00+00:00 | 2016-10-24T00:00:00+00:00 | 0.156813 | 0.014115 | 672 | 2016-10-17T19:00:00+00:00 | 27916 |
| 2 | 1-MV-semiurb--2-sw | 7 | 2016-03-14T00:00:00+00:00 | 2016-03-21T00:00:00+00:00 | 0.152321 | 0.0167413 | 672 | 2016-03-16T19:15:00+00:00 | 7277 |
| 2 | 1-MV-semiurb--2-sw | 8 | 2016-02-08T00:00:00+00:00 | 2016-02-15T00:00:00+00:00 | 0.152148 | 0.0243485 | 672 | 2016-02-13T19:00:00+00:00 | 4204 |
| 2 | 1-MV-semiurb--2-sw | 9 | 2016-11-14T00:00:00+00:00 | 2016-11-21T00:00:00+00:00 | 0.148895 | 0.0394392 | 672 | 2016-11-16T16:45:00+00:00 | 30787 |
| 2 | 1-MV-semiurb--2-sw | 10 | 2016-03-07T00:00:00+00:00 | 2016-03-14T00:00:00+00:00 | 0.146817 | 0.0202751 | 672 | 2016-03-09T18:45:00+00:00 | 6603 |

## Coverage-Vs-K For Annual Top Import-Loading Steps

| scenario | grid_code | week_rank | top_672_coverage |
| --- | --- | --- | --- |
| 0 | 1-MV-semiurb--0-sw | 1 | 0.178571 |
| 0 | 1-MV-semiurb--0-sw | 2 | 0.386905 |
| 0 | 1-MV-semiurb--0-sw | 3 | 0.416667 |
| 0 | 1-MV-semiurb--0-sw | 4 | 0.46875 |
| 0 | 1-MV-semiurb--0-sw | 5 | 0.517857 |
| 0 | 1-MV-semiurb--0-sw | 6 | 0.59375 |
| 0 | 1-MV-semiurb--0-sw | 7 | 0.653274 |
| 0 | 1-MV-semiurb--0-sw | 8 | 0.697917 |
| 0 | 1-MV-semiurb--0-sw | 9 | 0.729167 |
| 0 | 1-MV-semiurb--0-sw | 10 | 0.744048 |
| 1 | 1-MV-semiurb--1-sw | 1 | 0.22619 |
| 1 | 1-MV-semiurb--1-sw | 2 | 0.296131 |
| 1 | 1-MV-semiurb--1-sw | 3 | 0.488095 |
| 1 | 1-MV-semiurb--1-sw | 4 | 0.58631 |
| 1 | 1-MV-semiurb--1-sw | 5 | 0.625 |
| 1 | 1-MV-semiurb--1-sw | 6 | 0.638393 |
| 1 | 1-MV-semiurb--1-sw | 7 | 0.666667 |
| 1 | 1-MV-semiurb--1-sw | 8 | 0.721726 |
| 1 | 1-MV-semiurb--1-sw | 9 | 0.754464 |
| 1 | 1-MV-semiurb--1-sw | 10 | 0.815476 |
| 2 | 1-MV-semiurb--2-sw | 1 | 0.220238 |
| 2 | 1-MV-semiurb--2-sw | 2 | 0.397321 |
| 2 | 1-MV-semiurb--2-sw | 3 | 0.458333 |
| 2 | 1-MV-semiurb--2-sw | 4 | 0.471726 |
| 2 | 1-MV-semiurb--2-sw | 5 | 0.534226 |
| 2 | 1-MV-semiurb--2-sw | 6 | 0.561012 |
| 2 | 1-MV-semiurb--2-sw | 7 | 0.59375 |
| 2 | 1-MV-semiurb--2-sw | 8 | 0.644345 |
| 2 | 1-MV-semiurb--2-sw | 9 | 0.760417 |
| 2 | 1-MV-semiurb--2-sw | 10 | 0.797619 |

## Export-Direction Exceedance Side Report

| scenario | grid_code | export_max_loading_pu | export_max_timestamp | export_steps_above_threshold | export_episodes | import_steps_above_threshold | import_episodes | import_steps | export_steps | zero_direction_steps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1-MV-semiurb--0-sw | 0.135013 | 2016-05-29T12:45:00+00:00 | 0 | 0 | 0 | 0 | 23333 | 11803 | 0 |
| 1 | 1-MV-semiurb--1-sw | 0.440427 | 2016-07-25T11:30:00+00:00 | 0 | 0 | 0 | 0 | 12398 | 22738 | 0 |
| 2 | 1-MV-semiurb--2-sw | 0.533511 | 2016-07-25T11:30:00+00:00 | 0 | 0 | 0 | 0 | 11105 | 24031 | 0 |

## Interpretation For G1

The adaptive windows satisfy the deterministic G0-A1 coverage target for
these SimBench profile screens where `target_feasible` is true. G1 still
needs the PI decision on compute budget and time structure; this report
does not freeze IC schemas or pass G1.
