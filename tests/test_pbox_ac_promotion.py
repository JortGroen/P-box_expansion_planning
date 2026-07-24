from __future__ import annotations

import json

import numpy as np
import pytest

from src.evaluator_sum import Tier1Evaluation, count_import_overload_episodes
from src.pbox_ac_promotion import (
    AC_EXECUTION_STATUS,
    G2_STATUS_PENDING,
    SELECTIVE_AC_PROMOTION_FORMAT,
    assert_selective_ac_promotion_payload,
    build_selective_ac_promotion_metadata,
)
from src.pbox_error import OutputErrorEnvelope
from src.rng import sample_seed


def test_selective_ac_metadata_records_threshold_straddling_candidates() -> None:
    metadata = build_selective_ac_promotion_metadata(
        {
            0.0: [
                _trajectory([0.8, 0.8, 0.8, 0.8], p_signs=[1, 1, 1, 1]),
                _trajectory([0.96, 0.96, 0.96, 0.96], p_signs=[1, 1, 1, 1]),
                _trajectory([1.2, 1.2, 1.2, 1.2], p_signs=[1, 1, 1, 1]),
            ]
        },
        OutputErrorEnvelope(
            epsilon_grid=0.0,
            epsilon_tier1_minus=0.0,
            epsilon_tier1_plus=0.08,
        ),
        root_seed=1234,
    )

    payload = metadata.to_mapping()

    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert payload["metadata_format"] == SELECTIVE_AC_PROMOTION_FORMAT
    assert payload["use_status"] == "synthetic-only"
    assert payload["g2_status"] == G2_STATUS_PENDING
    assert payload["ac_execution_status"] == AC_EXECUTION_STATUS
    assert len(payload["candidates"]) == 1
    candidate = payload["candidates"][0]
    assert candidate["alpha"] == 0.0
    assert candidate["sample_index"] == 1
    assert candidate["sample_seed"] == sample_seed(1234, 1)
    assert candidate["straddling_timestep_indices"] == [0, 1, 2, 3]
    assert candidate["lower_event"] is False
    assert candidate["upper_event"] is True
    assert_selective_ac_promotion_payload(payload)


def test_selective_ac_metadata_preserves_rng001_identity_across_alpha_levels() -> None:
    metadata = build_selective_ac_promotion_metadata(
        {
            0.0: [_trajectory([0.96, 0.96, 0.96, 0.96], p_signs=[1, 1, 1, 1])],
            0.5: [_trajectory([0.96, 0.96, 0.96, 0.96], p_signs=[1, 1, 1, 1])],
        },
        OutputErrorEnvelope(0.0, 0.0, 0.08),
        root_seed=77,
    )

    candidates = metadata.to_mapping()["candidates"]

    assert [candidate["alpha"] for candidate in candidates] == [0.0, 0.5]
    assert {candidate["sample_seed"] for candidate in candidates} == {sample_seed(77, 0)}

    different_root = build_selective_ac_promotion_metadata(
        {0.0: [_trajectory([0.96, 0.96, 0.96, 0.96], p_signs=[1, 1, 1, 1])]},
        OutputErrorEnvelope(0.0, 0.0, 0.08),
        root_seed=78,
    )
    assert different_root.to_mapping()["candidates"][0]["sample_seed"] != sample_seed(77, 0)


def test_selective_ac_metadata_uses_unwidened_import_gate_for_straddles() -> None:
    metadata = build_selective_ac_promotion_metadata(
        {
            0.0: [
                _trajectory([0.96, 0.96, 0.96, 0.96], p_signs=[-1, -1, -1, -1]),
                _trajectory([0.96, 0.96, 0.96, 0.96], p_signs=[0, 0, 0, 0]),
                _trajectory([0.96, 0.96, 0.96, 0.96], p_signs=[1, -1, 1, 0]),
            ]
        },
        OutputErrorEnvelope(0.0, 0.0, 0.08),
        root_seed=12,
    )

    payload = metadata.to_mapping()

    assert len(payload["candidates"]) == 1
    assert payload["candidates"][0]["sample_index"] == 2
    assert payload["candidates"][0]["straddling_timestep_indices"] == [0, 2]
    assert payload["candidates"][0]["upper_event"] is False


def test_selective_ac_metadata_accepts_alpha_indexed_envelopes() -> None:
    metadata = build_selective_ac_promotion_metadata(
        {
            0.0: [_trajectory([0.96, 0.96, 0.96, 0.96], p_signs=[1, 1, 1, 1])],
            1.0: [_trajectory([0.96, 0.96, 0.96, 0.96], p_signs=[1, 1, 1, 1])],
        },
        {
            0.0: OutputErrorEnvelope(0.0, 0.0, 0.0),
            1.0: OutputErrorEnvelope(0.0, 0.0, 0.08),
        },
        root_seed=100,
    )

    payload = metadata.to_mapping()

    assert [candidate["alpha"] for candidate in payload["candidates"]] == [1.0]


def test_selective_ac_metadata_accepts_sensitivity_thresholds_above_one() -> None:
    metadata = build_selective_ac_promotion_metadata(
        {
            0.0: [
                _trajectory(
                    [1.16, 1.16, 1.16, 1.16],
                    p_signs=[1, 1, 1, 1],
                    threshold_pu=1.2,
                )
            ]
        },
        OutputErrorEnvelope(0.0, 0.0, 0.08),
        root_seed=222,
    )

    payload = metadata.to_mapping()

    assert payload["candidates"][0]["threshold_pu"] == 1.2
    assert_selective_ac_promotion_payload(payload)


@pytest.mark.parametrize(
    "payload_update,match",
    [
        ({"metadata_format": "old"}, "metadata_format"),
        ({"use_status": "paper-facing"}, "synthetic-only"),
        ({"g2_status": "approved"}, "pending"),
        ({"ac_execution_status": "run"}, "not-run"),
        ({"sample_count": 0}, "positive"),
        ({"alpha_grid": [0.5, 0.0]}, "strictly increasing"),
    ],
)
def test_selective_ac_payload_rejects_invalid_top_level_fields(
    payload_update: dict[str, object],
    match: str,
) -> None:
    payload = _valid_payload()
    payload.update(payload_update)

    with pytest.raises(ValueError, match=match):
        assert_selective_ac_promotion_payload(payload)


def test_selective_ac_payload_rejects_tampered_candidate_seed() -> None:
    payload = _valid_payload()
    payload["candidates"][0]["sample_seed"] = sample_seed(999, 0)

    with pytest.raises(ValueError, match="RNG-001"):
        assert_selective_ac_promotion_payload(payload)


def test_selective_ac_payload_rejects_duplicate_candidate_identity_keys() -> None:
    payload = _valid_payload()
    payload["candidates"].append(dict(payload["candidates"][0]))

    with pytest.raises(ValueError, match="strictly increasing"):
        assert_selective_ac_promotion_payload(payload)


def test_selective_ac_payload_rejects_unsorted_candidate_indices() -> None:
    payload = _valid_payload()
    payload["candidates"][0]["straddling_timestep_indices"] = [2, 1]

    with pytest.raises(ValueError, match="sorted and unique"):
        assert_selective_ac_promotion_payload(payload)


def test_selective_ac_payload_rejects_lower_event_outside_upper_event() -> None:
    payload = _valid_payload()
    payload["candidates"][0]["lower_event"] = True
    payload["candidates"][0]["upper_event"] = False

    with pytest.raises(ValueError, match="lower endpoint event"):
        assert_selective_ac_promotion_payload(payload)


def test_selective_ac_payload_rejects_endpoint_longest_run_inversion() -> None:
    payload = _valid_payload()
    payload["candidates"][0]["lower_longest_run_steps"] = 4
    payload["candidates"][0]["upper_longest_run_steps"] = 3

    with pytest.raises(ValueError, match="lower_longest_run_steps"):
        assert_selective_ac_promotion_payload(payload)


def test_selective_ac_builder_rejects_invalid_inputs() -> None:
    envelope = OutputErrorEnvelope(0.0, 0.0, 0.0)

    with pytest.raises(ValueError, match="root_seed"):
        build_selective_ac_promotion_metadata(
            {0.0: [_trajectory([1.0], p_signs=[1])]},
            envelope,
            root_seed=-1,
        )

    with pytest.raises(ValueError, match="same sample_count"):
        build_selective_ac_promotion_metadata(
            {
                0.0: [_trajectory([1.0], p_signs=[1])],
                0.5: [
                    _trajectory([1.0], p_signs=[1]),
                    _trajectory([1.0], p_signs=[1]),
                ],
            },
            envelope,
            root_seed=1,
        )

    with pytest.raises(ValueError, match="same alpha grid"):
        build_selective_ac_promotion_metadata(
            {0.0: [_trajectory([1.0], p_signs=[1])]},
            {0.5: envelope},
            root_seed=1,
        )


def _valid_payload() -> dict[str, object]:
    return build_selective_ac_promotion_metadata(
        {0.0: [_trajectory([0.96, 0.96, 0.96, 0.96], p_signs=[1, 1, 1, 1])]},
        OutputErrorEnvelope(0.0, 0.0, 0.08),
        root_seed=10,
    ).to_mapping()


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
