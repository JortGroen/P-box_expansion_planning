"""Synthetic E4/E5 runner-readiness packets for p-box math outputs.

The helpers here assemble existing B-owned output-error endpoint counts and
monotonicity diagnostics into manifest-ready synthetic packets. They do not run
real trajectories, estimate real overload probabilities, or authorize G3 vertex
shortcut use.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from src.contracts.loading_trajectory import LoadingTrajectoryResult
from src.pbox_error import (
    OUTPUT_ERROR_APPLICATION,
    OUTPUT_ERROR_DEPENDENCE,
    OUTPUT_ERROR_SAMPLING,
    OutputErrorProtocolConfig,
    estimate_output_error_probability_from_config,
)
from src.pbox_monotonicity import assert_synthetic_rho_sweep_payload

RUNNER_READINESS_PROTOCOL = "e4-e5-synthetic-runner-readiness-v1"
REAL_RUN_BLOCKER_PROTOCOL = "e4-e5-real-runner-blocker-v1"
RUNNER_READINESS_USE_STATUS = "synthetic-runner-readiness"
G3_PENDING_STATUS = "pending-no-paper-facing-vertex-claim"
REAL_RUN_BLOCKERS: tuple[str, ...] = (
    "missing signed G2 Tier-1 endpoints",
    "unsigned A-013 grid-error value/form",
    "missing capacity convention and denominator provenance",
    "missing real LoadingTrajectoryResult manifests",
    "missing real output-error endpoint records",
    "missing A-016 scenario consistency manifest",
    "G3 monotonicity verdict pending where vertex shortcut is claimed",
)
_FORBIDDEN_COLLAPSED_FIELDS = frozenset(
    {
        "defuzzified_probability",
        "expected_probability",
        "mean_probability",
        "mid_probability",
        "p_hat",
        "p_mid",
    }
)


@dataclass(frozen=True)
class SyntheticRunnerReadinessManifest:
    """Manifest-ready synthetic E4/E5 runner-readiness packet."""

    manifest_id: str
    alpha_endpoint_records: tuple[dict[str, object], ...]
    output_error_config: Mapping[str, object]
    real_use_blocker_manifest: Mapping[str, object]
    rho_sweep: Mapping[str, object] | None = None
    use_status: str = RUNNER_READINESS_USE_STATUS
    protocol: str = RUNNER_READINESS_PROTOCOL
    g3_status: str = G3_PENDING_STATUS

    def __post_init__(self) -> None:
        if not isinstance(self.manifest_id, str) or not self.manifest_id.strip():
            raise ValueError("manifest_id must be a nonempty string")
        if self.protocol != RUNNER_READINESS_PROTOCOL:
            raise ValueError(f"protocol must be {RUNNER_READINESS_PROTOCOL!r}")
        if self.use_status != RUNNER_READINESS_USE_STATUS:
            raise ValueError("runner readiness packets must remain synthetic-only")
        if self.g3_status != G3_PENDING_STATUS:
            raise ValueError("G3 must remain pending in this synthetic scaffold")
        _validate_alpha_endpoint_records(self.alpha_endpoint_records)
        _validate_output_error_config_metadata(self.output_error_config)
        assert_real_runner_blocker_payload(self.real_use_blocker_manifest)
        if self.rho_sweep is not None:
            assert_synthetic_rho_sweep_payload(self.rho_sweep)
            if int(self.rho_sweep["sample_count"]) != _endpoint_sample_count(
                self.alpha_endpoint_records
            ):
                raise ValueError("rho sweep sample_count must match endpoint records")

    def to_mapping(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "alpha_endpoint_records": [dict(record) for record in self.alpha_endpoint_records],
            "g3_status": self.g3_status,
            "invariants": {
                "alpha_indexed_lower_upper_reporting": True,
                "crn_sample_identity": "ordered_sample_indices_reused_across_alpha",
                "defuzzification": "forbidden",
                "endpoint_application": OUTPUT_ERROR_APPLICATION,
                "error_dependence": OUTPUT_ERROR_DEPENDENCE,
                "error_sampling": OUTPUT_ERROR_SAMPLING,
                "g3_vertex_claim": "none",
                "probability_widening": "forbidden",
                "unwidened_direction_gate": "unwidened_p_net_import_mask",
            },
            "manifest_id": self.manifest_id,
            "non_claims": [
                "no real trajectories",
                "no real P(E)",
                "no real rho sweep",
                "no capacity choice",
                "no A-013 or G2 numerical signoff",
                "no G3 vertex claim",
                "no manuscript number",
            ],
            "output_error_config": dict(self.output_error_config),
            "protocol": self.protocol,
            "real_use_blocker_manifest": dict(self.real_use_blocker_manifest),
            "use_status": self.use_status,
        }
        if self.rho_sweep is not None:
            payload["rho_sweep"] = dict(self.rho_sweep)
        return payload


def build_synthetic_runner_readiness_manifest(
    *,
    manifest_id: str,
    results_by_alpha: Mapping[float, Sequence[LoadingTrajectoryResult]],
    output_error_config: OutputErrorProtocolConfig,
    rho_sweep_payload: Mapping[str, object] | None = None,
    confidence_level: float = 0.95,
) -> SyntheticRunnerReadinessManifest:
    """Build a synthetic E4/E5 packet from validated trajectory fixtures.

    The packet is intentionally array-free. It preserves ordered sample indices
    across alpha levels so a later runner can check CRN identity without
    treating a synthetic fixture as a real experiment manifest.
    """

    if not isinstance(output_error_config, OutputErrorProtocolConfig):
        raise TypeError("output_error_config must be an OutputErrorProtocolConfig")
    if not results_by_alpha:
        raise ValueError("results_by_alpha must not be empty")
    alpha_grid = tuple(sorted(float(alpha) for alpha in results_by_alpha))
    if len(alpha_grid) != len(results_by_alpha):
        raise ValueError("alpha levels must be unique")
    alpha_records: list[dict[str, object]] = []
    reference_sample_indices: tuple[int, ...] | None = None
    for alpha in alpha_grid:
        if not math.isfinite(alpha) or not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha values must be finite and in [0, 1]")
        probability = estimate_output_error_probability_from_config(
            results_by_alpha[alpha],
            output_error_config,
            confidence_level=confidence_level,
        )
        sample_indices = tuple(event.sample_index for event in probability.samples)
        if reference_sample_indices is None:
            reference_sample_indices = sample_indices
        elif sample_indices != reference_sample_indices:
            raise ValueError("alpha levels must reuse identical ordered sample indices")
        alpha_records.append(_alpha_endpoint_record(alpha, probability))

    blocker_manifest = build_real_runner_blocker_manifest(
        manifest_id=f"{manifest_id}:real-use-blockers"
    )
    manifest = SyntheticRunnerReadinessManifest(
        manifest_id=manifest_id,
        alpha_endpoint_records=tuple(alpha_records),
        output_error_config=output_error_config.manifest_metadata(),
        real_use_blocker_manifest=blocker_manifest,
        rho_sweep=rho_sweep_payload,
    )
    return manifest


def build_real_runner_blocker_manifest(*, manifest_id: str) -> dict[str, object]:
    """Return the fail-closed blocker packet for future real runner use."""

    if not isinstance(manifest_id, str) or not manifest_id.strip():
        raise ValueError("manifest_id must be a nonempty string")
    return {
        "blockers": list(REAL_RUN_BLOCKERS),
        "manifest_id": manifest_id,
        "manifest_protocol": REAL_RUN_BLOCKER_PROTOCOL,
        "non_claims": [
            "no real trajectories accepted by this scaffold",
            "no real P(E)",
            "no capacity convention choice",
            "no A-013 or G2 numerical signoff",
            "no G3 vertex claim",
            "no manuscript number",
        ],
        "ready_for_real_run": False,
        "use_status": "real-use-blocker",
    }


def assert_synthetic_runner_readiness_payload(payload: Mapping[str, object]) -> None:
    """Validate a serialized synthetic E4/E5 runner-readiness packet."""

    _reject_collapsed_fields(payload)
    required = {
        "alpha_endpoint_records",
        "g3_status",
        "invariants",
        "manifest_id",
        "non_claims",
        "output_error_config",
        "protocol",
        "real_use_blocker_manifest",
        "use_status",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"runner readiness payload is missing fields: {missing}")
    if payload["protocol"] != RUNNER_READINESS_PROTOCOL:
        raise ValueError(f"protocol must be {RUNNER_READINESS_PROTOCOL!r}")
    if payload["use_status"] != RUNNER_READINESS_USE_STATUS:
        raise ValueError("runner readiness payload must remain synthetic-only")
    if payload["g3_status"] != G3_PENDING_STATUS:
        raise ValueError("G3 status must remain pending")
    _validate_invariants(payload["invariants"])
    if not isinstance(payload["output_error_config"], Mapping):
        raise TypeError("output_error_config must be a mapping")
    _validate_output_error_config_metadata(payload["output_error_config"])
    records = _expect_sequence(
        payload["alpha_endpoint_records"], name="alpha_endpoint_records"
    )
    _validate_alpha_endpoint_records(tuple(_expect_mapping(record) for record in records))
    assert_real_runner_blocker_payload(payload["real_use_blocker_manifest"])
    if "rho_sweep" in payload:
        rho_sweep = _expect_mapping(payload["rho_sweep"])
        assert_synthetic_rho_sweep_payload(rho_sweep)
        if int(rho_sweep["sample_count"]) != _endpoint_sample_count(
            tuple(_expect_mapping(record) for record in records)
        ):
            raise ValueError("rho sweep sample_count must match endpoint records")


def assert_real_runner_blocker_payload(payload: Mapping[str, object]) -> None:
    """Validate the real-use blocker packet without allowing readiness flips."""

    _reject_collapsed_fields(payload)
    if not isinstance(payload, Mapping):
        raise TypeError("real runner blocker payload must be a mapping")
    required = {
        "blockers",
        "manifest_id",
        "manifest_protocol",
        "non_claims",
        "ready_for_real_run",
        "use_status",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"real runner blocker payload is missing fields: {missing}")
    if payload["manifest_protocol"] != REAL_RUN_BLOCKER_PROTOCOL:
        raise ValueError(f"manifest_protocol must be {REAL_RUN_BLOCKER_PROTOCOL!r}")
    if payload["use_status"] != "real-use-blocker":
        raise ValueError("real runner blocker payload must remain a blocker")
    if payload["ready_for_real_run"] is not False:
        raise ValueError("real runner blocker payload must fail closed")
    blockers = tuple(
        _expect_string(item, name="blocker")
        for item in _expect_sequence(payload["blockers"], name="blockers")
    )
    if blockers != REAL_RUN_BLOCKERS:
        raise ValueError("real runner blockers must match the signed-gap checklist")


def _alpha_endpoint_record(alpha: float, probability: object) -> dict[str, object]:
    lower = probability.lower
    upper = probability.upper
    return {
        "alpha": alpha,
        "event_count_bounds": {
            "lower_successes": lower.successes,
            "sample_count": lower.sample_count,
            "upper_successes": upper.successes,
        },
        "probability_bounds": {
            "lower": _probability_estimate_mapping(lower),
            "upper": _probability_estimate_mapping(upper),
        },
        "sample_endpoint_events": [
            {
                "lower_event": event.lower_event,
                "lower_longest_run_steps": event.lower_longest_run_steps,
                "sample_index": event.sample_index,
                "upper_event": event.upper_event,
                "upper_longest_run_steps": event.upper_longest_run_steps,
            }
            for event in probability.samples
        ],
        "sample_indices": [event.sample_index for event in probability.samples],
    }


def _probability_estimate_mapping(estimate: object) -> dict[str, object]:
    return {
        "ci_lower": estimate.ci_lower,
        "ci_upper": estimate.ci_upper,
        "probability": estimate.probability,
        "sample_count": estimate.sample_count,
        "successes": estimate.successes,
    }


def _validate_alpha_endpoint_records(records: Sequence[Mapping[str, object]]) -> None:
    if not records:
        raise ValueError("alpha_endpoint_records must not be empty")
    previous_alpha: float | None = None
    reference_sample_indices: tuple[int, ...] | None = None
    for record in records:
        alpha = _expect_probability_float(record["alpha"], name="alpha")
        if previous_alpha is not None and alpha <= previous_alpha:
            raise ValueError("alpha endpoint records must be strictly increasing")
        previous_alpha = alpha
        sample_indices = tuple(
            _expect_nonnegative_int(item, name="sample_index")
            for item in _expect_sequence(record["sample_indices"], name="sample_indices")
        )
        if sample_indices != tuple(range(len(sample_indices))):
            raise ValueError("sample_indices must be contiguous from zero")
        if reference_sample_indices is None:
            reference_sample_indices = sample_indices
        elif sample_indices != reference_sample_indices:
            raise ValueError("alpha levels must reuse identical ordered sample indices")
        counts = _expect_mapping(record["event_count_bounds"])
        sample_count = _expect_nonnegative_int(counts["sample_count"], name="sample_count")
        lower_successes = _expect_nonnegative_int(
            counts["lower_successes"], name="lower_successes"
        )
        upper_successes = _expect_nonnegative_int(
            counts["upper_successes"], name="upper_successes"
        )
        if sample_count != len(sample_indices):
            raise ValueError("sample_count must match sample_indices")
        if lower_successes > upper_successes:
            raise ValueError("lower_successes must not exceed upper_successes")
        probability_bounds = _expect_mapping(record["probability_bounds"])
        _validate_probability_bound(
            _expect_mapping(probability_bounds["lower"]),
            expected_successes=lower_successes,
            expected_sample_count=sample_count,
            label="lower",
        )
        _validate_probability_bound(
            _expect_mapping(probability_bounds["upper"]),
            expected_successes=upper_successes,
            expected_sample_count=sample_count,
            label="upper",
        )
        for event in _expect_sequence(
            record["sample_endpoint_events"], name="sample_endpoint_events"
        ):
            event_mapping = _expect_mapping(event)
            index = _expect_nonnegative_int(event_mapping["sample_index"], name="sample_index")
            if index not in sample_indices:
                raise ValueError("event sample_index must be listed in sample_indices")
            if event_mapping["lower_event"] is True and event_mapping["upper_event"] is not True:
                raise ValueError("lower endpoint event cannot exceed upper endpoint event")
            lower_run = _expect_nonnegative_int(
                event_mapping["lower_longest_run_steps"], name="lower_longest_run_steps"
            )
            upper_run = _expect_nonnegative_int(
                event_mapping["upper_longest_run_steps"], name="upper_longest_run_steps"
            )
            if lower_run > upper_run:
                raise ValueError(
                    "lower endpoint run length cannot exceed upper endpoint run length"
                )


def _validate_probability_bound(
    bound: Mapping[str, object],
    *,
    expected_successes: int,
    expected_sample_count: int,
    label: str,
) -> None:
    probability = _expect_probability_float(bound["probability"], name=f"{label}.probability")
    ci_lower = _expect_probability_float(bound["ci_lower"], name=f"{label}.ci_lower")
    ci_upper = _expect_probability_float(bound["ci_upper"], name=f"{label}.ci_upper")
    successes = _expect_nonnegative_int(bound["successes"], name=f"{label}.successes")
    sample_count = _expect_nonnegative_int(bound["sample_count"], name=f"{label}.sample_count")
    if successes != expected_successes or sample_count != expected_sample_count:
        raise ValueError(f"{label} probability metadata must match event counts")
    if not ci_lower <= probability <= ci_upper:
        raise ValueError(f"{label} CI must contain probability")


def _validate_output_error_config_metadata(config: Mapping[str, object]) -> None:
    if config.get("probability_widening") != "forbidden":
        raise ValueError("probability widening must be forbidden")
    if config.get("error_application") != OUTPUT_ERROR_APPLICATION:
        raise ValueError("output-error endpoints must apply before event detection")
    if config.get("error_sampling") != OUTPUT_ERROR_SAMPLING:
        raise ValueError("output-error sampling must be forbidden")
    event_semantics = _expect_mapping(config["event_semantics"])
    if event_semantics.get("direction_gate") != "unwidened_p_net_import_mask":
        raise ValueError("direction gate must use unwidened P_net import mask")


def _validate_invariants(value: object) -> None:
    invariants = _expect_mapping(value)
    expected = {
        "alpha_indexed_lower_upper_reporting": True,
        "defuzzification": "forbidden",
        "endpoint_application": OUTPUT_ERROR_APPLICATION,
        "error_sampling": OUTPUT_ERROR_SAMPLING,
        "g3_vertex_claim": "none",
        "probability_widening": "forbidden",
        "unwidened_direction_gate": "unwidened_p_net_import_mask",
    }
    for key, expected_value in expected.items():
        if invariants.get(key) != expected_value:
            raise ValueError(f"invariant {key!r} must be {expected_value!r}")


def _endpoint_sample_count(records: Sequence[Mapping[str, object]]) -> int:
    counts = {
        _expect_nonnegative_int(
            _expect_mapping(record["event_count_bounds"])["sample_count"],
            name="sample_count",
        )
        for record in records
    }
    if len(counts) != 1:
        raise ValueError("all alpha endpoint records must use the same sample_count")
    return counts.pop()


def _reject_collapsed_fields(value: object) -> None:
    if isinstance(value, Mapping):
        collapsed = sorted(_FORBIDDEN_COLLAPSED_FIELDS.intersection(value))
        if collapsed:
            raise ValueError(f"runner readiness payload must not collapse probability: {collapsed}")
        for nested in value.values():
            _reject_collapsed_fields(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for nested in value:
            _reject_collapsed_fields(nested)


def _expect_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("expected a mapping")
    return value


def _expect_sequence(value: object, *, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a sequence")
    return value


def _expect_string(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value


def _expect_nonnegative_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a nonnegative integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def _expect_probability_float(value: object, *, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be a float")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return number
