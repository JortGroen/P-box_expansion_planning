"""Capacity provenance helpers for the E3.S2b screen boundary.

The module extracts transformer-bank facts from the selected pandapower network
and packages both total-nameplate and firm ``(n-1)`` conventions without
choosing either as the scientific denominator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


CAPACITY_PROVENANCE_SCHEMA_VERSION = "e3_s2b_capacity_provenance_v1"
PENDING_CAPACITY_CONVENTION_STATUS = "pending_g1_a2_e3_s2b"
RAW_MVA_REPORT_CONVENTIONS = ("total_nameplate", "firm_n_minus_1")
FIRM_OUTAGE_CONVENTION = (
    "firm (n-1) aggregate nameplate equals total selected decision-transformer "
    "nameplate minus the largest in-service selected unit nameplate"
)


@dataclass(frozen=True)
class CapacityProvenanceConfig:
    """Versioned input for E3.S2b capacity-provenance extraction."""

    grid_key: str
    grid_code: str
    decision_transformer_indices: tuple[int, ...]
    busbar_switch_indices: tuple[int, ...]
    transformer_switch_indices: tuple[int, ...]
    grid_source: str = "simbench"
    decision_asset_id: str = "g0_decision_transformer"
    task_id: str = "E3.S2b"
    supporting_evidence_paths: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_nonempty_text(self.grid_key, name="grid_key")
        _require_nonempty_text(self.grid_code, name="grid_code")
        _require_nonempty_text(self.grid_source, name="grid_source")
        _require_nonempty_text(self.decision_asset_id, name="decision_asset_id")
        _require_nonempty_text(self.task_id, name="task_id")
        object.__setattr__(
            self,
            "decision_transformer_indices",
            _exact_nonnegative_integer_tuple(self.decision_transformer_indices, name="decision_transformer_indices"),
        )
        object.__setattr__(
            self,
            "busbar_switch_indices",
            _exact_nonnegative_integer_tuple(self.busbar_switch_indices, name="busbar_switch_indices"),
        )
        object.__setattr__(
            self,
            "transformer_switch_indices",
            _exact_nonnegative_integer_tuple(self.transformer_switch_indices, name="transformer_switch_indices"),
        )
        if not self.decision_transformer_indices:
            raise ValueError("decision_transformer_indices must not be empty")
        if len(set(self.decision_transformer_indices)) != len(self.decision_transformer_indices):
            raise ValueError("decision_transformer_indices must not contain duplicates")
        if len(set(self.busbar_switch_indices)) != len(self.busbar_switch_indices):
            raise ValueError("busbar_switch_indices must not contain duplicates")
        if len(set(self.transformer_switch_indices)) != len(self.transformer_switch_indices):
            raise ValueError("transformer_switch_indices must not contain duplicates")
        support = tuple(_require_nonempty_text(path, name="supporting_evidence_path") for path in self.supporting_evidence_paths)
        _validate_metadata(self.metadata, name="metadata")
        object.__setattr__(self, "supporting_evidence_paths", support)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "CapacityProvenanceConfig":
        """Build a config from a JSON-compatible mapping."""

        return cls(
            grid_key=str(payload["grid_key"]),
            grid_code=str(payload["grid_code"]),
            grid_source=str(payload.get("grid_source", "simbench")),
            decision_asset_id=str(payload.get("decision_asset_id", "g0_decision_transformer")),
            task_id=str(payload.get("task_id", "E3.S2b")),
            decision_transformer_indices=tuple(payload["decision_transformer_indices"]),
            busbar_switch_indices=tuple(payload.get("busbar_switch_indices", ())),
            transformer_switch_indices=tuple(payload.get("transformer_switch_indices", ())),
            supporting_evidence_paths=tuple(payload.get("supporting_evidence_paths", ())),
            metadata=dict(payload.get("metadata", {})),
        )

    def manifest_record(self) -> dict[str, object]:
        """Return JSON-ready config metadata without loading the grid."""

        return {
            "grid_key": self.grid_key,
            "grid_code": self.grid_code,
            "grid_source": self.grid_source,
            "decision_asset_id": self.decision_asset_id,
            "task_id": self.task_id,
            "decision_transformer_indices": self.decision_transformer_indices,
            "busbar_switch_indices": self.busbar_switch_indices,
            "transformer_switch_indices": self.transformer_switch_indices,
            "supporting_evidence_paths": self.supporting_evidence_paths,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CapacityProvenancePacket:
    """Machine-readable capacity facts for later E3.S2b pre-run readiness."""

    schema_version: str
    task_id: str
    status: str
    ready_for_e3_s2b_capacity_prerun: bool
    capacity_provenance: Mapping[str, object]
    transformer_records: tuple[Mapping[str, object], ...]
    switch_records: tuple[Mapping[str, object], ...]
    blocker_manifest: Mapping[str, object]
    non_claims: tuple[str, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_nonempty_text(self.schema_version, name="schema_version")
        _require_nonempty_text(self.task_id, name="task_id")
        _require_nonempty_text(self.status, name="status")
        if not isinstance(self.ready_for_e3_s2b_capacity_prerun, bool):
            raise TypeError("ready_for_e3_s2b_capacity_prerun must be boolean")
        _validate_metadata(self.capacity_provenance, name="capacity_provenance")
        _validate_metadata(self.blocker_manifest, name="blocker_manifest")
        blockers = self.blocker_manifest.get("items", ())
        if self.ready_for_e3_s2b_capacity_prerun and blockers:
            raise ValueError("ready capacity packet must not contain blockers")
        if not self.ready_for_e3_s2b_capacity_prerun and not blockers:
            raise ValueError("blocked capacity packet must explain blockers")
        if not self.transformer_records:
            raise ValueError("transformer_records must not be empty")
        if not self.non_claims:
            raise ValueError("non_claims must not be empty")
        object.__setattr__(self, "capacity_provenance", MappingProxyType(dict(self.capacity_provenance)))
        object.__setattr__(self, "transformer_records", tuple(MappingProxyType(dict(row)) for row in self.transformer_records))
        object.__setattr__(self, "switch_records", tuple(MappingProxyType(dict(row)) for row in self.switch_records))
        object.__setattr__(self, "blocker_manifest", MappingProxyType(dict(self.blocker_manifest)))
        object.__setattr__(self, "non_claims", tuple(self.non_claims))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def manifest_record(self) -> dict[str, object]:
        """Return a JSON-serializable packet."""

        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "status": self.status,
            "ready_for_e3_s2b_capacity_prerun": self.ready_for_e3_s2b_capacity_prerun,
            "capacity_provenance": dict(self.capacity_provenance),
            "transformer_records": [dict(row) for row in self.transformer_records],
            "switch_records": [dict(row) for row in self.switch_records],
            "blocker_manifest": dict(self.blocker_manifest),
            "non_claims": self.non_claims,
            "metadata": dict(self.metadata),
        }


def collect_capacity_provenance(net: Any, config: CapacityProvenanceConfig) -> CapacityProvenancePacket:
    """Collect decision-transformer capacity facts from a pandapower network.

    The function returns a fail-closed packet. Ambiguous bank topology or missing
    rating metadata is reported as blockers instead of selecting a convention.
    """

    trafo = _require_table(net, "trafo")
    switch = getattr(net, "switch", pd.DataFrame())
    blockers: list[dict[str, object]] = []
    transformer_records, transformer_blockers = _transformer_records(trafo, config.decision_transformer_indices)
    blockers.extend(transformer_blockers)
    switch_records, switch_blockers = _switch_records(
        switch,
        busbar_switch_indices=config.busbar_switch_indices,
        transformer_switch_indices=config.transformer_switch_indices,
    )
    blockers.extend(switch_blockers)
    topology_record, topology_blockers = _parallel_operation_record(
        transformer_records,
        switch_records,
        busbar_switch_indices=config.busbar_switch_indices,
        transformer_switch_indices=config.transformer_switch_indices,
    )
    blockers.extend(topology_blockers)

    unit_nameplate_kva = tuple(float(row["sn_mva"]) * 1000.0 for row in transformer_records)
    total_nameplate_kva = float(sum(unit_nameplate_kva)) if unit_nameplate_kva else 0.0
    firm_nameplate_kva = 0.0
    if len(unit_nameplate_kva) < 2:
        blockers.append(_blocker("firm_nameplate_not_applicable", "G1-A2-CAPACITY-CONVENTION", "firm (n-1) nameplate requires at least two selected transformer units"))
    elif total_nameplate_kva > 0.0:
        firm_nameplate_kva = total_nameplate_kva - max(unit_nameplate_kva)
        if firm_nameplate_kva <= 0.0:
            blockers.append(_blocker("firm_nameplate_nonpositive", "G1-A2-CAPACITY-CONVENTION", "firm (n-1) nameplate must be positive"))

    ready = not blockers
    status = "ready_for_pi_capacity_provenance_review" if ready else "blocked_capacity_provenance"
    capacity_provenance = {
        "s_nom_agg_kva": total_nameplate_kva,
        "convention_status": PENDING_CAPACITY_CONVENTION_STATUS,
        "source": "E3.S2b capacity provenance collector from selected pandapower network",
        "transformer_indices": config.decision_transformer_indices,
        "unit_nameplate_kva": unit_nameplate_kva,
        "total_nameplate_kva": total_nameplate_kva,
        "firm_n_minus_1_nameplate_kva": firm_nameplate_kva,
        "firm_outage_convention": FIRM_OUTAGE_CONVENTION,
        "raw_mva_report_conventions": RAW_MVA_REPORT_CONVENTIONS,
        "raw_mva_reporting_fields": _raw_mva_reporting_fields(),
        "metadata": {
            "grid_key": config.grid_key,
            "grid_code": config.grid_code,
            "grid_source": config.grid_source,
            "decision_asset_id": config.decision_asset_id,
            "busbar_parallel_status": topology_record["summary"],
            "total_vs_firm_decision_status": "pending_pi_decision_after_e3_s2b_screen",
            "firm_primary_requires_actual_one_transformer_out_ac_validation": True,
        },
    }
    return CapacityProvenancePacket(
        schema_version=CAPACITY_PROVENANCE_SCHEMA_VERSION,
        task_id=config.task_id,
        status=status,
        ready_for_e3_s2b_capacity_prerun=ready,
        capacity_provenance=capacity_provenance,
        transformer_records=transformer_records,
        switch_records=switch_records,
        blocker_manifest={
            "ready": ready,
            "blocker_count": len(blockers),
            "items": tuple(blockers),
        },
        non_claims=(
            "No total-versus-firm denominator convention is selected.",
            "No capacity/domain screen result, congestion conclusion, event count, P(E), or manuscript number is produced.",
            "Firm capacity remains a planning convention candidate and requires actual one-transformer-out AC validation before primary use.",
        ),
        metadata={
            "config": config.manifest_record(),
            "topology_record": topology_record,
        },
    )


def _transformer_records(trafo: pd.DataFrame, indices: Sequence[int]) -> tuple[tuple[dict[str, object], ...], list[dict[str, object]]]:
    records: list[dict[str, object]] = []
    blockers: list[dict[str, object]] = []
    required_columns = ("sn_mva", "hv_bus", "lv_bus", "in_service")
    missing_columns = [column for column in required_columns if column not in trafo.columns]
    if missing_columns:
        return (), [_blocker("transformer_columns_missing", "E3.S2B-CAPACITY-PROVENANCE", f"net.trafo missing column(s): {', '.join(missing_columns)}")]
    for index in indices:
        if index not in trafo.index:
            blockers.append(_blocker("transformer_index_missing", "E3.S2B-CAPACITY-PROVENANCE", f"net.trafo index {index} is missing"))
            continue
        row = trafo.loc[index]
        nameplate = float(row["sn_mva"])
        if not np.isfinite(nameplate) or nameplate <= 0.0:
            blockers.append(_blocker("transformer_nameplate_invalid", "E3.S2B-CAPACITY-PROVENANCE", f"net.trafo index {index} has invalid sn_mva"))
        in_service = bool(row["in_service"])
        if not in_service:
            blockers.append(_blocker("transformer_not_in_service", "E3.S2B-CAPACITY-PROVENANCE", f"net.trafo index {index} is not in service"))
        records.append(
            {
                "trafo_index": int(index),
                "name": _string_or_empty(row.get("name", "")),
                "hv_bus": int(row["hv_bus"]),
                "lv_bus": int(row["lv_bus"]),
                "sn_mva": nameplate,
                "sn_kva": nameplate * 1000.0,
                "parallel": int(row["parallel"]) if "parallel" in trafo.columns and pd.notna(row.get("parallel")) else 1,
                "tap_pos": _json_scalar(row.get("tap_pos")) if "tap_pos" in trafo.columns else None,
                "in_service": in_service,
            }
        )
    return tuple(records), blockers


def _switch_records(
    switch: pd.DataFrame,
    *,
    busbar_switch_indices: Sequence[int],
    transformer_switch_indices: Sequence[int],
) -> tuple[tuple[dict[str, object], ...], list[dict[str, object]]]:
    records: list[dict[str, object]] = []
    blockers: list[dict[str, object]] = []
    if not busbar_switch_indices:
        blockers.append(_blocker("busbar_switch_indices_missing", "E3.S2B-CAPACITY-PROVENANCE", "busbar/tie switch indices are required to confirm parallel operation"))
    if not transformer_switch_indices:
        blockers.append(_blocker("transformer_switch_indices_missing", "E3.S2B-CAPACITY-PROVENANCE", "transformer switch indices are required to confirm selected units are connected"))
    if switch.empty:
        blockers.append(_blocker("switch_table_missing", "E3.S2B-CAPACITY-PROVENANCE", "net.switch table is required to confirm busbar/tie arrangement"))
        return (), blockers
    required_columns = ("bus", "element", "et", "closed")
    missing_columns = [column for column in required_columns if column not in switch.columns]
    if missing_columns:
        blockers.append(_blocker("switch_columns_missing", "E3.S2B-CAPACITY-PROVENANCE", f"net.switch missing column(s): {', '.join(missing_columns)}"))
        return (), blockers
    for role, indices, expected_et in (
        ("busbar_tie", busbar_switch_indices, "b"),
        ("transformer_circuit_breaker", transformer_switch_indices, "t"),
    ):
        for index in indices:
            if index not in switch.index:
                blockers.append(_blocker("switch_index_missing", "E3.S2B-CAPACITY-PROVENANCE", f"net.switch index {index} is missing"))
                continue
            row = switch.loc[index]
            closed = bool(row["closed"])
            et = str(row["et"])
            if et != expected_et:
                blockers.append(_blocker("switch_type_mismatch", "E3.S2B-CAPACITY-PROVENANCE", f"net.switch index {index} has et={et!r}, expected {expected_et!r}"))
            if not closed:
                blockers.append(_blocker("switch_open", "E3.S2B-CAPACITY-PROVENANCE", f"net.switch index {index} is open"))
            records.append(
                {
                    "switch_index": int(index),
                    "role": role,
                    "bus": int(row["bus"]),
                    "element": int(row["element"]),
                    "et": et,
                    "closed": closed,
                    "type": _string_or_empty(row.get("type", "")),
                    "name": _string_or_empty(row.get("name", "")),
                }
            )
    return tuple(records), blockers


def _parallel_operation_record(
    transformer_records: Sequence[Mapping[str, object]],
    switch_records: Sequence[Mapping[str, object]],
    *,
    busbar_switch_indices: Sequence[int],
    transformer_switch_indices: Sequence[int],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    blockers: list[dict[str, object]] = []
    in_service = all(bool(row["in_service"]) for row in transformer_records)
    busbar_closed = all(bool(row["closed"]) for row in switch_records if row["role"] == "busbar_tie")
    trafo_switches_closed = all(bool(row["closed"]) for row in switch_records if row["role"] == "transformer_circuit_breaker")
    tap_values = tuple(row.get("tap_pos") for row in transformer_records)
    equal_taps = len(set(tap_values)) <= 1
    unit_count = len(transformer_records)
    if unit_count < 2:
        blockers.append(_blocker("parallel_unit_count_insufficient", "A-005", "decision-transformer bank must contain at least two units for total/firm side-by-side reporting"))
    if not busbar_closed:
        blockers.append(_blocker("busbar_tie_not_closed", "A-005", "busbar/tie switches must be closed before treating the units as one aggregate decision asset"))
    if not trafo_switches_closed:
        blockers.append(_blocker("transformer_switches_not_closed", "A-005", "selected transformer circuit breakers must be closed before aggregate capacity use"))
    if not equal_taps:
        blockers.append(_blocker("tap_positions_differ", "A-005", "selected transformer tap positions differ, making aggregate parallel loading ambiguous"))
    if not in_service:
        blockers.append(_blocker("selected_transformer_not_in_service", "A-005", "selected transformer units must be in service"))
    summary = (
        "Closed busbar-parallel transformer bank: "
        f"busbar/tie switches {list(busbar_switch_indices)} closed={busbar_closed}; "
        f"associated transformer circuit-breaker switches {list(transformer_switch_indices)} closed={trafo_switches_closed}; "
        f"equal tap positions={equal_taps}; selected transformer units in service={in_service}."
    )
    return {
        "summary": summary,
        "unit_count": unit_count,
        "busbar_switch_indices": tuple(busbar_switch_indices),
        "transformer_switch_indices": tuple(transformer_switch_indices),
        "busbar_switches_closed": busbar_closed,
        "transformer_switches_closed": trafo_switches_closed,
        "equal_tap_positions": equal_taps,
        "selected_transformers_in_service": in_service,
    }, blockers


def _raw_mva_reporting_fields() -> tuple[dict[str, object], ...]:
    return (
        {
            "field": "raw_import_mva",
            "unit": "MVA",
            "meaning": "un-normalized import-direction apparent power at the decision transformer",
        },
        {
            "field": "raw_export_mva",
            "unit": "MVA",
            "meaning": "un-normalized export-direction apparent power at the decision transformer, reported separately from the primary import event",
        },
        {
            "field": "loading_total_nameplate_pu",
            "denominator_field": "total_nameplate_kva",
            "meaning": "raw MVA divided by aggregate installed selected-unit nameplate",
        },
        {
            "field": "loading_firm_n_minus_1_pu",
            "denominator_field": "firm_n_minus_1_nameplate_kva",
            "meaning": "raw MVA divided by largest-unit-out firm nameplate; diagnostic until PI selects and AC-validates firm use",
        },
    )


def _require_table(net: Any, table_name: str) -> pd.DataFrame:
    table = getattr(net, table_name, None)
    if table is None or not isinstance(table, pd.DataFrame):
        raise ValueError(f"pandapower net must contain DataFrame table {table_name!r}")
    return table


def _blocker(code: str, blocker_id: str, message: str) -> dict[str, object]:
    return {"code": code, "blocker_ids": (blocker_id,), "message": message}


def _exact_nonnegative_integer_tuple(values: Sequence[object], *, name: str) -> tuple[int, ...]:
    result: list[int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
            raise TypeError(f"{name} must contain exact nonnegative integers")
        integer = int(value)
        if integer < 0:
            raise ValueError(f"{name} must contain exact nonnegative integers")
        result.append(integer)
    return tuple(result)


def _require_nonempty_text(value: str, *, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _validate_metadata(mapping: Mapping[str, object], *, name: str) -> None:
    for key, value in mapping.items():
        _require_nonempty_text(str(key), name=f"{name} key")
        if value is None:
            raise ValueError(f"{name} values must not be None")
        if isinstance(value, str) and not value:
            raise ValueError(f"{name} string values must be non-empty")


def _string_or_empty(value: object) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return str(value)


def _json_scalar(value: object) -> object:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value