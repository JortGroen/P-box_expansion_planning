"""Selective-AC promotion metadata scaffolding for p-box output-error results.

This module does not execute AC power flow or approve a G2 promotion rule. It
only makes threshold-straddling endpoint evidence manifestable with preserved
RNG-001 sample identity so a later PI-approved selective-AC path can be wired
without losing provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

import numpy as np

from src.contracts.loading_trajectory import (
    LoadingTrajectoryResult,
    validate_loading_trajectory_result,
)
from src.pbox_error import (
    OutputErrorEnvelope,
    apply_output_error_envelope,
    evaluate_output_error_endpoint_event,
)
from src.rng import sample_seed

SELECTIVE_AC_PROMOTION_FORMAT = "selective-ac-promotion-metadata-v1"
SYNTHETIC_USE_STATUS = "synthetic-only"
G2_STATUS_PENDING = "g2-pending-rule-not-approved"
AC_EXECUTION_STATUS = "not-run"


@dataclass(frozen=True)
class SelectiveACPromotionCandidate:
    """One synthetic endpoint-straddling sample that a future rule may promote."""

    alpha: float
    sample_index: int
    sample_seed: int
    threshold_pu: float
    straddling_timestep_indices: tuple[int, ...]
    lower_event: bool
    upper_event: bool
    lower_longest_run_steps: int
    upper_longest_run_steps: int

    def __post_init__(self) -> None:
        _expect_probability(self.alpha, name="alpha")
        if self.sample_index < 0:
            raise ValueError("sample_index must be nonnegative")
        if self.sample_seed < 0:
            raise ValueError("sample_seed must be nonnegative")
        _expect_nonnegative_float(self.threshold_pu, name="threshold_pu")
        if not self.straddling_timestep_indices:
            raise ValueError("candidate must include at least one straddling timestep")
        if tuple(sorted(self.straddling_timestep_indices)) != self.straddling_timestep_indices:
            raise ValueError("straddling timestep indices must be sorted")
        if len(set(self.straddling_timestep_indices)) != len(self.straddling_timestep_indices):
            raise ValueError("straddling timestep indices must be unique")
        if any(index < 0 for index in self.straddling_timestep_indices):
            raise ValueError("straddling timestep indices must be nonnegative")
        if self.lower_event and not self.upper_event:
            raise ValueError("lower endpoint event cannot exceed upper endpoint event")
        if self.lower_longest_run_steps < 0 or self.upper_longest_run_steps < 0:
            raise ValueError("longest run diagnostics must be nonnegative")

    def to_mapping(self) -> dict[str, object]:
        """Return a JSON-stable candidate record."""

        return {
            "alpha": self.alpha,
            "lower_event": self.lower_event,
            "lower_longest_run_steps": self.lower_longest_run_steps,
            "sample_index": self.sample_index,
            "sample_seed": self.sample_seed,
            "straddling_timestep_indices": list(self.straddling_timestep_indices),
            "threshold_pu": self.threshold_pu,
            "upper_event": self.upper_event,
            "upper_longest_run_steps": self.upper_longest_run_steps,
        }


@dataclass(frozen=True)
class SelectiveACPromotionMetadata:
    """Manifest-ready synthetic selective-AC candidate metadata."""

    alpha_grid: tuple[float, ...]
    sample_count: int
    candidates: tuple[SelectiveACPromotionCandidate, ...]
    root_seed: int
    rule_basis: str = "endpoint-threshold-straddling-candidate"
    metadata_format: str = SELECTIVE_AC_PROMOTION_FORMAT
    use_status: str = SYNTHETIC_USE_STATUS
    g2_status: str = G2_STATUS_PENDING
    ac_execution_status: str = AC_EXECUTION_STATUS

    def __post_init__(self) -> None:
        if self.metadata_format != SELECTIVE_AC_PROMOTION_FORMAT:
            raise ValueError(
                f"metadata_format must be {SELECTIVE_AC_PROMOTION_FORMAT!r}"
            )
        if self.use_status != SYNTHETIC_USE_STATUS:
            raise ValueError("selective-AC promotion metadata is synthetic-only")
        if self.g2_status != G2_STATUS_PENDING:
            raise ValueError("g2_status must keep the promotion rule pending")
        if self.ac_execution_status != AC_EXECUTION_STATUS:
            raise ValueError("AC execution must remain not-run in this scaffold")
        if not isinstance(self.rule_basis, str) or not self.rule_basis.strip():
            raise ValueError("rule_basis must be a nonempty string")
        if self.root_seed < 0:
            raise ValueError("root_seed must be nonnegative")
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if not self.alpha_grid:
            raise ValueError("alpha_grid must not be empty")
        previous_alpha: float | None = None
        for alpha in self.alpha_grid:
            alpha_value = _expect_probability(alpha, name="alpha_grid")
            if previous_alpha is not None and alpha_value <= previous_alpha:
                raise ValueError("alpha_grid must be strictly increasing")
            previous_alpha = alpha_value
        for candidate in self.candidates:
            if candidate.alpha not in self.alpha_grid:
                raise ValueError("candidate alpha must appear in alpha_grid")
            if candidate.sample_index >= self.sample_count:
                raise ValueError("candidate sample_index exceeds sample_count")
            expected_seed = sample_seed(self.root_seed, candidate.sample_index)
            if candidate.sample_seed != expected_seed:
                raise ValueError("candidate sample_seed must match RNG-001 sample_seed")
        assert_selective_ac_promotion_payload(self.to_mapping())

    def to_mapping(self) -> dict[str, object]:
        """Return a JSON-stable payload for future runner manifests."""

        return {
            "ac_execution_status": self.ac_execution_status,
            "alpha_grid": list(self.alpha_grid),
            "candidates": [candidate.to_mapping() for candidate in self.candidates],
            "g2_status": self.g2_status,
            "metadata_format": self.metadata_format,
            "root_seed": self.root_seed,
            "rule_basis": self.rule_basis,
            "sample_count": self.sample_count,
            "use_status": self.use_status,
        }


def build_selective_ac_promotion_metadata(
    results_by_alpha: Mapping[float, Sequence[LoadingTrajectoryResult]],
    envelope: OutputErrorEnvelope | Mapping[float, OutputErrorEnvelope],
    *,
    root_seed: int,
) -> SelectiveACPromotionMetadata:
    """Build synthetic threshold-straddling metadata from endpoint trajectories."""

    if root_seed < 0:
        raise ValueError("root_seed must be nonnegative")
    if not results_by_alpha:
        raise ValueError("results_by_alpha must contain at least one alpha level")
    alpha_grid = tuple(sorted(results_by_alpha))
    for alpha in alpha_grid:
        _expect_probability(alpha, name="alpha")
    sample_counts = {len(results_by_alpha[alpha]) for alpha in alpha_grid}
    if len(sample_counts) != 1:
        raise ValueError("all alpha levels must use the same sample_count")
    sample_count = sample_counts.pop()
    if sample_count <= 0:
        raise ValueError("all alpha levels must contain at least one sample")

    if isinstance(envelope, Mapping):
        if tuple(sorted(envelope)) != alpha_grid:
            raise ValueError("envelope mapping must use the same alpha grid")
        envelope_by_alpha = envelope
    else:
        envelope_by_alpha = {alpha: envelope for alpha in alpha_grid}

    candidates: list[SelectiveACPromotionCandidate] = []
    for alpha in alpha_grid:
        for sample_index, result in enumerate(results_by_alpha[alpha]):
            candidate = _candidate_from_result(
                alpha=alpha,
                sample_index=sample_index,
                root_seed=root_seed,
                result=result,
                envelope=envelope_by_alpha[alpha],
            )
            if candidate is not None:
                candidates.append(candidate)
    return SelectiveACPromotionMetadata(
        alpha_grid=alpha_grid,
        sample_count=sample_count,
        candidates=tuple(candidates),
        root_seed=root_seed,
    )


def assert_selective_ac_promotion_payload(payload: Mapping[str, object]) -> None:
    """Validate serialized synthetic selective-AC promotion metadata."""

    required = {
        "ac_execution_status",
        "alpha_grid",
        "candidates",
        "g2_status",
        "metadata_format",
        "root_seed",
        "rule_basis",
        "sample_count",
        "use_status",
    }
    _require_mapping_fields(payload, required, name="selective AC payload")
    if payload["metadata_format"] != SELECTIVE_AC_PROMOTION_FORMAT:
        raise ValueError(
            f"metadata_format must be {SELECTIVE_AC_PROMOTION_FORMAT!r}"
        )
    if payload["use_status"] != SYNTHETIC_USE_STATUS:
        raise ValueError("use_status must be synthetic-only")
    if payload["g2_status"] != G2_STATUS_PENDING:
        raise ValueError("g2_status must remain pending")
    if payload["ac_execution_status"] != AC_EXECUTION_STATUS:
        raise ValueError("AC execution must remain not-run")
    if not isinstance(payload["rule_basis"], str) or not payload["rule_basis"].strip():
        raise ValueError("rule_basis must be a nonempty string")
    root_seed = _expect_nonnegative_int(payload["root_seed"], name="root_seed")
    sample_count = _expect_positive_int(payload["sample_count"], name="sample_count")
    alpha_grid = tuple(
        _expect_probability(alpha, name="alpha_grid")
        for alpha in _expect_sequence(payload["alpha_grid"], name="alpha_grid")
    )
    if not alpha_grid:
        raise ValueError("alpha_grid must not be empty")
    if tuple(sorted(alpha_grid)) != alpha_grid or len(set(alpha_grid)) != len(alpha_grid):
        raise ValueError("alpha_grid must be strictly increasing")

    candidates = _expect_sequence(payload["candidates"], name="candidates")
    previous_key: tuple[float, int] | None = None
    for raw_candidate in candidates:
        candidate = _expect_mapping(raw_candidate, name="candidate")
        _validate_candidate_mapping(
            candidate,
            alpha_grid=alpha_grid,
            root_seed=root_seed,
            sample_count=sample_count,
        )
        key = (float(candidate["alpha"]), int(candidate["sample_index"]))
        if previous_key is not None and key < previous_key:
            raise ValueError("candidates must be sorted by alpha and sample_index")
        previous_key = key


def _candidate_from_result(
    *,
    alpha: float,
    sample_index: int,
    root_seed: int,
    result: LoadingTrajectoryResult,
    envelope: OutputErrorEnvelope,
) -> SelectiveACPromotionCandidate | None:
    validate_loading_trajectory_result(result)
    endpoints = apply_output_error_envelope(result, envelope)
    import_mask = np.asarray(result.import_mask, dtype=bool)
    threshold = float(result.threshold_pu)
    lower = np.asarray(endpoints.lower_import_loading_pu, dtype=float)
    upper = np.asarray(endpoints.upper_import_loading_pu, dtype=float)
    # The straddle detector is metadata-only: it records where endpoint
    # uncertainty crosses the strict event threshold, without choosing or
    # executing a G2 selective-AC promotion rule.
    straddles = np.where(import_mask & (lower <= threshold) & (threshold < upper))[0]
    if straddles.size == 0:
        return None
    event = evaluate_output_error_endpoint_event(
        result,
        envelope,
        sample_index=sample_index,
    )
    return SelectiveACPromotionCandidate(
        alpha=alpha,
        sample_index=sample_index,
        sample_seed=sample_seed(root_seed, sample_index),
        threshold_pu=threshold,
        straddling_timestep_indices=tuple(int(index) for index in straddles.tolist()),
        lower_event=event.lower_event,
        upper_event=event.upper_event,
        lower_longest_run_steps=event.lower_longest_run_steps,
        upper_longest_run_steps=event.upper_longest_run_steps,
    )


def _validate_candidate_mapping(
    candidate: Mapping[str, object],
    *,
    alpha_grid: tuple[float, ...],
    root_seed: int,
    sample_count: int,
) -> None:
    required = {
        "alpha",
        "lower_event",
        "lower_longest_run_steps",
        "sample_index",
        "sample_seed",
        "straddling_timestep_indices",
        "threshold_pu",
        "upper_event",
        "upper_longest_run_steps",
    }
    _require_mapping_fields(candidate, required, name="candidate")
    alpha = _expect_probability(candidate["alpha"], name="candidate.alpha")
    if alpha not in alpha_grid:
        raise ValueError("candidate alpha must appear in alpha_grid")
    sample_index = _expect_nonnegative_int(
        candidate["sample_index"], name="candidate.sample_index"
    )
    if sample_index >= sample_count:
        raise ValueError("candidate sample_index exceeds sample_count")
    sample_seed_value = _expect_nonnegative_int(
        candidate["sample_seed"], name="candidate.sample_seed"
    )
    if sample_seed_value != sample_seed(root_seed, sample_index):
        raise ValueError("candidate sample_seed must match RNG-001 sample_seed")
    _expect_nonnegative_float(candidate["threshold_pu"], name="candidate.threshold_pu")
    indices = tuple(
        _expect_nonnegative_int(index, name="straddling_timestep_index")
        for index in _expect_sequence(
            candidate["straddling_timestep_indices"],
            name="candidate.straddling_timestep_indices",
        )
    )
    if not indices:
        raise ValueError("candidate must include at least one straddling timestep")
    if tuple(sorted(indices)) != indices or len(set(indices)) != len(indices):
        raise ValueError("straddling timestep indices must be sorted and unique")
    lower_event = candidate["lower_event"]
    upper_event = candidate["upper_event"]
    if not isinstance(lower_event, bool) or not isinstance(upper_event, bool):
        raise TypeError("candidate endpoint events must be booleans")
    if lower_event and not upper_event:
        raise ValueError("lower endpoint event cannot exceed upper endpoint event")
    _expect_nonnegative_int(
        candidate["lower_longest_run_steps"], name="candidate.lower_longest_run_steps"
    )
    _expect_nonnegative_int(
        candidate["upper_longest_run_steps"], name="candidate.upper_longest_run_steps"
    )


def _require_mapping_fields(mapping: Mapping[str, object], required: set[str], *, name: str) -> None:
    missing = required.difference(mapping)
    if missing:
        raise ValueError(f"{name} is missing fields: {sorted(missing)}")


def _expect_mapping(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _expect_sequence(value: object, *, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a sequence")
    return value


def _expect_probability(value: object, *, name: str) -> float:
    probability = float(value)
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return probability


def _expect_nonnegative_float(value: object, *, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return number

def _expect_positive_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _expect_nonnegative_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value
