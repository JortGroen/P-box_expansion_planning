from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.fuzzy import TrapezoidalFuzzyNumber
from src.pbox_crosscheck import (
    BootstrapProbabilityInterval,
    FiniteHybridState,
    GaussianCrosscheckAlphaRecord,
    GaussianCrosscheckManifest,
    GaussianToyParameters,
    HybridReproductionReadiness,
    OutputErrorToyTrajectory,
    assert_hybrid_reproduction_ready_payload,
    assert_math_core_trust_certificate_payload,
    bootstrap_probability_interval,
    build_gaussian_crosscheck_manifest,
    build_math_core_trust_certificate_manifest,
    estimate_gaussian_toy_pbox,
    finite_hybrid_bounds,
    gaussian_closed_form_bounds,
    gaussian_tail_probability,
    monotonicity_sweep_from_events,
    output_error_alpha_crosscheck_records,
)
from src.pbox_error import OutputErrorProtocolConfig


def _gaussian_fixture() -> tuple[TrapezoidalFuzzyNumber, list[float], GaussianToyParameters]:
    return (
        TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0),
        [0.0, 0.5, 1.0],
        GaussianToyParameters(mu_0=1.0, beta=0.4, sigma=0.2, threshold=1.1),
    )


def test_gaussian_crosscheck_closed_form_is_monotone_and_endpoint_bounded() -> None:
    fuzzy, alpha_grid, params = _gaussian_fixture()

    bounds = gaussian_closed_form_bounds(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        params=params,
    )

    assert list(bounds) == alpha_grid
    for alpha, (lower, upper) in bounds.items():
        cut = fuzzy.alpha_cut(alpha)
        assert lower <= upper
        assert lower == pytest.approx(gaussian_tail_probability(rho=cut.upper, params=params))
        assert upper == pytest.approx(gaussian_tail_probability(rho=cut.lower, params=params))

    assert bounds[0.0][0] <= bounds[0.5][0] <= bounds[1.0][0]
    assert bounds[1.0][1] <= bounds[0.5][1] <= bounds[0.0][1]


def test_gaussian_crosscheck_known_synthetic_tail_values_are_stable() -> None:
    _, _, params = _gaussian_fixture()

    assert gaussian_tail_probability(rho=0.0, params=params) == pytest.approx(
        0.3085375387259869
    )
    assert gaussian_tail_probability(rho=1.0, params=params) == pytest.approx(
        0.006209665325776159
    )


def test_gaussian_crosscheck_exercises_vertex_pbox_against_closed_form() -> None:
    fuzzy, alpha_grid, params = _gaussian_fixture()
    expected = gaussian_closed_form_bounds(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        params=params,
    )

    pbox = estimate_gaussian_toy_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        params=params,
        sample_count=4096,
        root_seed=20260721,
    )

    for alpha, result in pbox.items():
        expected_lower, expected_upper = expected[alpha]
        assert abs(result.lower.probability - expected_lower) < 0.01
        assert abs(result.upper.probability - expected_upper) < 0.01
        assert result.lower.probability <= result.upper.probability


def test_gaussian_crosscheck_replays_same_root_seed_deterministically() -> None:
    fuzzy, alpha_grid, params = _gaussian_fixture()

    first = estimate_gaussian_toy_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        params=params,
        sample_count=512,
        root_seed=20260722,
    )
    second = estimate_gaussian_toy_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        params=params,
        sample_count=512,
        root_seed=20260722,
    )

    assert first.keys() == second.keys()
    for alpha in alpha_grid:
        assert first[alpha].lower == second[alpha].lower
        assert first[alpha].upper == second[alpha].upper


def test_gaussian_crosscheck_manifest_is_json_stable_and_tolerance_guarded() -> None:
    fuzzy, alpha_grid, params = _gaussian_fixture()

    manifest = build_gaussian_crosscheck_manifest(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        params=params,
        sample_count=4096,
        root_seed=20260721,
        tolerance=0.01,
    )
    payload = manifest.to_mapping()

    assert isinstance(manifest, GaussianCrosscheckManifest)
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert payload["crosscheck_id"] == "E5.S4-gaussian-analytic-v1"
    assert payload["passed"] is True
    assert payload["max_absolute_error"] <= payload["tolerance"]
    assert payload["probability_reporting"] == "alpha-indexed-lower-upper-only"
    assert payload["g3_claim"] == "none-pre-g3-synthetic"
    assert payload["alpha_rows_nested"] is True
    assert payload["closed_form_within_confidence_intervals"] is True
    assert payload["confidence_interval_reporting"] == "separate-lower-upper-ci"
    assert "defuzzified_probability" not in json.dumps(payload)
    assert [row["alpha"] for row in payload["alpha_rows"]] == alpha_grid
    for row in payload["alpha_rows"]:
        assert row["closed_form_lower_in_ci"] is True
        assert row["closed_form_upper_in_ci"] is True
        assert row["estimated_lower_ci_lower"] <= row["estimated_lower"]
        assert row["estimated_upper"] <= row["estimated_upper_ci_upper"]

def test_gaussian_crosscheck_manifest_can_fail_closed_without_changing_oracle() -> None:
    fuzzy, alpha_grid, params = _gaussian_fixture()

    manifest = build_gaussian_crosscheck_manifest(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        params=params,
        sample_count=64,
        root_seed=20260721,
        tolerance=1e-6,
    )

    assert manifest.passed is False
    assert manifest.max_absolute_error > manifest.tolerance


def test_gaussian_crosscheck_manifest_rejects_bad_metadata() -> None:
    fuzzy, alpha_grid, params = _gaussian_fixture()
    valid = build_gaussian_crosscheck_manifest(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        params=params,
        sample_count=128,
        root_seed=20260721,
    )

    with pytest.raises(ValueError, match="synthetic-only"):
        GaussianCrosscheckManifest(
            rows=valid.rows,
            tolerance=0.01,
            sample_count=128,
            root_seed=20260721,
            use_status="paper-facing",
        )


def test_gaussian_crosscheck_alpha_record_rejects_inconsistent_ci_flag() -> None:
    with pytest.raises(ValueError, match="closed_form_lower_in_ci"):
        GaussianCrosscheckAlphaRecord(
            alpha=0.0,
            rho_lower=0.0,
            rho_upper=1.0,
            closed_form_lower=0.2,
            closed_form_upper=0.8,
            estimated_lower=0.25,
            estimated_upper=0.75,
            estimated_lower_ci_lower=0.1,
            estimated_lower_ci_upper=0.3,
            estimated_upper_ci_lower=0.7,
            estimated_upper_ci_upper=0.9,
            closed_form_lower_in_ci=False,
            closed_form_upper_in_ci=True,
            absolute_error_lower=0.05,
            absolute_error_upper=0.05,
        )


def test_gaussian_crosscheck_manifest_detects_non_nested_alpha_rows() -> None:
    row_0 = GaussianCrosscheckAlphaRecord(
        alpha=0.0,
        rho_lower=0.0,
        rho_upper=1.0,
        closed_form_lower=0.2,
        closed_form_upper=0.8,
        estimated_lower=0.2,
        estimated_upper=0.8,
        estimated_lower_ci_lower=0.1,
        estimated_lower_ci_upper=0.3,
        estimated_upper_ci_lower=0.7,
        estimated_upper_ci_upper=0.9,
        closed_form_lower_in_ci=True,
        closed_form_upper_in_ci=True,
        absolute_error_lower=0.0,
        absolute_error_upper=0.0,
    )
    row_1 = GaussianCrosscheckAlphaRecord(
        alpha=0.5,
        rho_lower=0.25,
        rho_upper=0.75,
        closed_form_lower=0.1,
        closed_form_upper=0.9,
        estimated_lower=0.1,
        estimated_upper=0.9,
        estimated_lower_ci_lower=0.05,
        estimated_lower_ci_upper=0.15,
        estimated_upper_ci_lower=0.85,
        estimated_upper_ci_upper=0.95,
        closed_form_lower_in_ci=True,
        closed_form_upper_in_ci=True,
        absolute_error_lower=0.0,
        absolute_error_upper=0.0,
    )

    manifest = GaussianCrosscheckManifest(
        rows=(row_0, row_1),
        tolerance=0.01,
        sample_count=10,
        root_seed=0,
    )

    assert manifest.alpha_rows_nested is False
    assert manifest.passed is False


def test_hybrid_reproduction_readiness_blocks_until_source_is_verified() -> None:
    readiness = HybridReproductionReadiness(
        source_id="baudrit-style-source-pending",
        source_status="pending-source",
        published_example_id="published-example-pending",
        example_reproduced=False,
        qualitative_behavior_checked=True,
        blockers=("verified published example source is not registered",),
    )
    payload = readiness.to_mapping()

    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert payload["ready"] is False
    with pytest.raises(RuntimeError, match="not ready"):
        assert_hybrid_reproduction_ready_payload(payload)


def test_hybrid_reproduction_readiness_accepts_verified_reproduction_packet() -> None:
    readiness = HybridReproductionReadiness(
        source_id="D-verified-hybrid-example",
        source_status="verified-approved",
        published_example_id="example-1",
        example_reproduced=True,
        qualitative_behavior_checked=True,
        blockers=(),
        provenance_ids=(
            "source:D-verified-hybrid-example",
            "published-example:example-4-2",
            "reproduction-evidence:reports/e5_s4_baudrit_reproduction.json",
        ),
    )

    assert readiness.ready is True
    assert_hybrid_reproduction_ready_payload(readiness.to_mapping())


def test_hybrid_reproduction_readiness_rejects_ready_without_exact_provenance_roles() -> None:
    with pytest.raises(ValueError, match="missing provenance roles"):
        HybridReproductionReadiness(
            source_id="D-verified-hybrid-example",
            source_status="verified-approved",
            published_example_id="example-1",
            example_reproduced=True,
            qualitative_behavior_checked=True,
            blockers=(),
            provenance_ids=(
                "source:D-verified-hybrid-example",
                "published-example:example-4-2",
            ),
        )

    with pytest.raises(ValueError, match="unsigned placeholder"):
        HybridReproductionReadiness(
            source_id="D-verified-hybrid-example",
            source_status="verified-approved",
            published_example_id="example-1",
            example_reproduced=True,
            qualitative_behavior_checked=True,
            blockers=(),
            provenance_ids=(
                "source:D-verified-hybrid-example",
                "published-example:pending-example",
                "reproduction-evidence:reports/e5_s4_baudrit_reproduction.json",
            ),
        )


def test_hybrid_reproduction_readiness_rejects_serialized_tampering() -> None:
    readiness = HybridReproductionReadiness(
        source_id="baudrit-style-source-pending",
        source_status="pending-source",
        published_example_id="published-example-pending",
        example_reproduced=False,
        qualitative_behavior_checked=True,
        blockers=("verified published example source is not registered",),
    )
    payload = readiness.to_mapping()

    relabeled = dict(payload)
    relabeled["use_status"] = "paper-facing"
    with pytest.raises(ValueError, match="source-readiness"):
        assert_hybrid_reproduction_ready_payload(relabeled)

    collapsed = dict(payload)
    collapsed["defuzzified_probability"] = 0.5
    with pytest.raises(ValueError, match="defuzzified"):
        assert_hybrid_reproduction_ready_payload(collapsed)

    false_ready = dict(payload)
    false_ready["ready"] = True
    with pytest.raises(ValueError, match="ready flag"):
        assert_hybrid_reproduction_ready_payload(false_ready)


def test_hybrid_reproduction_readiness_rejects_ready_flag_tamper_on_verified_packet() -> None:
    readiness = HybridReproductionReadiness(
        source_id="D-verified-hybrid-example",
        source_status="verified-approved",
        published_example_id="example-1",
        example_reproduced=True,
        qualitative_behavior_checked=True,
        blockers=(),
        provenance_ids=(
            "source:D-verified-hybrid-example",
            "published-example:example-4-2",
            "reproduction-evidence:reports/e5_s4_baudrit_reproduction.json",
        ),
    )
    tampered = readiness.to_mapping()
    tampered["ready"] = False

    with pytest.raises(ValueError, match="ready flag"):
        assert_hybrid_reproduction_ready_payload(tampered)


def test_math_core_trust_certificate_records_green_analytic_and_blocked_source() -> None:
    fuzzy, alpha_grid, params = _gaussian_fixture()
    analytic = build_gaussian_crosscheck_manifest(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        params=params,
        sample_count=4096,
        root_seed=20260721,
        tolerance=0.01,
    )
    hybrid = HybridReproductionReadiness(
        source_id="baudrit-style-source-pending",
        source_status="pending-source",
        published_example_id="published-example-pending",
        example_reproduced=False,
        qualitative_behavior_checked=True,
        blockers=("verified published example source is not registered",),
    )

    certificate = build_math_core_trust_certificate_manifest(
        analytic_gaussian=analytic,
        hybrid_reproduction=hybrid,
    )
    payload = certificate.to_mapping()

    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert payload["protocol"] == "e5s4-math-core-trust-certificate-v1"
    assert payload["ready_for_paper_math_claims"] is False
    assert (
        "analytic Gaussian p-box cross-check within tolerance"
        in payload["green_checks"]
    )
    assert "alpha-indexed lower/upper rows are nested" in payload["green_checks"]
    assert "no scalar defuzzified probability fields" in payload["green_checks"]
    assert (
        "verified published example source is not registered"
        in payload["paper_facing_blockers"]
    )
    assert (
        "G3 remains pending for any paper-facing vertex-shortcut claim"
        in payload["paper_facing_blockers"]
    )
    assert "defuzzified_probability" not in json.dumps(payload)
    assert_math_core_trust_certificate_payload(payload)


def test_math_core_trust_certificate_rejects_ready_and_defuzzified_tampering() -> None:
    fuzzy, alpha_grid, params = _gaussian_fixture()
    analytic = build_gaussian_crosscheck_manifest(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        params=params,
        sample_count=4096,
        root_seed=20260721,
        tolerance=0.01,
    )
    hybrid = HybridReproductionReadiness(
        source_id="baudrit-style-source-pending",
        source_status="pending-source",
        published_example_id="published-example-pending",
        example_reproduced=False,
        qualitative_behavior_checked=True,
        blockers=("verified published example source is not registered",),
    )
    payload = build_math_core_trust_certificate_manifest(
        analytic_gaussian=analytic,
        hybrid_reproduction=hybrid,
    ).to_mapping()

    false_ready = dict(payload)
    false_ready["ready_for_paper_math_claims"] = True
    with pytest.raises(ValueError, match="blocker state"):
        assert_math_core_trust_certificate_payload(false_ready)

    collapsed = dict(payload)
    collapsed["analytic_gaussian"] = dict(payload["analytic_gaussian"])
    collapsed["analytic_gaussian"]["defuzzified_probability"] = 0.5
    with pytest.raises(ValueError, match="collapsed field"):
        assert_math_core_trust_certificate_payload(collapsed)

    relabeled = dict(payload)
    relabeled["use_status"] = "paper-facing"
    with pytest.raises(ValueError, match="synthetic-only"):
        assert_math_core_trust_certificate_payload(relabeled)



def test_math_core_trust_certificate_recomputes_serialized_invariants() -> None:
    fuzzy, alpha_grid, params = _gaussian_fixture()
    analytic = build_gaussian_crosscheck_manifest(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        params=params,
        sample_count=4096,
        root_seed=20260721,
        tolerance=0.01,
    )
    hybrid = HybridReproductionReadiness(
        source_id="baudrit-style-source-pending",
        source_status="pending-source",
        published_example_id="published-example-pending",
        example_reproduced=False,
        qualitative_behavior_checked=True,
        blockers=("verified published example source is not registered",),
    )
    payload = build_math_core_trust_certificate_manifest(
        analytic_gaussian=analytic,
        hybrid_reproduction=hybrid,
    ).to_mapping()

    analytic_tamper = dict(payload)
    analytic_payload = dict(payload["analytic_gaussian"])
    rows = [dict(row) for row in analytic_payload["alpha_rows"]]
    rows[0]["absolute_error_lower"] = 0.5
    analytic_payload["alpha_rows"] = rows
    analytic_tamper["analytic_gaussian"] = analytic_payload
    with pytest.raises(ValueError, match="analytic_gaussian"):
        assert_math_core_trust_certificate_payload(analytic_tamper)

    green_tamper = dict(payload)
    green_tamper["green_checks"] = ["no scalar defuzzified probability fields"]
    with pytest.raises(ValueError, match="green_checks"):
        assert_math_core_trust_certificate_payload(green_tamper)

    blocker_tamper = dict(payload)
    blocker_tamper["paper_facing_blockers"] = [
        "verified published example source is not registered"
    ]
    with pytest.raises(ValueError, match="paper_facing_blockers"):
        assert_math_core_trust_certificate_payload(blocker_tamper)

    non_claim_tamper = dict(payload)
    non_claim_tamper["synthetic_non_claims"] = ["no real trajectories"]
    with pytest.raises(ValueError, match="synthetic_non_claims"):
        assert_math_core_trust_certificate_payload(non_claim_tamper)

def test_finite_hybrid_crosscheck_matches_hand_computed_probability_bounds() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.2, 0.4, 0.6)
    states = [
        FiniteHybridState(value=0.2, probability=0.25),
        FiniteHybridState(value=0.7, probability=0.25),
        FiniteHybridState(value=1.05, probability=0.5),
    ]

    bounds = finite_hybrid_bounds(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0, 0.5, 1.0],
        states=states,
        threshold=0.5,
    )

    assert bounds[0.0].lower_probability == pytest.approx(0.0)
    assert bounds[0.0].upper_probability == pytest.approx(0.75)
    assert bounds[0.5].lower_probability == pytest.approx(0.5)
    assert bounds[0.5].upper_probability == pytest.approx(0.75)
    assert bounds[1.0].lower_probability == pytest.approx(0.5)
    assert bounds[1.0].upper_probability == pytest.approx(0.5)
    assert bounds[0.0].lower_probability <= bounds[0.5].lower_probability <= bounds[1.0].lower_probability
    assert bounds[1.0].upper_probability <= bounds[0.5].upper_probability <= bounds[0.0].upper_probability


def test_finite_hybrid_crosscheck_keeps_alpha_indexed_bounds_only() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.2, 0.4, 0.6)
    states = [
        FiniteHybridState(value=0.2, probability=0.25),
        FiniteHybridState(value=0.7, probability=0.25),
        FiniteHybridState(value=1.05, probability=0.5),
    ]

    bounds = finite_hybrid_bounds(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0, 1.0],
        states=states,
        threshold=0.5,
    )

    assert set(bounds) == {0.0, 1.0}
    assert all(hasattr(result, "lower_probability") for result in bounds.values())
    assert all(hasattr(result, "upper_probability") for result in bounds.values())
    assert all(not hasattr(result, "defuzzified_probability") for result in bounds.values())

def _output_error_config() -> OutputErrorProtocolConfig:
    return OutputErrorProtocolConfig.from_mapping(
        {
            "epsilon_grid": 0.0,
            "epsilon_tier1_minus": 0.1,
            "epsilon_tier1_plus": 0.1,
            "threshold_pu": 1.0,
            "min_consecutive_steps": 4,
            "timestep_seconds": 900,
            "envelope_source": "synthetic-crosscheck-envelope",
            "grid_error_source": "synthetic-grid-placeholder",
            "tier1_error_source": "synthetic-tier1-placeholder",
            "capacity_denominator_provenance": "synthetic-capacity-placeholder",
        }
    )


def _output_error_samples() -> list[OutputErrorToyTrajectory]:
    return [
        OutputErrorToyTrajectory("sample-0", (0.8, 0.8, 0.8, 0.8), (1, 1, 1, 1)),
        OutputErrorToyTrajectory("sample-1", (0.95, 0.95, 0.95, 0.95), (1, 1, 1, 1)),
        OutputErrorToyTrajectory("sample-2", (1.2, 1.2, 1.2, 1.2), (1, 1, 1, 1)),
        OutputErrorToyTrajectory("sample-3", (1.2, 1.2, 1.2, 1.2), (1, 1, -1, 1)),
    ]


def test_output_error_crosscheck_matches_hand_computed_endpoint_event_counts() -> None:
    config = _output_error_config()
    samples = _output_error_samples()
    raw_middle = samples[1].to_loading_trajectory(
        threshold_pu=config.threshold_pu,
        min_consecutive_steps=config.min_consecutive_steps,
    )

    records = output_error_alpha_crosscheck_records(
        samples_by_alpha={0.0: samples},
        config=config,
    )

    record = records[0.0]
    assert raw_middle.overload is False
    assert record.lower_successes == 1
    assert record.upper_successes == 2
    assert record.sample_count == 4
    assert record.manifest_record["event_count_bounds"] == {
        "lower_successes": 1,
        "upper_successes": 2,
        "sample_count": 4,
    }
    assert [
        (event["lower_event"], event["upper_event"], event["upper_longest_run_steps"])
        for event in record.manifest_record["sample_endpoint_events"]
    ] == [
        (False, False, 0),
        (False, True, 4),
        (True, True, 4),
        (False, False, 2),
    ]


def test_output_error_crosscheck_preserves_alpha_sample_identity_and_metadata() -> None:
    config = _output_error_config()
    records = output_error_alpha_crosscheck_records(
        samples_by_alpha={
            0.5: _output_error_samples(),
            0.0: _output_error_samples(),
        },
        config=config,
    )

    assert list(records) == [0.0, 0.5]
    assert records[0.0].sample_ids == records[0.5].sample_ids
    assert records[0.0].manifest_record["probability_widening"] == "forbidden"
    assert records[0.0].manifest_record["config"]["event_semantics"]["direction_gate"] == (
        "unwidened_p_net_import_mask"
    )
    assert all(not hasattr(result, "defuzzified_probability") for result in records.values())
    assert [
        event["sample_index"] for event in records[0.5].manifest_record["sample_endpoint_events"]
    ] == [0, 1, 2, 3]


def test_output_error_crosscheck_rejects_broken_crn_identity_and_invalid_toys() -> None:
    config = _output_error_config()

    with pytest.raises(ValueError, match="same ordered sample_id sequence"):
        output_error_alpha_crosscheck_records(
            samples_by_alpha={
                0.0: _output_error_samples(),
                1.0: [
                    OutputErrorToyTrajectory(
                        "sample-1",
                        (0.8, 0.8, 0.8, 0.8),
                        (1, 1, 1, 1),
                    ),
                    *_output_error_samples()[1:],
                ],
            },
            config=config,
        )

    with pytest.raises(ValueError, match="p_signs"):
        OutputErrorToyTrajectory("bad-sign", (1.0,), (2,))


def _bootstrap_resamples() -> list[list[int]]:
    return [
        [0, 1, 2, 3],
        [0, 0, 1, 1],
        [2, 2, 3, 3],
    ]


def test_bootstrap_probability_interval_uses_hand_computable_rank_endpoints() -> None:
    interval = bootstrap_probability_interval(
        [True, False, True, False],
        resample_indices=_bootstrap_resamples(),
        confidence_level=0.5,
    )

    assert isinstance(interval, BootstrapProbabilityInterval)
    assert interval.probability == pytest.approx(0.5)
    assert interval.ci_lower == pytest.approx(0.5)
    assert interval.ci_upper == pytest.approx(0.5)
    assert interval.replicate_count == 3


def test_monotonicity_sweep_reports_no_violation_for_synthetic_decreasing_events() -> None:
    sweep = monotonicity_sweep_from_events(
        events_by_rho={
            1.0: [True, False, False, False],
            0.0: [True, True, True, False],
            0.5: [True, True, False, False],
        },
        resample_indices=_bootstrap_resamples(),
        confidence_level=0.5,
    )

    assert [point.rho for point in sweep.points] == [0.0, 0.5, 1.0]
    assert [point.successes for point in sweep.points] == [3, 2, 1]
    assert [point.probability for point in sweep.points] == [0.75, 0.5, 0.25]
    assert sweep.expected_direction == "nonincreasing"
    assert sweep.violations == ()
    assert all(not hasattr(point, "g3_verdict") for point in sweep.points)


def test_monotonicity_sweep_flags_synthetic_violation_without_g3_claim() -> None:
    sweep = monotonicity_sweep_from_events(
        events_by_rho={
            0.0: [True, False, False, False],
            0.5: [True, True, False, False],
            1.0: [False, False, False, False],
        },
        resample_indices=_bootstrap_resamples(),
        confidence_level=0.5,
    )

    assert sweep.violations == ((0.0, 0.5, 0.25, 0.5),)
    assert not hasattr(sweep, "g3_verdict")


def test_monotonicity_sweep_rejects_invalid_synthetic_inputs() -> None:
    with pytest.raises(ValueError, match="same sample count"):
        monotonicity_sweep_from_events(
            events_by_rho={0.0: [True, False], 0.5: [True]},
            resample_indices=[[0, 1]],
        )

    with pytest.raises(TypeError, match="booleans"):
        bootstrap_probability_interval(
            [True, 0],
            resample_indices=[[0, 1]],
        )

    with pytest.raises(ValueError, match="bootstrap indices"):
        bootstrap_probability_interval(
            [True, False],
            resample_indices=[[0, 2]],
        )

def test_crosscheck_helpers_reject_invalid_synthetic_inputs() -> None:
    with pytest.raises(ValueError, match="beta must be positive"):
        GaussianToyParameters(mu_0=1.0, beta=0.0, sigma=0.2, threshold=1.1)

    with pytest.raises(ValueError, match="state probabilities must sum to 1"):
        finite_hybrid_bounds(
            fuzzy_number=TrapezoidalFuzzyNumber(0.0, 0.2, 0.4, 0.6),
            alpha_grid=[0.0],
            states=[FiniteHybridState(value=1.0, probability=0.5)],
            threshold=0.5,
        )


def test_crosscheck_report_records_scaffold_only_guardrails() -> None:
    report = Path("reports/crosscheck.md").read_text(encoding="utf-8")

    required_phrases = [
        "scaffold-only plan",
        "does not run integrated net load",
        "P(E_toy | rho)",
        "1 - Phi",
        "absolute-error tolerance",
        "finite hybrid toy",
        "Baudrit-style hybrid propagation",
        "executable synthetic package",
        "no scalar defuzzified probability",
        "G3 remains pending",
        "Q-5 is resolved by G0-A3",
        "Cross-Check 4: Synthetic Monotonicity",
        "rank-bootstrap intervals",
        "trust-certificate manifest",
        "separate lower/upper confidence intervals",
        "published-example blocker",
        "no G3 verdict",
    ]
    for phrase in required_phrases:
        assert phrase in report
