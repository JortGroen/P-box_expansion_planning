from __future__ import annotations

import numpy as np
import pytest

from src.evaluator_sum import Tier1Evaluation, count_import_overload_episodes
from src.pbox_error import (
    OutputErrorEnvelope,
    apply_output_error_envelope,
    estimate_alpha_output_error_probability,
    estimate_output_error_probability,
    evaluate_output_error_endpoint_event,
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


def test_output_error_probability_counts_endpoint_events_not_shifted_margins() -> None:
    no_event = _trajectory([1.0, 1.0, 1.0, 1.0], p_signs=[1, 1, 1, 1])
    upper_event = _trajectory([1.05, 1.05, 1.05, 1.05], p_signs=[1, 1, 1, 1])
    both_event = _trajectory([1.3, 1.3, 1.3, 1.3], p_signs=[1, 1, 1, 1])
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
                _trajectory([1.0, 1.0, 1.0, 1.0], p_signs=[1, 1, 1, 1]),
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


def _trajectory(
    loading_pu: list[float],
    *,
    p_signs: list[int],
    threshold_pu: float = 1.1,
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
