from __future__ import annotations

import pandas as pd
import pytest

from src.evaluator_capacity import (
    FIRM_OUTAGE_CONVENTION,
    PENDING_CAPACITY_CONVENTION_STATUS,
    RAW_MVA_REPORT_CONVENTIONS,
    CapacityProvenanceConfig,
    collect_capacity_provenance,
)


class FakeNet:
    def __init__(self, *, busbar_closed: bool = True, tap_positions: tuple[int, int] = (0, 0)) -> None:
        self.trafo = pd.DataFrame(
            {
                "name": ["T1", "T2"],
                "hv_bus": [0, 1],
                "lv_bus": [2, 3],
                "sn_mva": [40.0, 40.0],
                "parallel": [1, 1],
                "tap_pos": list(tap_positions),
                "in_service": [True, True],
            },
            index=[0, 1],
        )
        self.switch = pd.DataFrame(
            {
                "bus": [0, 2, 0, 2, 1, 3],
                "element": [1, 3, 0, 0, 1, 1],
                "et": ["b", "b", "t", "t", "t", "t"],
                "closed": [True, busbar_closed, True, True, True, True],
                "type": ["CB"] * 6,
                "name": [
                    "HV bus tie",
                    "MV bus tie",
                    "T1 HV CB",
                    "T1 MV CB",
                    "T2 HV CB",
                    "T2 MV CB",
                ],
            },
            index=[0, 5, 1, 2, 3, 4],
        )


def _config() -> CapacityProvenanceConfig:
    return CapacityProvenanceConfig(
        grid_key="simbench_semiurb",
        grid_code="1-MV-semiurb--0-sw",
        decision_transformer_indices=(0, 1),
        busbar_switch_indices=(0, 5),
        transformer_switch_indices=(1, 2, 3, 4),
        supporting_evidence_paths=("reports/grid_inventory.md",),
    )


def test_collect_capacity_provenance_reports_total_and_firm_without_choice() -> None:
    packet = collect_capacity_provenance(FakeNet(), _config())
    record = packet.capacity_provenance

    assert packet.ready_for_e3_s2b_capacity_prerun is True
    assert packet.blocker_manifest["items"] == ()
    assert record["convention_status"] == PENDING_CAPACITY_CONVENTION_STATUS
    assert record["transformer_indices"] == (0, 1)
    assert record["unit_nameplate_kva"] == (40000.0, 40000.0)
    assert record["total_nameplate_kva"] == 80000.0
    assert record["firm_n_minus_1_nameplate_kva"] == 40000.0
    assert record["firm_outage_convention"] == FIRM_OUTAGE_CONVENTION
    assert record["raw_mva_report_conventions"] == RAW_MVA_REPORT_CONVENTIONS
    assert record["metadata"]["total_vs_firm_decision_status"] == "pending_pi_decision_after_e3_s2b_screen"
    assert record["metadata"]["firm_primary_requires_actual_one_transformer_out_ac_validation"] is True
    assert packet.transformer_records[0]["sn_mva"] == 40.0
    assert "P(E)" in packet.non_claims[1]


def test_collect_capacity_provenance_fails_closed_on_open_bus_tie() -> None:
    packet = collect_capacity_provenance(FakeNet(busbar_closed=False), _config())

    assert packet.ready_for_e3_s2b_capacity_prerun is False
    codes = {item["code"] for item in packet.blocker_manifest["items"]}
    assert "switch_open" in codes
    assert "busbar_tie_not_closed" in codes


def test_collect_capacity_provenance_fails_closed_on_tap_mismatch() -> None:
    packet = collect_capacity_provenance(FakeNet(tap_positions=(0, 1)), _config())

    assert packet.ready_for_e3_s2b_capacity_prerun is False
    codes = {item["code"] for item in packet.blocker_manifest["items"]}
    assert "tap_positions_differ" in codes


@pytest.mark.parametrize(
    "bad_index",
    [True, 1.2, "1"],
)
def test_capacity_config_rejects_non_integral_transformer_indices(bad_index: object) -> None:
    with pytest.raises((TypeError, ValueError), match="exact nonnegative integers"):
        CapacityProvenanceConfig(
            grid_key="simbench_semiurb",
            grid_code="1-MV-semiurb--0-sw",
            decision_transformer_indices=(bad_index,),
            busbar_switch_indices=(0,),
            transformer_switch_indices=(1,),
        )


def test_collect_capacity_provenance_reports_missing_rating_as_blocker() -> None:
    net = FakeNet()
    net.trafo.loc[1, "sn_mva"] = 0.0

    packet = collect_capacity_provenance(net, _config())

    assert packet.ready_for_e3_s2b_capacity_prerun is False
    codes = {item["code"] for item in packet.blocker_manifest["items"]}
    assert "transformer_nameplate_invalid" in codes