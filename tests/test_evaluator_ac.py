from __future__ import annotations

import numpy as np
import pytest

from src.contracts.loading_trajectory import validate_loading_trajectory_result
from src.evaluator_ac import (
    ACEvaluatorProvenance,
    TransformerCapacityMetadata,
    build_ac_loading_trajectory,
)


def _timestamps() -> np.ndarray:
    return np.array(
        [
            "2035-01-01T00:00:00",
            "2035-01-01T00:15:00",
            "2035-01-01T00:30:00",
            "2035-01-01T00:45:00",
        ],
        dtype="datetime64[s]",
    )


def _capacity() -> TransformerCapacityMetadata:
    return TransformerCapacityMetadata(
        s_nom_agg_kva=80_000.0,
        convention="total_nameplate",
        transformer_indices=(0, 1),
        unit_nameplate_kva=(40_000.0, 40_000.0),
    )


def _provenance() -> ACEvaluatorProvenance:
    return ACEvaluatorProvenance(
        backend="synthetic",
        network_id="synthetic-primary-grid",
        solver="stubbed-ac-output",
        run_id="unit-test",
        metadata={"adapter": "scaffold"},
    )


def test_ac_scaffold_emits_loading_trajectory_contract_fields() -> None:
    result = build_ac_loading_trajectory(
        [40_000.0, -30_000.0, 0.0, 10_000.0],
        [0.0, 40_000.0, 5_000.0, 0.0],
        timestamps=_timestamps(),
        capacity=_capacity(),
        provenance=_provenance(),
    )

    validate_loading_trajectory_result(result)
    np.testing.assert_allclose(result.s_net_kva, [40_000.0, 50_000.0, 5_000.0, 10_000.0])
    np.testing.assert_allclose(result.screening_loading_pu, [0.5, 0.625, 0.0625, 0.125])
    np.testing.assert_allclose(result.import_loading_pu, [0.5, 0.0, 0.0, 0.125])
    np.testing.assert_allclose(result.export_loading_pu, [0.0, 0.625, 0.0, 0.0])
    assert result.import_mask.tolist() == [True, False, False, True]
    assert result.export_mask.tolist() == [False, True, False, False]
    assert result.zero_mask.tolist() == [False, False, True, False]
    assert result.primary_probability_domain is True


def test_ac_scaffold_validates_shape_units_and_timestep_cadence() -> None:
    with pytest.raises(ValueError, match="identical shapes"):
        build_ac_loading_trajectory(
            [1.0, 2.0],
            [1.0],
            timestamps=_timestamps()[:2],
            capacity=_capacity(),
            provenance=_provenance(),
        )

    with pytest.raises(ValueError, match="finite values"):
        build_ac_loading_trajectory(
            [1.0, np.nan],
            [0.0, 0.0],
            timestamps=_timestamps()[:2],
            capacity=_capacity(),
            provenance=_provenance(),
        )

    bad_cadence = np.array(["2035-01-01T00:00:00", "2035-01-01T00:10:00"], dtype="datetime64[s]")
    with pytest.raises(ValueError, match="900-second cadence"):
        build_ac_loading_trajectory(
            [1.0, 2.0],
            [0.0, 0.0],
            timestamps=bad_cadence,
            capacity=_capacity(),
            provenance=_provenance(),
        )


def test_capacity_metadata_is_validated_and_manifestable() -> None:
    capacity = _capacity()

    assert capacity.manifest_metadata() == {
        "s_nom_agg_kva": 80_000.0,
        "convention": "total_nameplate",
        "transformer_indices": [0, 1],
        "unit_nameplate_kva": [40_000.0, 40_000.0],
    }

    with pytest.raises(ValueError, match="positive"):
        TransformerCapacityMetadata(
            s_nom_agg_kva=0.0,
            convention="total_nameplate",
            transformer_indices=(0,),
            unit_nameplate_kva=(40_000.0,),
        )

    with pytest.raises(ValueError, match="duplicates"):
        TransformerCapacityMetadata(
            s_nom_agg_kva=80_000.0,
            convention="total_nameplate",
            transformer_indices=(0, 0),
            unit_nameplate_kva=(40_000.0, 40_000.0),
        )

    with pytest.raises(ValueError, match="match transformer_indices"):
        TransformerCapacityMetadata(
            s_nom_agg_kva=80_000.0,
            convention="total_nameplate",
            transformer_indices=(0, 1),
            unit_nameplate_kva=(40_000.0,),
        )


def test_ac_provenance_and_result_metadata_are_manifestable() -> None:
    result = build_ac_loading_trajectory(
        [1.0, 2.0, 3.0, 4.0],
        [0.0, 0.0, 0.0, 0.0],
        timestamps=_timestamps(),
        capacity=_capacity(),
        provenance=_provenance(),
        time_domain="window_set",
        threshold_pu=1.1,
        min_consecutive_steps=4,
    )

    metadata = result.manifest_metadata()
    assert metadata["time_domain"] == "window_set"
    assert metadata["primary_probability_domain"] is False
    assert metadata["timestep_s"] == 900
    assert metadata["threshold_pu"] == 1.1
    assert metadata["min_consecutive_steps"] == 4
    assert metadata["capacity"]["transformer_indices"] == [0, 1]
    assert metadata["provenance"]["backend"] == "synthetic"
    assert metadata["provenance"]["metadata"] == {"adapter": "scaffold"}


def test_ac_scaffold_preserves_unwidened_direction_gate_only() -> None:
    result = build_ac_loading_trajectory(
        [1_000.0, -1_000.0, 0.0],
        [0.0, 0.0, 1_000.0],
        timestamps=_timestamps()[:3],
        capacity=TransformerCapacityMetadata(
            s_nom_agg_kva=1_000.0,
            convention="custom",
            transformer_indices=(3,),
            unit_nameplate_kva=(1_000.0,),
        ),
        provenance=_provenance(),
    )

    widened = result.screening_loading_pu + 0.2
    assert np.where(result.import_mask, widened, 0.0).tolist() == pytest.approx([1.2, 0.0, 0.0])
    assert np.where(result.export_mask, widened, 0.0).tolist() == pytest.approx([0.0, 1.2, 0.0])
    assert result.zero_mask.tolist() == [False, False, True]
