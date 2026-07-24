from __future__ import annotations

import json

import numpy as np
import pytest

from src.evaluator_sum import Tier1Evaluation, count_import_overload_episodes
from src.evaluator_ac import (
    ACEvaluatorProvenance,
    TransformerCapacityMetadata,
    build_ac_loading_trajectory,
)
from src.pbox_error import (
    OUTPUT_ERROR_APPLICATION,
    OUTPUT_ERROR_DEPENDENCE,
    OUTPUT_ERROR_LOWER_FORMULA,
    OUTPUT_ERROR_SAMPLING,
    OUTPUT_ERROR_UPPER_FORMULA,
    OutputErrorEnvelope,
    OutputErrorProtocolConfig,
    apply_output_error_envelope,
    build_output_error_manifest_record,
    estimate_alpha_output_error_probability,
    estimate_output_error_probability,
    estimate_output_error_probability_from_config,
    evaluate_output_error_endpoint_event,
)


def test_output_error_protocol_config_records_manifest_ready_metadata() -> None:
    config = OutputErrorProtocolConfig.from_mapping(
        {
            "epsilon_grid": [0.0, 0.1],
            "epsilon_tier1_minus": [0.2, 0.1],
            "epsilon_tier1_plus": 0.3,
            "threshold_pu": 1.0,
            "min_consecutive_steps": 4,
            "timestep_seconds": 900,
            "envelope_source": "synthetic-test-envelope",
            "grid_error_source": "synthetic-grid-placeholder",
            "tier1_error_source": "synthetic-tier1-placeholder",
            "capacity_denominator_provenance": "synthetic-capacity-placeholder",
        }
    )

    metadata = config.manifest_metadata()

    assert json.loads(json.dumps(metadata, sort_keys=True)) == metadata
    assert metadata["probability_widening"] == "forbidden"
    assert metadata["use_status"] == "synthetic-only"
    assert metadata["envelope"] == {
        "epsilon_grid": [0.0, 0.1],
        "epsilon_tier1_minus": [0.2, 0.1],
        "epsilon_tier1_plus": 0.3,
    }
    assert metadata["event_semantics"] == {
        "comparator": "strict_greater_than",
        "direction_gate": "unwidened_p_net_import_mask",
        "min_consecutive_steps": 4,
        "threshold_pu": 1.0,
        "timestep_seconds": 900,
    }


def test_output_error_manifest_record_is_json_stable_and_count_based() -> None:
    config = OutputErrorProtocolConfig.from_mapping(
        {
            "epsilon_grid": 0.0,
            "epsilon_tier1_minus": 0.1,
            "epsilon_tier1_plus": 0.1,
            "threshold_pu": 1.0,
            "min_consecutive_steps": 4,
            "timestep_seconds": 900,
            "envelope_source": "synthetic-record-envelope",
            "grid_error_source": "synthetic-grid-placeholder",
            "tier1_error_source": "synthetic-tier1-placeholder",
            "capacity_denominator_provenance": "synthetic-capacity-placeholder",
        }
    )

    record = build_output_error_manifest_record(
        [
            _trajectory([0.8, 0.8, 0.8, 0.8], p_signs=[1, 1, 1, 1]),
            _trajectory([0.95, 0.95, 0.95, 0.95], p_signs=[1, 1, 1, 1]),
            _trajectory([1.2, 1.2, 1.2, 1.2], p_signs=[1, 1, 1, 1]),
        ],
        config,
    )

    assert json.loads(json.dumps(record, sort_keys=True)) == record
    assert record["probability_widening"] == "forbidden"
    assert record["config"]["probability_widening"] == "forbidden"
    assert record["config"]["event_semantics"]["direction_gate"] == (
        "unwidened_p_net_import_mask"
    )
    assert record["event_count_bounds"] == {
        "lower_successes": 1,
        "upper_successes": 2,
        "sample_count": 3,
    }
    assert record["probability_bounds"]["lower"]["successes"] == 1
    assert record["probability_bounds"]["upper"]["successes"] == 2
    assert record["probability_bounds"]["lower"]["probability"] == pytest.approx(1 / 3)
    assert record["probability_bounds"]["upper"]["probability"] == pytest.approx(2 / 3)
    assert [event["sample_index"] for event in record["sample_endpoint_events"]] == [0, 1, 2]
    assert [
        (event["lower_event"], event["upper_event"])
        for event in record["sample_endpoint_events"]
    ] == [(False, False), (False, True), (True, True)]


def test_output_error_manifest_record_validates_protocol_config_against_trajectories() -> None:
    config = OutputErrorProtocolConfig.from_mapping(
        {
            "epsilon_grid": 0.0,
            "epsilon_tier1_minus": 0.0,
            "epsilon_tier1_plus": 0.0,
            "threshold_pu": 1.0,
            "min_consecutive_steps": 4,
            "timestep_seconds": 900,
        }
    )

    with pytest.raises(ValueError, match="trajectory threshold_pu"):
        build_output_error_manifest_record(
            [_trajectory([1.0], p_signs=[1], threshold_pu=1.1)],
            config,
        )

def test_output_error_endpoints_match_hand_computed_asymmetric_formula() -> None:
    result = _trajectory([1.0, 0.5], p_signs=[1, 1])
    envelope = OutputErrorEnvelope(
        epsilon_grid=0.1,
        epsilon_tier1_minus=[0.2, 0.1],
        epsilon_tier1_plus=0.3,
    )

    endpoints = apply_output_error_envelope(result, envelope)

    np.testing.assert_allclose(endpoints.lower_loading_pu, [0.72, 0.36])
    np.testing.assert_allclose(endpoints.upper_loading_pu, [1.43, 0.88])
    np.testing.assert_allclose(endpoints.lower_import_loading_pu, [0.72, 0.36])
    np.testing.assert_allclose(endpoints.upper_import_loading_pu, [1.43, 0.88])


def test_output_error_lower_endpoint_clips_tier1_subtraction_at_zero() -> None:
    result = _trajectory([0.05, 0.3], p_signs=[1, 1])
    envelope = OutputErrorEnvelope(
        epsilon_grid=0.2,
        epsilon_tier1_minus=0.1,
        epsilon_tier1_plus=0.0,
    )

    endpoints = apply_output_error_envelope(result, envelope)

    np.testing.assert_allclose(endpoints.lower_loading_pu, [0.0, 0.16])
    np.testing.assert_allclose(endpoints.upper_loading_pu, [0.06, 0.36])


def test_output_error_accepts_time_varying_endpoint_arrays_for_unknown_dependence() -> None:
    result = _trajectory([0.9, 0.9, 0.9, 0.9], p_signs=[1, 1, 1, 1])
    envelope = OutputErrorEnvelope(
        epsilon_grid=[0.0, 0.05, 0.10, 0.20],
        epsilon_tier1_minus=[0.0, 0.10, 0.0, 0.10],
        epsilon_tier1_plus=[0.0, 0.0, 0.05, 0.05],
    )

    endpoints = apply_output_error_envelope(result, envelope)

    # Unknown dependence is represented by conservative endpoint arrays, not by
    # independently drawing an error realization for each timestep or sample.
    np.testing.assert_allclose(endpoints.lower_loading_pu, [0.9, 0.76, 0.81, 0.64])
    np.testing.assert_allclose(endpoints.upper_loading_pu, [0.9, 0.945, 1.045, 1.14])


def test_output_error_uses_unwidened_import_direction_gate() -> None:
    result = _trajectory([1.2, 1.4, 1.5, 1.3], p_signs=[1, -1, 0, 1])
    envelope = OutputErrorEnvelope(
        epsilon_grid=0.2,
        epsilon_tier1_minus=0.0,
        epsilon_tier1_plus=0.2,
    )

    endpoints = apply_output_error_envelope(result, envelope)

    assert result.import_mask.tolist() == [True, False, False, True]
    np.testing.assert_allclose(endpoints.upper_loading_pu, [1.68, 1.92, 2.04, 1.8])
    np.testing.assert_allclose(endpoints.upper_import_loading_pu, [1.68, 0.0, 0.0, 1.8])
    assert count_import_overload_episodes(
        endpoints.upper_import_loading_pu,
        threshold_pu=result.threshold_pu,
        min_consecutive_steps=result.min_consecutive_steps,
    ) == (0, 1)


def test_output_error_event_detector_runs_on_lower_and_upper_endpoints() -> None:
    result = _trajectory([1.0, 1.0, 1.0, 1.0], p_signs=[1, 1, 1, 1])
    envelope = OutputErrorEnvelope(
        epsilon_grid=0.1,
        epsilon_tier1_minus=0.0,
        epsilon_tier1_plus=0.05,
    )

    event = evaluate_output_error_endpoint_event(result, envelope, sample_index=4)

    assert event.sample_index == 4
    assert event.lower_event is False
    assert event.lower_longest_run_steps == 0
    assert event.upper_event is True
    assert event.upper_episode_count == 1
    assert event.upper_longest_run_steps == 4


def test_output_error_path_accepts_ac_loading_trajectory_contract() -> None:
    result = build_ac_loading_trajectory(
        [1_000.0, 1_000.0, -1_000.0, 0.0],
        [0.0, 0.0, 0.0, 1_200.0],
        timestamps=np.array(
            [
                "2035-01-01T00:00:00",
                "2035-01-01T00:15:00",
                "2035-01-01T00:30:00",
                "2035-01-01T00:45:00",
            ],
            dtype="datetime64[s]",
        ),
        capacity=TransformerCapacityMetadata(
            s_nom_agg_kva=1_000.0,
            convention="custom",
            transformer_indices=(0,),
            unit_nameplate_kva=(1_000.0,),
        ),
        provenance=ACEvaluatorProvenance(
            backend="synthetic",
            network_id="synthetic-contract-fixture",
            solver="no-ac-solve",
            run_id="e5-s3-output-error-test",
        ),
    )
    envelope = OutputErrorEnvelope(
        epsilon_grid=0.1,
        epsilon_tier1_minus=0.0,
        epsilon_tier1_plus=0.2,
    )

    endpoints = apply_output_error_envelope(result, envelope)

    np.testing.assert_allclose(endpoints.upper_loading_pu, [1.32, 1.32, 1.32, 1.54])
    # The output-error envelope widens magnitudes only; direction remains the
    # unwidened AC P-net sign from the shared IC-2 trajectory contract.
    np.testing.assert_allclose(endpoints.upper_import_loading_pu, [1.32, 1.32, 0.0, 0.0])
    event = evaluate_output_error_endpoint_event(result, envelope)
    assert event.upper_event is False
    assert event.upper_longest_run_steps == 2


def test_output_error_probability_from_config_uses_validated_trajectory_semantics() -> None:
    config = OutputErrorProtocolConfig.from_mapping(
        {
            "epsilon_grid": 0.0,
            "epsilon_tier1_minus": 0.1,
            "epsilon_tier1_plus": 0.1,
            "threshold_pu": 1.0,
            "min_consecutive_steps": 4,
            "timestep_seconds": 900,
        }
    )

    estimate = estimate_output_error_probability_from_config(
        [
            _trajectory([0.8, 0.8, 0.8, 0.8], p_signs=[1, 1, 1, 1]),
            _trajectory([0.95, 0.95, 0.95, 0.95], p_signs=[1, 1, 1, 1]),
            _trajectory([1.2, 1.2, 1.2, 1.2], p_signs=[1, 1, 1, 1]),
        ],
        config,
    )

    assert estimate.lower.successes == 1
    assert estimate.upper.successes == 2
    assert [event.sample_index for event in estimate.samples] == [0, 1, 2]

def test_output_error_probability_counts_endpoint_events_not_shifted_margins() -> None:
    no_event = _trajectory([0.8, 0.8, 0.8, 0.8], p_signs=[1, 1, 1, 1])
    upper_event = _trajectory([0.95, 0.95, 0.95, 0.95], p_signs=[1, 1, 1, 1])
    both_event = _trajectory([1.2, 1.2, 1.2, 1.2], p_signs=[1, 1, 1, 1])
    envelope = OutputErrorEnvelope(
        epsilon_grid=0.0,
        epsilon_tier1_minus=0.1,
        epsilon_tier1_plus=0.1,
    )

    estimate = estimate_output_error_probability(
        [no_event, upper_event, both_event],
        envelope,
    )

    assert estimate.lower.successes == 1
    assert estimate.lower.probability == pytest.approx(1 / 3)
    assert estimate.upper.successes == 2
    assert estimate.upper.probability == pytest.approx(2 / 3)
    assert [event.sample_index for event in estimate.samples] == [0, 1, 2]


def test_output_error_probability_uses_hand_computed_endpoint_event_counts() -> None:
    envelope = OutputErrorEnvelope(
        epsilon_grid=0.0,
        epsilon_tier1_minus=0.2,
        epsilon_tier1_plus=0.2,
    )
    estimate = estimate_output_error_probability(
        [
            _trajectory([1.0, 1.0, 1.0, 1.0], p_signs=[1, 1, 1, 1]),
            _trajectory([1.05, 1.05, 1.05, 1.05], p_signs=[1, 1, 1, 1]),
            _trajectory([1.35, 1.35, 1.35, 1.35], p_signs=[1, 1, 1, 1]),
            _trajectory([1.4, 1.4, 1.4, 1.4], p_signs=[1, 1, 1, 1]),
        ],
        envelope,
    )

    assert estimate.lower.successes == 2
    assert estimate.upper.successes == 4
    assert estimate.lower.probability == pytest.approx(0.5)
    assert estimate.upper.probability == pytest.approx(1.0)
    assert [(event.lower_event, event.upper_event) for event in estimate.samples] == [
        (False, True),
        (False, True),
        (True, True),
        (True, True),
    ]


def test_output_error_endpoint_detection_resets_on_unwidened_direction_flips() -> None:
    result = _trajectory([1.4, 1.4, 1.4, 1.4, 1.4], p_signs=[1, 1, -1, 1, 1])
    envelope = OutputErrorEnvelope(
        epsilon_grid=0.0,
        epsilon_tier1_minus=0.0,
        epsilon_tier1_plus=0.0,
    )

    event = evaluate_output_error_endpoint_event(result, envelope)

    assert event.upper_event is False
    assert event.upper_episode_count == 0
    assert event.upper_longest_run_steps == 2


def test_output_error_endpoint_sample_identity_is_reused_without_resampling() -> None:
    envelope = OutputErrorEnvelope(
        epsilon_grid=0.0,
        epsilon_tier1_minus=0.1,
        epsilon_tier1_plus=0.1,
    )
    first = [
        _trajectory([1.0, 1.0, 1.0, 1.0], p_signs=[1, 1, 1, 1]),
        _trajectory([1.3, 1.3, 1.3, 1.3], p_signs=[1, 1, 1, 1]),
    ]
    second = list(first)

    first_estimate = estimate_output_error_probability(first, envelope)
    second_estimate = estimate_output_error_probability(second, envelope)

    assert [event.sample_index for event in first_estimate.samples] == [0, 1]
    assert [event.sample_index for event in second_estimate.samples] == [0, 1]
    assert [
        (
            event.sample_index,
            event.lower_event,
            event.upper_event,
            event.lower_longest_run_steps,
            event.upper_longest_run_steps,
        )
        for event in first_estimate.samples
    ] == [
        (
            event.sample_index,
            event.lower_event,
            event.upper_event,
            event.lower_longest_run_steps,
            event.upper_longest_run_steps,
        )
        for event in second_estimate.samples
    ]


def test_output_error_alpha_estimator_keeps_separate_endpoint_counts() -> None:
    envelope = OutputErrorEnvelope(
        epsilon_grid=0.0,
        epsilon_tier1_minus=0.1,
        epsilon_tier1_plus=0.1,
    )
    estimates = estimate_alpha_output_error_probability(
        {
            0.5: [
                _trajectory([1.05, 1.05, 1.05, 1.05], p_signs=[1, 1, 1, 1]),
                _trajectory([1.3, 1.3, 1.3, 1.3], p_signs=[1, 1, 1, 1]),
            ],
            0.0: [
                _trajectory([0.85, 0.85, 0.85, 0.85], p_signs=[1, 1, 1, 1]),
                _trajectory([1.3, 1.3, 1.3, 1.3], p_signs=[1, 1, 1, 1]),
            ],
        },
        envelope,
    )

    assert list(estimates) == [0.0, 0.5]
    assert estimates[0.0].alpha == 0.0
    assert estimates[0.0].probability.lower.successes == 1
    assert estimates[0.0].probability.upper.successes == 1
    assert estimates[0.5].probability.lower.successes == 1
    assert estimates[0.5].probability.upper.successes == 2
    assert [event.sample_index for event in estimates[0.5].probability.samples] == [0, 1]


def test_output_error_alpha_estimator_accepts_alpha_indexed_envelopes() -> None:
    estimates = estimate_alpha_output_error_probability(
        {
            0.0: [
                _trajectory([1.0, 1.0, 1.0, 1.0], p_signs=[1, 1, 1, 1]),
            ],
            1.0: [
                _trajectory([1.0, 1.0, 1.0, 1.0], p_signs=[1, 1, 1, 1]),
            ],
        },
        {
            0.0: OutputErrorEnvelope(0.0, 0.0, 0.0),
            1.0: OutputErrorEnvelope(0.0, 0.0, 0.2),
        },
    )

    assert estimates[0.0].probability.upper.successes == 0
    assert estimates[1.0].probability.upper.successes == 1


def test_output_error_config_rejects_invalid_fields_and_trajectory_mismatch() -> None:
    base_config = {
        "epsilon_grid": 0.0,
        "epsilon_tier1_minus": 0.0,
        "epsilon_tier1_plus": 0.0,
        "threshold_pu": 1.0,
        "min_consecutive_steps": 4,
        "timestep_seconds": 900,
    }

    with pytest.raises(ValueError, match="unknown output-error config fields"):
        OutputErrorProtocolConfig.from_mapping({**base_config, "extra": "nope"})

    with pytest.raises(ValueError, match="missing output-error config fields"):
        OutputErrorProtocolConfig.from_mapping({"epsilon_grid": 0.0})

    config = OutputErrorProtocolConfig.from_mapping(base_config)
    with pytest.raises(ValueError, match="trajectory threshold_pu"):
        estimate_output_error_probability_from_config(
            [_trajectory([1.0], p_signs=[1], threshold_pu=1.1)],
            config,
        )

def test_output_error_rejects_invalid_envelopes_and_shape_mismatches() -> None:
    result = _trajectory([1.0, 1.0], p_signs=[1, 1])

    with pytest.raises(ValueError, match="epsilon_grid must be less than 1"):
        apply_output_error_envelope(
            result,
            OutputErrorEnvelope(1.0, 0.0, 0.0),
        )

    with pytest.raises(ValueError, match="epsilon_tier1_minus must be nonnegative"):
        apply_output_error_envelope(
            result,
            OutputErrorEnvelope(0.0, -0.1, 0.0),
        )

    with pytest.raises(ValueError, match="broadcastable"):
        apply_output_error_envelope(
            result,
            OutputErrorEnvelope(0.0, [0.0, 0.0, 0.0], 0.0),
        )


def test_output_error_empty_probability_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        estimate_output_error_probability(
            [],
            OutputErrorEnvelope(0.0, 0.0, 0.0),
        )


def test_output_error_alpha_estimator_rejects_invalid_alpha_inputs() -> None:
    envelope = OutputErrorEnvelope(0.0, 0.0, 0.0)

    with pytest.raises(ValueError, match="results_by_alpha"):
        estimate_alpha_output_error_probability({}, envelope)

    with pytest.raises(ValueError, match="alpha values"):
        estimate_alpha_output_error_probability(
            {np.nan: [_trajectory([1.0], p_signs=[1])]},
            envelope,
        )

    with pytest.raises(ValueError, match="same alpha grid"):
        estimate_alpha_output_error_probability(
            {0.0: [_trajectory([1.0], p_signs=[1])]},
            {0.5: envelope},
        )

    with pytest.raises(ValueError, match="same sample count"):
        estimate_alpha_output_error_probability(
            {
                0.0: [_trajectory([1.0], p_signs=[1])],
                0.5: [
                    _trajectory([1.0], p_signs=[1]),
                    _trajectory([1.0], p_signs=[1]),
                ],
            },
            envelope,
        )


def _trajectory(
    loading_pu: list[float],
    *,
    p_signs: list[int],
    threshold_pu: float = 1.0,
    min_consecutive_steps: int = 4,
) -> Tier1Evaluation:
    if len(loading_pu) != len(p_signs):
        raise ValueError("loading_pu and p_signs must have the same length")

    denominator_kva = 1000.0
    loading = np.asarray(loading_pu, dtype=float)
    signs = np.asarray(p_signs, dtype=int)
    p_net_kw = signs * loading * denominator_kva
    q_net_kvar = np.where(signs == 0, loading * denominator_kva, 0.0)
    s_net_kva = np.hypot(p_net_kw, q_net_kvar)
    screening_loading_pu = s_net_kva / denominator_kva
    import_mask = p_net_kw > 0.0
    export_mask = p_net_kw < 0.0
    zero_mask = p_net_kw == 0.0
    import_loading_pu = np.where(import_mask, screening_loading_pu, 0.0)
    export_loading_pu = np.where(export_mask, screening_loading_pu, 0.0)
    episodes, longest = count_import_overload_episodes(
        import_loading_pu,
        threshold_pu=threshold_pu,
        min_consecutive_steps=min_consecutive_steps,
    )
    return Tier1Evaluation(
        p_net_kw=p_net_kw,
        q_net_kvar=q_net_kvar,
        s_net_kva=s_net_kva,
        screening_loading_pu=screening_loading_pu,
        import_loading_pu=import_loading_pu,
        export_loading_pu=export_loading_pu,
        import_mask=import_mask,
        export_mask=export_mask,
        zero_mask=zero_mask,
        overload=episodes > 0,
        overload_episode_count=episodes,
        longest_import_run_steps=longest,
        time_domain="full_year",
        primary_probability_domain=True,
        threshold_pu=threshold_pu,
        min_consecutive_steps=min_consecutive_steps,
    )
