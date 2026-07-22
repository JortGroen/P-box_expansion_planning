from __future__ import annotations

import numpy as np
import pytest

from src.contracts.net_load import (
    AdapterBackedNetLoadProvider,
    ComponentAdapterRegistry,
    ComponentAdapterOutput,
    ComponentAdapterSkeleton,
    ComponentProvenance,
    DEFAULT_REALIZATION_COMPONENTS,
    NetLoadAssemblyPlan,
    NetLoadComponent,
    NetLoadProvider,
    NetLoadResult,
    REAL_COMPONENT_WIRING_KINDS,
    assemble_net_load_from_adapter_outputs,
    assemble_net_load_from_components,
    assemble_net_load_from_real_component_outputs,
    assemble_net_load_from_registry_outputs,
    build_ic1_assembly_plan_from_registry,
    build_realization_context,
    build_net_load_result,
    net_load_component_from_adapter_output,
    validate_component_adapter_skeletons,
    validate_net_load_result,
    validate_real_component_adapter_readiness,
)
from src.contracts.loading_trajectory import TimeDomain


def _calendar() -> np.ndarray:
    return np.array(
        [
            "2035-01-01T00:00:00",
            "2035-01-01T00:15:00",
            "2035-01-01T00:30:00",
            "2035-01-01T00:45:00",
        ],
        dtype="datetime64[s]",
    )


def _component(
    component_id: str,
    kind: str,
    p_kw: list[float],
    *,
    node_id: str = "node-1",
    member_id: str | None = None,
    source_id: str | None = None,
    shared_weather_driver_id: str | None = None,
    timestamps: np.ndarray | None = None,
) -> NetLoadComponent:
    return NetLoadComponent(
        provenance=ComponentProvenance(
            component_id=component_id,
            kind=kind,
            node_id=node_id,
            member_id=member_id,
            source_id=source_id,
            shared_weather_driver_id=shared_weather_driver_id,
            metadata={"synthetic": True},
        ),
        p_kw=np.array(p_kw, dtype=float),
        q_kvar=np.zeros(4, dtype=float),
        timestamps=_calendar() if timestamps is None else timestamps,
    )


def _integration_components() -> list[NetLoadComponent]:
    return [
        _component("base-a", "baseline", [10.0, 11.0, 12.0, 13.0], node_id="node-a", member_id="simbench-a"),
        _component("ev-a", "ev", [1.0, 2.0, 3.0, 4.0], node_id="node-a", member_id="ev-7"),
        _component("hp-b", "hp", [4.0, 5.0, 6.0, 7.0], node_id="node-b", member_id="hp-3", shared_weather_driver_id="weather-1"),
        _component("pv-b", "pv", [0.0, -2.0, -3.0, 0.0], node_id="node-b", member_id="pv-3", shared_weather_driver_id="weather-1"),
        _component("adoption-a", "adoption", [0.5, 0.5, 0.5, 0.5], node_id="node-a", member_id="adoption-2035"),
        _component("flex-a", "flexibility", [-0.2, -0.2, 0.0, 0.0], node_id="node-a", member_id="rho-0.5"),
    ]


def _realization_context():
    return build_realization_context(
        scenario="scenario-a",
        year=2035,
        time_domain="full_year",
        rho=0.5,
        seed=7001,
        calendar_metadata={"calendar_id": "synthetic-2035-15min"},
        mapping_version_metadata={"node_mapping_version": "synthetic-v1"},
    )


def _stream_id(context, component: str) -> str:
    return next(stream.stream_id for stream in context.component_streams if stream.component == component)


def _adapter_output(
    context,
    component_id: str,
    kind: str,
    p_kw: list[float],
    *,
    node_id: str = "node-a",
    q_kvar: list[float] | None = None,
    member_id: str | None = None,
    source_id: str | None = None,
    shared_weather_driver_id: str | None = None,
    timestamps: np.ndarray | None = None,
    stream_id: str | None = None,
    artifact_status: str = "synthetic_fixture",
) -> ComponentAdapterOutput:
    return ComponentAdapterOutput(
        component_id=component_id,
        kind=kind,
        node_id=node_id,
        p_kw=np.array(p_kw, dtype=float),
        q_kvar=np.zeros(4, dtype=float) if q_kvar is None else np.array(q_kvar, dtype=float),
        timestamps=_calendar() if timestamps is None else timestamps,
        member_id=member_id or f"{kind}-member",
        source_id=source_id or f"synthetic-{kind}-adapter",
        stream_id=stream_id or _stream_id(context, kind),
        shared_weather_driver_id=shared_weather_driver_id,
        metadata={"adapter": "synthetic", "artifact_status": artifact_status},
    )


def _adapter_outputs(context) -> list[ComponentAdapterOutput]:
    weather_id = context.shared_weather_driver_id
    return [
        _adapter_output(context, "baseline-a", "baseline", [10.0, 11.0, 12.0, 13.0], member_id="base-1"),
        _adapter_output(context, "ev-a", "ev", [1.0, 2.0, 3.0, 4.0], member_id="ev-1"),
        _adapter_output(
            context,
            "hp-b",
            "hp",
            [4.0, 5.0, 6.0, 7.0],
            node_id="node-b",
            member_id="hp-1",
            shared_weather_driver_id=weather_id,
        ),
        _adapter_output(
            context,
            "pv-b",
            "pv",
            [0.0, -2.0, -3.0, 0.0],
            node_id="node-b",
            member_id="pv-1",
            shared_weather_driver_id=weather_id,
        ),
        _adapter_output(context, "adoption-a", "adoption", [0.0, 0.0, 0.0, 0.0], member_id="adoption-1"),
        _adapter_output(context, "flex-a", "flexibility", [-0.2, -0.2, 0.0, 0.0], member_id="rho-0.5"),
    ]


def _adapter_skeletons(
    *,
    artifact_status: str = "scaffold",
    shared_weather_driver_id: str = "weather-placeholder-1",
) -> list[ComponentAdapterSkeleton]:
    blockers = () if artifact_status == "accepted" else ("awaiting accepted E2 artifact",)
    return [
        ComponentAdapterSkeleton(
            kind="baseline",
            artifact_status=artifact_status,
            source_id="baseline-readiness",
            member_id="baseline-member-placeholder",
            node_ids=("node-a", "node-b"),
            calendar_id="calendar-2035-15min",
            blocking_items=blockers,
            metadata={"readiness_artifact": "E2.S5"},
        ),
        ComponentAdapterSkeleton(
            kind="ev",
            artifact_status=artifact_status,
            source_id="ev-readiness",
            member_id="ev-member-placeholder",
            node_ids=("node-a",),
            calendar_id="calendar-2035-15min",
            blocking_items=blockers,
            metadata={"readiness_artifact": "E2.S2"},
        ),
        ComponentAdapterSkeleton(
            kind="hp",
            artifact_status=artifact_status,
            source_id="hp-readiness",
            member_id="hp-member-placeholder",
            node_ids=("node-b",),
            calendar_id="calendar-2035-15min",
            shared_weather_driver_id=shared_weather_driver_id,
            blocking_items=blockers,
            metadata={"readiness_artifact": "E2.S3"},
        ),
        ComponentAdapterSkeleton(
            kind="pv",
            artifact_status=artifact_status,
            source_id="weather-pv-readiness",
            member_id="pv-member-placeholder",
            node_ids=("node-b",),
            calendar_id="calendar-2035-15min",
            shared_weather_driver_id=shared_weather_driver_id,
            blocking_items=blockers,
            metadata={"readiness_artifact": "E2.S4"},
        ),
    ]


def _accepted_adapter_registry() -> ComponentAdapterRegistry:
    return ComponentAdapterRegistry(
        registry_id="synthetic-accepted-registry",
        node_ids=("node-a", "node-b"),
        skeletons=tuple(
            _adapter_skeletons(
                artifact_status="accepted",
                shared_weather_driver_id="weather-registry-1",
            )
        ),
        metadata={"mapping_version": "synthetic-v1"},
    )


def _registry_context(registry: ComponentAdapterRegistry):
    return build_realization_context(
        scenario="scenario-a",
        year=2035,
        time_domain="full_year",
        rho=0.5,
        seed=7001,
        shared_weather_driver_id=registry.manifest_record()["readiness"]["shared_weather_driver_id"],
        calendar_metadata={"calendar_id": "calendar-2035-15min"},
        mapping_version_metadata={"node_mapping_version": "synthetic-v1"},
    )


def _registry_adapter_output(
    context,
    skeleton: ComponentAdapterSkeleton,
    component_id: str,
    p_kw: list[float],
    *,
    node_id: str,
) -> ComponentAdapterOutput:
    return _adapter_output(
        context,
        component_id,
        skeleton.kind,
        p_kw,
        node_id=node_id,
        member_id=skeleton.member_id,
        source_id=skeleton.source_id,
        shared_weather_driver_id=(
            context.shared_weather_driver_id
            if skeleton.kind in {"hp", "pv"}
            else None
        ),
        artifact_status=skeleton.artifact_status,
    )


def _registry_adapter_outputs(context, registry: ComponentAdapterRegistry) -> list[ComponentAdapterOutput]:
    skeletons = {skeleton.kind: skeleton for skeleton in registry.skeletons}
    outputs = [
        _registry_adapter_output(
            context,
            skeletons["baseline"],
            "baseline-a",
            [10.0, 11.0, 12.0, 13.0],
            node_id="node-a",
        ),
        _registry_adapter_output(
            context,
            skeletons["ev"],
            "ev-a",
            [1.0, 2.0, 3.0, 4.0],
            node_id="node-a",
        ),
        _registry_adapter_output(
            context,
            skeletons["hp"],
            "hp-b",
            [4.0, 5.0, 6.0, 7.0],
            node_id="node-b",
        ),
        _registry_adapter_output(
            context,
            skeletons["pv"],
            "pv-b",
            [0.0, -2.0, -3.0, 0.0],
            node_id="node-b",
        ),
    ]
    return [
        ComponentAdapterOutput(
            component_id=output.component_id,
            kind=output.kind,
            node_id=output.node_id,
            p_kw=output.p_kw,
            q_kvar=output.q_kvar,
            timestamps=output.timestamps,
            member_id=output.member_id,
            source_id=output.source_id,
            stream_id=output.stream_id,
            shared_weather_driver_id=output.shared_weather_driver_id,
            metadata={**dict(output.metadata), "calendar_id": skeletons[output.kind].calendar_id},
        )
        for output in outputs
    ]


class _SyntheticNetLoadProvider:
    def get_net_load(
        self,
        scenario: str,
        year: int,
        time_domain: TimeDomain,
        rho: float,
        seed: int,
    ) -> NetLoadResult:
        if time_domain != "full_year":
            raise ValueError("synthetic fixture supports full_year only")
        weather_id = f"weather-{seed}"
        scale = 1.0 + (seed % 5) * 0.1
        return build_net_load_result(
            [
                _component(
                    f"baseline-{scenario}-{year}",
                    "baseline",
                    [10.0 * scale, 11.0 * scale, 12.0 * scale, 13.0 * scale],
                    member_id=f"baseline-member-{seed}",
                ),
                _component(
                    f"ev-{scenario}-{year}",
                    "ev",
                    [1.0 * scale, 2.0 * scale, 3.0 * scale, 4.0 * scale],
                    member_id=f"ev-member-{seed}",
                    source_id="synthetic-ev-fixture",
                ),
                _component(
                    f"hp-{scenario}-{year}",
                    "hp",
                    [3.0, 4.0, 5.0, 6.0],
                    member_id=f"hp-member-{seed}",
                    shared_weather_driver_id=weather_id,
                ),
                _component(
                    f"pv-{scenario}-{year}",
                    "pv",
                    [0.0, -2.0, -3.0, 0.0],
                    member_id=f"pv-member-{seed}",
                    shared_weather_driver_id=weather_id,
                ),
            ],
            metadata={"scenario": scenario, "year": year, "rho": rho, "seed": seed},
        )


class _SyntheticComponentAdapter:
    def __init__(
        self,
        *,
        kind: str,
        node_id: str,
        p_kw: list[float],
        component_id: str | None = None,
        weather_id: str | None = None,
        timestamps: np.ndarray | None = None,
    ) -> None:
        self.kind = kind
        self.node_id = node_id
        self.p_kw = p_kw
        self.component_id = component_id or f"{kind}-{node_id}"
        self.weather_id = weather_id
        self.timestamps = timestamps

    def get_component_outputs(self, context, node_ids) -> list[ComponentAdapterOutput]:
        if self.node_id not in node_ids:
            raise ValueError("synthetic adapter node_id must appear in node_ids")
        weather_id = self.weather_id
        if self.kind in {"hp", "pv"} and weather_id is None:
            weather_id = context.shared_weather_driver_id
        # Member IDs derive from the context to prove the provider passes one
        # auditable sample identity to every adapter without changing IC-1.
        return [
            _adapter_output(
                context,
                self.component_id,
                self.kind,
                self.p_kw,
                node_id=self.node_id,
                member_id=f"{self.kind}-member-{context.root_seed}",
                source_id=f"synthetic-{self.kind}-smoke",
                shared_weather_driver_id=weather_id,
                timestamps=self.timestamps,
            )
        ]


def _smoke_provider(*, weather_id: str | None = None, timestamps: np.ndarray | None = None) -> AdapterBackedNetLoadProvider:
    plan = NetLoadAssemblyPlan(node_ids=("node-a", "node-b"), metadata={"node_mapping": "smoke-v1"})
    return AdapterBackedNetLoadProvider(
        plan=plan,
        adapters=(
            _SyntheticComponentAdapter(kind="baseline", node_id="node-a", p_kw=[10.0, 11.0, 12.0, 13.0]),
            _SyntheticComponentAdapter(kind="ev", node_id="node-a", p_kw=[1.0, 2.0, 3.0, 4.0]),
            _SyntheticComponentAdapter(kind="hp", node_id="node-b", p_kw=[4.0, 5.0, 6.0, 7.0], weather_id=weather_id),
            _SyntheticComponentAdapter(kind="pv", node_id="node-b", p_kw=[0.0, -2.0, -3.0, 0.0], weather_id=weather_id),
            _SyntheticComponentAdapter(kind="adoption", node_id="node-a", p_kw=[0.0, 0.0, 0.0, 0.0]),
            _SyntheticComponentAdapter(kind="flexibility", node_id="node-a", p_kw=[-0.2, -0.2, 0.0, 0.0], timestamps=timestamps),
        ),
        calendar_metadata={"calendar_id": "smoke-2035-15min"},
        mapping_version_metadata={"node_mapping_version": "smoke-v1"},
        metadata={"scaffold_only": True},
    )


def test_same_synthetic_inputs_give_deterministic_output() -> None:
    components = [
        _component("base-a", "baseline", [10.0, 11.0, 12.0, 13.0], member_id="simbench-a"),
        _component("ev-a", "ev", [1.0, 2.0, 3.0, 4.0], member_id="ev-member-7"),
        _component("pv-a", "pv", [0.0, -5.0, -6.0, 0.0], member_id="pv-synthetic"),
    ]

    first = build_net_load_result(components, metadata={"scenario": "synthetic"})
    second = build_net_load_result(components, metadata={"scenario": "synthetic"})

    np.testing.assert_array_equal(first.p_net_kw, second.p_net_kw)
    np.testing.assert_array_equal(first.q_net_kvar, second.q_net_kvar)
    np.testing.assert_array_equal(first.timestamps, second.timestamps)
    assert first.node_ids == second.node_ids
    assert first.component_provenance == second.component_provenance
    np.testing.assert_array_equal(first.p_net_kw, np.array([[11.0, 8.0, 9.0, 17.0]]))


def test_net_load_provider_protocol_preserves_crn_and_member_traceability() -> None:
    provider: NetLoadProvider = _SyntheticNetLoadProvider()

    first = provider.get_net_load("synthetic", 2035, "full_year", rho=0.5, seed=17)
    second = provider.get_net_load("synthetic", 2035, "full_year", rho=0.5, seed=17)
    different_seed = provider.get_net_load("synthetic", 2035, "full_year", rho=0.5, seed=18)

    np.testing.assert_array_equal(first.p_net_kw, second.p_net_kw)
    np.testing.assert_array_equal(first.q_net_kvar, second.q_net_kvar)
    np.testing.assert_array_equal(first.timestamps, second.timestamps)
    assert first.component_provenance == second.component_provenance
    assert first.shared_weather_driver_ids == ("weather-17",)
    assert {item.member_id for item in first.component_provenance if item.kind == "ev"} == {"ev-member-17"}
    assert different_seed.shared_weather_driver_ids == ("weather-18",)
    assert not np.array_equal(first.p_net_kw, different_seed.p_net_kw)

    validate_net_load_result(first)


def test_realization_context_is_deterministic_and_manifestable_from_public_args() -> None:
    first = build_realization_context(
        scenario="scenario-a",
        year=2035,
        time_domain="full_year",
        rho=0.5,
        seed=140001,
        calendar_metadata={"calendar_id": "synthetic-2035-15min"},
        mapping_version_metadata={"node_mapping_version": "synthetic-v1"},
    )
    second = build_realization_context(
        scenario="scenario-a",
        year=2035,
        time_domain="full_year",
        rho=0.5,
        seed=140001,
        calendar_metadata={"calendar_id": "synthetic-2035-15min"},
        mapping_version_metadata={"node_mapping_version": "synthetic-v1"},
    )

    assert first == second
    assert first.scenario == "scenario-a"
    assert first.planning_year == 2035
    assert first.root_seed == 140001
    assert first.sample_index == 0
    assert first.shared_weather_driver_id.startswith("weather:sample_0:weather:seed_")
    assert {stream.component for stream in first.component_streams} == set(DEFAULT_REALIZATION_COMPONENTS)
    assert set(first.component_member_placeholders) == set(DEFAULT_REALIZATION_COMPONENTS)
    assert first.manifest_metadata()["aleatory_identity"] == second.manifest_metadata()["aleatory_identity"]


def test_realization_context_distinguishes_root_seed_and_sample_index() -> None:
    reference = build_realization_context(
        scenario="scenario-a",
        year=2035,
        time_domain="full_year",
        rho=0.0,
        seed=1,
    )
    different_root = build_realization_context(
        scenario="scenario-a",
        year=2035,
        time_domain="full_year",
        rho=0.0,
        seed=2,
    )
    different_sample = build_realization_context(
        scenario="scenario-a",
        year=2035,
        time_domain="full_year",
        rho=0.0,
        seed=1,
        sample_index=1,
    )

    assert reference.aleatory_identity() != different_root.aleatory_identity()
    assert reference.aleatory_identity() != different_sample.aleatory_identity()
    assert reference.shared_weather_driver_id != different_root.shared_weather_driver_id
    assert reference.shared_weather_driver_id != different_sample.shared_weather_driver_id


def test_realization_context_aleatory_identity_excludes_branch_like_labels() -> None:
    low_alpha = build_realization_context(
        scenario="scenario-a",
        year=2035,
        time_domain="full_year",
        rho=0.0,
        seed=7,
    )
    high_alpha = build_realization_context(
        scenario="scenario-a",
        year=2035,
        time_domain="full_year",
        rho=1.0,
        seed=7,
    )
    window_diagnostic = build_realization_context(
        scenario="scenario-a",
        year=2035,
        time_domain="window_set",
        rho=0.0,
        seed=7,
    )

    assert low_alpha.aleatory_identity() == high_alpha.aleatory_identity()
    assert low_alpha.aleatory_identity() == window_diagnostic.aleatory_identity()
    assert low_alpha.manifest_metadata()["rho"] == 0.0
    assert high_alpha.manifest_metadata()["rho"] == 1.0
    assert window_diagnostic.manifest_metadata()["time_domain"] == "window_set"


def test_realization_context_rejects_invalid_metadata_and_seed_inputs() -> None:
    with pytest.raises(ValueError, match="rho must be finite and in \\[0, 1\\]"):
        build_realization_context(
            scenario="scenario-a",
            year=2035,
            time_domain="full_year",
            rho=1.1,
            seed=1,
        )

    with pytest.raises(ValueError, match="root_seed must be non-negative"):
        build_realization_context(
            scenario="scenario-a",
            year=2035,
            time_domain="full_year",
            rho=0.5,
            seed=-1,
        )

    with pytest.raises(ValueError, match="component_names must not contain duplicates"):
        build_realization_context(
            scenario="scenario-a",
            year=2035,
            time_domain="full_year",
            rho=0.5,
            seed=1,
            component_names=("ev", "ev"),
        )

    with pytest.raises(ValueError, match="calendar_metadata values must not be None"):
        build_realization_context(
            scenario="scenario-a",
            year=2035,
            time_domain="full_year",
            rho=0.5,
            seed=1,
            calendar_metadata={"calendar_id": None},
        )

    with pytest.raises(ValueError, match="matching component streams"):
        build_realization_context(
            scenario="scenario-a",
            year=2035,
            time_domain="full_year",
            rho=0.5,
            seed=1,
            component_names=("ev",),
            component_member_placeholders={"ev": "pending:ev", "hp": "pending:hp"},
        )


def test_mismatched_calendars_are_rejected() -> None:
    shifted = _calendar().copy()
    shifted[2] = np.datetime64("2035-01-01T00:31:00")

    with pytest.raises(ValueError, match="complete 15-minute calendar"):
        _component("bad-calendar", "baseline", [1.0, 1.0, 1.0, 1.0], timestamps=shifted)

    later_calendar = _calendar() + np.timedelta64(15, "m")
    with pytest.raises(ValueError, match="same 15-minute calendar"):
        build_net_load_result(
            [
                _component("base-a", "baseline", [1.0, 1.0, 1.0, 1.0]),
                _component("ev-a", "ev", [1.0, 1.0, 1.0, 1.0], timestamps=later_calendar),
            ]
        )


def test_incomplete_or_nonfinite_trajectories_are_rejected() -> None:
    with pytest.raises(ValueError, match="p_kw must not be empty"):
        NetLoadComponent(
            provenance=ComponentProvenance("empty", "baseline", "node-1"),
            p_kw=np.array([], dtype=float),
            q_kvar=np.array([], dtype=float),
            timestamps=np.array([], dtype="datetime64[s]"),
        )

    with pytest.raises(ValueError, match="p_kw must contain only finite"):
        _component("nan-load", "ev", [1.0, np.nan, 2.0, 3.0])

    result = build_net_load_result([_component("base-a", "baseline", [1.0, 1.0, 1.0, 1.0])])
    result.p_net_kw[0, 0] = np.inf
    with pytest.raises(ValueError, match="net-load arrays must contain only finite"):
        validate_net_load_result(result)


def test_hp_and_pv_components_share_weather_driver_when_both_present() -> None:
    build_net_load_result(
        [
            _component("hp-a", "hp", [3.0, 4.0, 5.0, 6.0], shared_weather_driver_id="weather-17"),
            _component("pv-a", "pv", [0.0, -2.0, -3.0, 0.0], shared_weather_driver_id="weather-17"),
        ]
    )

    with pytest.raises(ValueError, match="HP and PV components must share"):
        build_net_load_result(
            [
                _component("hp-a", "hp", [3.0, 4.0, 5.0, 6.0], shared_weather_driver_id="weather-17"),
                _component("pv-a", "pv", [0.0, -2.0, -3.0, 0.0], shared_weather_driver_id="weather-18"),
            ]
        )

    with pytest.raises(ValueError, match="HP and PV components must share"):
        build_net_load_result(
            [
                _component("hp-a", "hp", [3.0, 4.0, 5.0, 6.0]),
                _component("pv-a", "pv", [0.0, -2.0, -3.0, 0.0], shared_weather_driver_id="weather-17"),
            ]
        )


def test_component_member_metadata_remains_traceable() -> None:
    result = build_net_load_result(
        [
            _component(
                "ev-home-001",
                "ev",
                [1.0, 1.5, 2.0, 2.5],
                node_id="node-ev",
                member_id="elaad-member-42",
                source_id="EV-004-home-cp",
            ),
            _component(
                "flex-ev-home-001",
                "flexibility",
                [-0.2, -0.2, 0.0, 0.0],
                node_id="node-ev",
                member_id="rho-0.5",
                source_id="FLEX-001",
            ),
        ],
        metadata={"scenario": "synthetic", "year": 2035},
    )

    assert result.node_ids == ("node-ev",)
    assert result.metadata["year"] == 2035
    ev_provenance = result.component_provenance[0]
    assert ev_provenance.component_id == "ev-home-001"
    assert ev_provenance.member_id == "elaad-member-42"
    assert ev_provenance.source_id == "EV-004-home-cp"
    assert ev_provenance.metadata["synthetic"] is True
    np.testing.assert_array_equal(result.p_net_kw, np.array([[0.8, 1.3, 2.0, 2.5]]))


def test_integration_harness_assembles_all_component_families_in_plan_node_order() -> None:
    plan = NetLoadAssemblyPlan(node_ids=("node-b", "node-a"), metadata={"scenario": "synthetic-2035"})

    result = assemble_net_load_from_components(
        plan,
        _integration_components(),
        metadata={"rho": 0.5},
    )

    assert result.node_ids == ("node-b", "node-a")
    assert result.metadata["assembly"] == "synthetic_ic1_harness"
    assert result.metadata["scenario"] == "synthetic-2035"
    assert result.metadata["rho"] == 0.5
    assert result.shared_weather_driver_ids == ("weather-1",)
    np.testing.assert_array_equal(result.timestamps, _calendar())
    np.testing.assert_array_equal(
        result.p_net_kw,
        np.array(
            [
                [4.0, 3.0, 3.0, 7.0],
                [11.3, 13.3, 15.5, 17.5],
            ]
        ),
    )


def test_integration_harness_rejects_missing_required_component_family() -> None:
    plan = NetLoadAssemblyPlan(node_ids=("node-a", "node-b"))
    components = [
        component
        for component in _integration_components()
        if component.provenance.kind != "adoption"
    ]

    with pytest.raises(ValueError, match="missing required component kind\\(s\\): adoption"):
        assemble_net_load_from_components(plan, components)


def test_integration_harness_rejects_duplicate_or_unknown_nodes() -> None:
    with pytest.raises(ValueError, match="node_ids must not contain duplicates"):
        NetLoadAssemblyPlan(node_ids=("node-a", "node-a"))

    plan = NetLoadAssemblyPlan(node_ids=("node-a", "node-b"))
    components = _integration_components()
    components[0] = _component("base-z", "baseline", [1.0, 1.0, 1.0, 1.0], node_id="node-z")

    with pytest.raises(ValueError, match="component node_id must appear"):
        assemble_net_load_from_components(plan, components)


def test_integration_harness_rejects_calendar_and_weather_mismatches() -> None:
    plan = NetLoadAssemblyPlan(node_ids=("node-a", "node-b"))
    shifted = _calendar() + np.timedelta64(15, "m")
    components = _integration_components()
    components[1] = _component("ev-shifted", "ev", [1.0, 2.0, 3.0, 4.0], node_id="node-a", timestamps=shifted)

    with pytest.raises(ValueError, match="same 15-minute calendar"):
        assemble_net_load_from_components(plan, components)

    components = _integration_components()
    components[3] = _component(
        "pv-b",
        "pv",
        [0.0, -2.0, -3.0, 0.0],
        node_id="node-b",
        shared_weather_driver_id="weather-2",
    )
    with pytest.raises(ValueError, match="HP and PV components must share"):
        assemble_net_load_from_components(plan, components)


def test_component_adapter_output_converts_through_realization_context() -> None:
    context = _realization_context()
    output = _adapter_output(
        context,
        "ev-a",
        "ev",
        [1.0, 2.0, 3.0, 4.0],
        member_id="ev-member-1",
        source_id="EV-004-synthetic",
    )

    component = net_load_component_from_adapter_output(output, context)

    assert component.provenance.component_id == "ev-a"
    assert component.provenance.kind == "ev"
    assert component.provenance.member_id == "ev-member-1"
    assert component.provenance.source_id == "EV-004-synthetic"
    assert component.provenance.metadata["realization_stream_id"] == _stream_id(context, "ev")
    assert isinstance(component.provenance.metadata["realization_component_seed"], int)
    np.testing.assert_array_equal(component.p_kw, np.array([1.0, 2.0, 3.0, 4.0]))


def test_component_adapter_boundary_assembles_synthetic_components_deterministically() -> None:
    context = _realization_context()
    plan = NetLoadAssemblyPlan(node_ids=("node-b", "node-a"), metadata={"mapping": "synthetic-v1"})

    first = assemble_net_load_from_adapter_outputs(
        plan,
        context,
        _adapter_outputs(context),
        metadata={"scaffold_only": True},
    )
    second = assemble_net_load_from_adapter_outputs(
        plan,
        context,
        _adapter_outputs(context),
        metadata={"scaffold_only": True},
    )

    np.testing.assert_array_equal(first.p_net_kw, second.p_net_kw)
    np.testing.assert_array_equal(first.q_net_kvar, second.q_net_kvar)
    assert first.metadata["assembly"] == "component_adapter_boundary_scaffold"
    assert first.metadata["scaffold_only"] is True
    assert first.metadata["realization_context"]["aleatory_identity"] == context.aleatory_identity()
    assert first.shared_weather_driver_ids == (context.shared_weather_driver_id,)
    assert {item.kind for item in first.component_provenance} == set(DEFAULT_REALIZATION_COMPONENTS)
    np.testing.assert_array_equal(
        first.p_net_kw,
        np.array(
            [
                [4.0, 3.0, 3.0, 7.0],
                [10.8, 12.8, 15.0, 17.0],
            ]
        ),
    )


def test_component_adapter_boundary_rejects_wrong_context_stream() -> None:
    context = _realization_context()
    other_context = build_realization_context(
        scenario="scenario-a",
        year=2035,
        time_domain="full_year",
        rho=0.5,
        seed=7002,
    )
    output = _adapter_output(
        context,
        "ev-a",
        "ev",
        [1.0, 2.0, 3.0, 4.0],
        stream_id=_stream_id(other_context, "ev"),
    )

    with pytest.raises(ValueError, match="stream_id must match"):
        net_load_component_from_adapter_output(output, context)


def test_component_adapter_boundary_rejects_unknown_or_duplicate_outputs() -> None:
    context = _realization_context()
    plan = NetLoadAssemblyPlan(node_ids=("node-a", "node-b"))

    with pytest.raises(ValueError, match="matching realization component stream"):
        net_load_component_from_adapter_output(
            _adapter_output(context, "other-a", "other", [1.0, 1.0, 1.0, 1.0], stream_id="other-stream"),
            context,
        )

    outputs = _adapter_outputs(context)
    outputs[1] = _adapter_output(context, "baseline-a", "ev", [1.0, 2.0, 3.0, 4.0])
    with pytest.raises(ValueError, match="component_id values must be unique"):
        assemble_net_load_from_adapter_outputs(plan, context, outputs)


def test_component_adapter_boundary_preserves_calendar_node_and_weather_failures() -> None:
    context = _realization_context()
    plan = NetLoadAssemblyPlan(node_ids=("node-a", "node-b"))
    shifted = _calendar() + np.timedelta64(15, "m")
    outputs = _adapter_outputs(context)
    outputs[1] = _adapter_output(context, "ev-shifted", "ev", [1.0, 2.0, 3.0, 4.0], timestamps=shifted)

    with pytest.raises(ValueError, match="same 15-minute calendar"):
        assemble_net_load_from_adapter_outputs(plan, context, outputs)

    outputs = _adapter_outputs(context)
    outputs[0] = _adapter_output(context, "baseline-z", "baseline", [1.0, 1.0, 1.0, 1.0], node_id="node-z")
    with pytest.raises(ValueError, match="component node_id must appear"):
        assemble_net_load_from_adapter_outputs(plan, context, outputs)

    outputs = _adapter_outputs(context)
    outputs[3] = _adapter_output(
        context,
        "pv-b",
        "pv",
        [0.0, -2.0, -3.0, 0.0],
        node_id="node-b",
        shared_weather_driver_id="different-weather",
    )
    with pytest.raises(ValueError, match="context shared_weather_driver_id"):
        assemble_net_load_from_adapter_outputs(plan, context, outputs)


def test_component_adapter_boundary_rejects_shared_non_context_weather_id() -> None:
    context = _realization_context()
    plan = NetLoadAssemblyPlan(node_ids=("node-a", "node-b"))
    outputs = _adapter_outputs(context)
    outputs[2] = _adapter_output(
        context,
        "hp-b",
        "hp",
        [4.0, 5.0, 6.0, 7.0],
        node_id="node-b",
        shared_weather_driver_id="same-but-not-context",
    )
    outputs[3] = _adapter_output(
        context,
        "pv-b",
        "pv",
        [0.0, -2.0, -3.0, 0.0],
        node_id="node-b",
        shared_weather_driver_id="same-but-not-context",
    )

    with pytest.raises(ValueError, match="context shared_weather_driver_id"):
        assemble_net_load_from_adapter_outputs(plan, context, outputs)


def test_adapter_backed_provider_smoke_harness_is_deterministic_for_same_seed() -> None:
    provider: NetLoadProvider = _smoke_provider()

    first = provider.get_net_load("smoke", 2035, "full_year", rho=0.25, seed=9001)
    second = provider.get_net_load("smoke", 2035, "full_year", rho=0.25, seed=9001)
    different_seed = provider.get_net_load("smoke", 2035, "full_year", rho=0.25, seed=9002)

    np.testing.assert_array_equal(first.p_net_kw, second.p_net_kw)
    np.testing.assert_array_equal(first.q_net_kvar, second.q_net_kvar)
    np.testing.assert_array_equal(first.timestamps, second.timestamps)
    assert first.component_provenance == second.component_provenance
    assert first.metadata["provider"] == "adapter_backed_smoke_harness"
    assert first.metadata["scaffold_only"] is True
    assert first.metadata["realization_context"]["aleatory_identity"]["root_seed"] == 9001
    assert first.metadata["realization_context"]["aleatory_identity"] != different_seed.metadata["realization_context"]["aleatory_identity"]


def test_adapter_backed_provider_smoke_harness_preserves_calendar_and_provenance() -> None:
    result = _smoke_provider().get_net_load("smoke", 2035, "full_year", rho=0.25, seed=9001)

    assert result.node_ids == ("node-a", "node-b")
    np.testing.assert_array_equal(result.timestamps, _calendar())
    assert {item.kind for item in result.component_provenance} == set(DEFAULT_REALIZATION_COMPONENTS)
    assert {item.member_id for item in result.component_provenance if item.kind == "ev"} == {"ev-member-9001"}
    ev_provenance = next(item for item in result.component_provenance if item.kind == "ev")
    assert ev_provenance.source_id == "synthetic-ev-smoke"
    assert ev_provenance.metadata["realization_stream_id"].startswith("sample_0:ev:seed_")
    np.testing.assert_array_equal(
        result.p_net_kw,
        np.array(
            [
                [10.8, 12.8, 15.0, 17.0],
                [4.0, 3.0, 3.0, 7.0],
            ]
        ),
    )


def test_adapter_backed_provider_smoke_harness_rejects_calendar_mismatch() -> None:
    shifted = _calendar() + np.timedelta64(15, "m")
    provider = _smoke_provider(timestamps=shifted)

    with pytest.raises(ValueError, match="same 15-minute calendar"):
        provider.get_net_load("smoke", 2035, "full_year", rho=0.25, seed=9001)


def test_adapter_backed_provider_smoke_harness_enforces_context_weather_identity() -> None:
    provider = _smoke_provider(weather_id="same-but-not-context")

    with pytest.raises(ValueError, match="context shared_weather_driver_id"):
        provider.get_net_load("smoke", 2035, "full_year", rho=0.25, seed=9001)


def test_real_component_readiness_records_required_artifact_statuses() -> None:
    context = _realization_context()
    readiness = validate_real_component_adapter_readiness(_adapter_outputs(context))

    assert readiness["required_real_component_kinds"] == REAL_COMPONENT_WIRING_KINDS
    assert readiness["present_component_kinds"] == (
        "adoption",
        "baseline",
        "ev",
        "flexibility",
        "hp",
        "pv",
    )
    assert readiness["artifact_status_by_component_id"]["baseline-a"] == "synthetic_fixture"
    assert readiness["artifact_status_by_component_id"]["hp-b"] == "synthetic_fixture"


def test_real_component_readiness_assembles_into_ic1_without_event_analysis() -> None:
    context = _realization_context()
    plan = NetLoadAssemblyPlan(node_ids=("node-b", "node-a"), metadata={"mapping": "real-readiness-v1"})

    result = assemble_net_load_from_real_component_outputs(
        plan,
        context,
        _adapter_outputs(context),
        metadata={"scaffold_only": True},
    )

    assert result.metadata["assembly"] == "component_adapter_boundary_scaffold"
    assert result.metadata["scaffold_only"] is True
    readiness = result.metadata["real_component_wiring"]
    assert readiness["required_real_component_kinds"] == REAL_COMPONENT_WIRING_KINDS
    assert readiness["artifact_status_by_component_id"]["pv-b"] == "synthetic_fixture"
    assert "threshold_pu" not in result.metadata
    assert "overload" not in result.metadata
    assert result.shared_weather_driver_ids == (context.shared_weather_driver_id,)
    np.testing.assert_array_equal(
        result.p_net_kw,
        np.array(
            [
                [4.0, 3.0, 3.0, 7.0],
                [10.8, 12.8, 15.0, 17.0],
            ]
        ),
    )


def test_real_component_readiness_rejects_missing_required_real_kind() -> None:
    context = _realization_context()
    outputs = [
        output
        for output in _adapter_outputs(context)
        if output.kind != "hp"
    ]

    with pytest.raises(ValueError, match="missing real-component adapter output kind\\(s\\): hp"):
        validate_real_component_adapter_readiness(outputs)


def test_real_component_readiness_rejects_missing_or_unknown_artifact_status() -> None:
    context = _realization_context()
    outputs = _adapter_outputs(context)
    outputs[0] = _adapter_output(
        context,
        "baseline-a",
        "baseline",
        [10.0, 11.0, 12.0, 13.0],
        artifact_status="candidate_only",
    )

    with pytest.raises(ValueError, match="valid artifact_status"):
        validate_real_component_adapter_readiness(outputs)


def test_metadata_adapter_skeletons_record_scaffold_readiness_without_arrays() -> None:
    readiness = validate_component_adapter_skeletons(_adapter_skeletons())

    assert readiness["required_component_kinds"] == REAL_COMPONENT_WIRING_KINDS
    assert readiness["present_component_kinds"] == ("baseline", "ev", "hp", "pv")
    assert readiness["ready_for_real_arrays"] is False
    assert readiness["artifact_status_by_kind"]["ev"] == "scaffold"
    assert readiness["blocking_items_by_kind"]["baseline"] == ("awaiting accepted E2 artifact",)
    assert readiness["shared_weather_driver_id"] == "weather-placeholder-1"
    assert readiness["skeletons"][0]["kind"] == "baseline"


def test_metadata_adapter_skeletons_can_mark_all_required_real_components_accepted() -> None:
    readiness = validate_component_adapter_skeletons(
        _adapter_skeletons(artifact_status="accepted")
    )

    assert readiness["ready_for_real_arrays"] is True
    assert readiness["blocking_items_by_kind"] == {}
    assert set(readiness["artifact_status_by_kind"].values()) == {"accepted"}


def test_metadata_adapter_skeletons_reject_missing_or_duplicate_required_kind() -> None:
    with pytest.raises(ValueError, match="missing component adapter skeleton kind\\(s\\): ev"):
        validate_component_adapter_skeletons(
            [skeleton for skeleton in _adapter_skeletons() if skeleton.kind != "ev"]
        )

    duplicate = _adapter_skeletons()
    duplicate.append(duplicate[0])
    with pytest.raises(ValueError, match="skeleton kinds must be unique"):
        validate_component_adapter_skeletons(duplicate)


def test_metadata_adapter_skeletons_reject_mismatched_calendar_id() -> None:
    skeletons = _adapter_skeletons()
    skeletons[1] = ComponentAdapterSkeleton(
        kind="ev",
        artifact_status="scaffold",
        source_id="ev-readiness",
        member_id="ev-member-placeholder",
        node_ids=("node-a",),
        calendar_id="different-calendar",
        blocking_items=("awaiting accepted E2 artifact",),
        metadata={"readiness_artifact": "E2.S2"},
    )

    with pytest.raises(ValueError, match="share one calendar_id"):
        validate_component_adapter_skeletons(skeletons)


def test_metadata_adapter_skeletons_enforce_weather_cadence_and_blocker_rules() -> None:
    with pytest.raises(ValueError, match="shared_weather_driver_id"):
        ComponentAdapterSkeleton(
            kind="hp",
            artifact_status="scaffold",
            source_id="hp-readiness",
            member_id="hp-member",
            node_ids=("node-b",),
            calendar_id="calendar-2035-15min",
        )

    skeletons = _adapter_skeletons()
    skeletons[3] = ComponentAdapterSkeleton(
        kind="pv",
        artifact_status="scaffold",
        source_id="weather-pv-readiness",
        member_id="pv-member-placeholder",
        node_ids=("node-b",),
        calendar_id="calendar-2035-15min",
        shared_weather_driver_id="different-weather",
        blocking_items=("awaiting accepted E2 artifact",),
    )
    with pytest.raises(ValueError, match="HP and PV adapter skeletons must share"):
        validate_component_adapter_skeletons(skeletons)

    with pytest.raises(ValueError, match="900-second"):
        ComponentAdapterSkeleton(
            kind="baseline",
            artifact_status="scaffold",
            source_id="baseline-readiness",
            member_id="baseline-member",
            node_ids=("node-a",),
            calendar_id="calendar-2035-15min",
            timestep_seconds=1800,
            blocking_items=("awaiting accepted E2 artifact",),
        )

    with pytest.raises(ValueError, match="accepted adapter skeletons must not list"):
        ComponentAdapterSkeleton(
            kind="ev",
            artifact_status="accepted",
            source_id="ev-readiness",
            member_id="ev-member",
            node_ids=("node-a",),
            calendar_id="calendar-2035-15min",
            blocking_items=("should not remain",),
        )


def test_adapter_registry_builds_manifestable_ic1_assembly_plan_from_accepted_metadata() -> None:
    registry = _accepted_adapter_registry()
    plan = build_ic1_assembly_plan_from_registry(registry)

    assert plan.node_ids == ("node-a", "node-b")
    assert plan.required_component_kinds == REAL_COMPONENT_WIRING_KINDS
    assert plan.metadata["assembly"] == "ic1_adapter_registry_readiness"
    manifest = plan.metadata["adapter_registry"]
    assert manifest["registry_id"] == "synthetic-accepted-registry"
    assert manifest["readiness"]["ready_for_real_arrays"] is True
    assert manifest["readiness"]["calendar_id_by_kind"]["hp"] == "calendar-2035-15min"
    assert manifest["readiness"]["shared_weather_driver_id"] == "weather-registry-1"


def test_adapter_registry_assembles_synthetic_outputs_without_event_analysis() -> None:
    registry = _accepted_adapter_registry()
    context = _registry_context(registry)
    result = assemble_net_load_from_registry_outputs(
        registry,
        context,
        _registry_adapter_outputs(context, registry),
        metadata={"dry_run": True},
    )

    assert result.metadata["assembly"] == "component_adapter_boundary_scaffold"
    assert result.metadata["scaffold_only"] is True
    assert result.metadata["dry_run"] is True
    assert result.metadata["adapter_registry"]["registry_id"] == registry.registry_id
    assert result.shared_weather_driver_ids == ("weather-registry-1",)
    assert "threshold_pu" not in result.metadata
    assert "overload" not in result.metadata
    np.testing.assert_array_equal(
        result.p_net_kw,
        np.array(
            [
                [11.0, 13.0, 15.0, 17.0],
                [4.0, 3.0, 3.0, 7.0],
            ]
        ),
    )


def test_adapter_registry_rejects_unaccepted_or_misaligned_metadata() -> None:
    with pytest.raises(ValueError, match="requires accepted component metadata"):
        ComponentAdapterRegistry(
            registry_id="not-ready",
            node_ids=("node-a", "node-b"),
            skeletons=tuple(_adapter_skeletons()),
        )

    with pytest.raises(ValueError, match="missing from registry node_ids"):
        ComponentAdapterRegistry(
            registry_id="missing-node",
            node_ids=("node-a",),
            skeletons=tuple(_adapter_skeletons(artifact_status="accepted")),
        )


def test_adapter_registry_rejects_output_metadata_drift_before_assembly() -> None:
    registry = _accepted_adapter_registry()
    context = _registry_context(registry)
    outputs = _registry_adapter_outputs(context, registry)
    outputs[1] = ComponentAdapterOutput(
        component_id=outputs[1].component_id,
        kind=outputs[1].kind,
        node_id=outputs[1].node_id,
        p_kw=outputs[1].p_kw,
        q_kvar=outputs[1].q_kvar,
        timestamps=outputs[1].timestamps,
        member_id="different-ev-member",
        source_id=outputs[1].source_id,
        stream_id=outputs[1].stream_id,
        metadata=dict(outputs[1].metadata),
    )

    with pytest.raises(ValueError, match="member_id must match"):
        assemble_net_load_from_registry_outputs(registry, context, outputs)

    outputs = _registry_adapter_outputs(context, registry)
    outputs[0] = ComponentAdapterOutput(
        component_id=outputs[0].component_id,
        kind=outputs[0].kind,
        node_id=outputs[0].node_id,
        p_kw=outputs[0].p_kw,
        q_kvar=outputs[0].q_kvar,
        timestamps=outputs[0].timestamps,
        member_id=outputs[0].member_id,
        source_id=outputs[0].source_id,
        stream_id=outputs[0].stream_id,
        metadata={**dict(outputs[0].metadata), "calendar_id": "different-calendar"},
    )
    with pytest.raises(ValueError, match="calendar_id must match"):
        assemble_net_load_from_registry_outputs(registry, context, outputs)

    wrong_weather_context = build_realization_context(
        scenario="scenario-a",
        year=2035,
        time_domain="full_year",
        rho=0.5,
        seed=7001,
        shared_weather_driver_id="different-weather",
    )
    with pytest.raises(ValueError, match="weather identity must match"):
        assemble_net_load_from_registry_outputs(
            registry,
            wrong_weather_context,
            _registry_adapter_outputs(context, registry),
        )
