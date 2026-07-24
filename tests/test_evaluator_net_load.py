from __future__ import annotations

import numpy as np
import pytest

from src.contracts.net_load import (
    AdapterBackedNetLoadProvider,
    AcceptedComponentAdapterArtifact,
    ComponentAdapterRegistry,
    ComponentAdapterOutput,
    ComponentAdapterSkeleton,
    ExecutableInputArtifact,
    FutureLayerScreenPreflightConfig,
    GatedAdapterBackedNetLoadProvider,
    ComponentProvenance,
    DEFAULT_REALIZATION_COMPONENTS,
    NetLoadAssemblyPlan,
    NetLoadComponent,
    NetLoadLoadingInputReadiness,
    NetLoadProvider,
    NetLoadResult,
    REAL_COMPONENT_WIRING_KINDS,
    assemble_net_load_from_adapter_outputs,
    assemble_net_load_from_components,
    assemble_net_load_from_real_component_outputs,
    assemble_net_load_from_registry_outputs,
    build_ic1_assembly_plan_from_registry,
    build_component_adapter_registry_from_artifacts,
    build_realization_context,
    build_executable_loading_bridge_preflight,
    build_net_load_result,
    dry_run_integrated_input_preflight,
    net_load_component_from_adapter_output,
    prepare_loading_input_from_registry_outputs,
    prepare_executable_net_load_assembly_from_artifacts,
    validate_component_adapter_skeletons,
    validate_net_load_result,
    validate_real_component_adapter_readiness,
    validate_registry_adapter_output_readiness,
    validate_executable_input_gate,
    validate_future_layer_screen_preflight,
)
from src.contracts.loading_trajectory import LoadingTrajectoryPreRunConfig, TimeDomain
from reports.e3_s2_generate_executable_readiness_preflight import _component_groups, _table_rows


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


def _registry_context(registry: ComponentAdapterRegistry, *, time_domain: TimeDomain = "full_year"):
    return build_realization_context(
        scenario="scenario-a",
        year=2035,
        time_domain=time_domain,
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



def test_registry_output_readiness_records_manifestable_component_metadata() -> None:
    registry = _accepted_adapter_registry()
    context = _registry_context(registry)
    readiness = validate_registry_adapter_output_readiness(
        registry,
        context,
        _registry_adapter_outputs(context, registry),
    )

    assert readiness["registry_id"] == registry.registry_id
    assert readiness["planning_year"] == 2035
    assert readiness["time_domain"] == "full_year"
    assert readiness["node_ids"] == ("node-a", "node-b")
    assert readiness["shared_weather_driver_id"] == "weather-registry-1"
    assert readiness["component_count"] == 4
    assert readiness["context_aleatory_identity"] == context.aleatory_identity()
    hp_record = next(item for item in readiness["component_outputs"] if item["kind"] == "hp")
    assert hp_record == {
        "component_id": "hp-b",
        "kind": "hp",
        "node_id": "node-b",
        "source_id": "hp-readiness",
        "member_id": "hp-member-placeholder",
        "stream_id": _stream_id(context, "hp"),
        "shared_weather_driver_id": "weather-registry-1",
        "artifact_status": "accepted",
        "calendar_id": "calendar-2035-15min",
    }
    assert "p_kw" not in hp_record
    assert "q_kvar" not in hp_record
    assert readiness["real_component_readiness"]["artifact_status_by_component_id"]["pv-b"] == "accepted"

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

    outputs = _registry_adapter_outputs(context, registry)
    outputs[2] = ComponentAdapterOutput(
        component_id=outputs[2].component_id,
        kind=outputs[2].kind,
        node_id=outputs[2].node_id,
        p_kw=outputs[2].p_kw,
        q_kvar=outputs[2].q_kvar,
        timestamps=outputs[2].timestamps,
        member_id=outputs[2].member_id,
        source_id=outputs[2].source_id,
        stream_id="stale-hp-stream",
        shared_weather_driver_id=outputs[2].shared_weather_driver_id,
        metadata=dict(outputs[2].metadata),
    )
    with pytest.raises(ValueError, match="stream_id must match"):
        validate_registry_adapter_output_readiness(registry, context, outputs)

def _accepted_adapter_artifacts(
    *,
    shared_weather_driver_id: str = "weather-artifact-1",
) -> list[AcceptedComponentAdapterArtifact]:
    return [
        AcceptedComponentAdapterArtifact(
            artifact_id="baseline-artifact",
            kind="baseline",
            source_id="baseline-readiness",
            member_id="baseline-member-placeholder",
            node_ids=("node-a", "node-b"),
            calendar_id="calendar-2035-15min",
            provenance={"readiness_artifact": "E2.S5"},
        ),
        AcceptedComponentAdapterArtifact(
            artifact_id="ev-artifact",
            kind="ev",
            source_id="ev-readiness",
            member_id="ev-member-placeholder",
            node_ids=("node-a",),
            calendar_id="calendar-2035-15min",
            provenance={"readiness_artifact": "E2.S2"},
        ),
        AcceptedComponentAdapterArtifact(
            artifact_id="hp-artifact",
            kind="hp",
            source_id="hp-readiness",
            member_id="hp-member-placeholder",
            node_ids=("node-b",),
            calendar_id="calendar-2035-15min",
            shared_weather_driver_id=shared_weather_driver_id,
            provenance={"readiness_artifact": "E2.S3"},
        ),
        AcceptedComponentAdapterArtifact(
            artifact_id="pv-artifact",
            kind="pv",
            source_id="weather-pv-readiness",
            member_id="pv-member-placeholder",
            node_ids=("node-b",),
            calendar_id="calendar-2035-15min",
            shared_weather_driver_id=shared_weather_driver_id,
            provenance={"readiness_artifact": "E2.S4"},
        ),
    ]


def test_artifact_bridge_builds_registry_and_manifest_ready_plan() -> None:
    registry = build_component_adapter_registry_from_artifacts(
        registry_id="artifact-bridge-registry",
        node_ids=("node-a", "node-b"),
        artifacts=_accepted_adapter_artifacts(),
        metadata={"node_mapping_version": "synthetic-v1"},
    )
    plan = build_ic1_assembly_plan_from_registry(registry)

    assert registry.registry_id == "artifact-bridge-registry"
    assert registry.node_ids == ("node-a", "node-b")
    assert plan.node_ids == ("node-a", "node-b")
    bridge = registry.manifest_record()["metadata"]["artifact_bridge"]
    assert [artifact["kind"] for artifact in bridge["accepted_artifacts"]] == list(REAL_COMPONENT_WIRING_KINDS)
    assert bridge["accepted_artifacts"][0]["provenance"]["readiness_artifact"] == "E2.S5"
    assert registry.manifest_record()["readiness"]["shared_weather_driver_id"] == "weather-artifact-1"


def test_artifact_bridge_feeds_synthetic_outputs_through_registry_harness() -> None:
    registry = build_component_adapter_registry_from_artifacts(
        registry_id="artifact-bridge-registry",
        node_ids=("node-a", "node-b"),
        artifacts=_accepted_adapter_artifacts(),
    )
    context = _registry_context(registry)
    result = assemble_net_load_from_registry_outputs(
        registry,
        context,
        _registry_adapter_outputs(context, registry),
        metadata={"artifact_bridge_dry_run": True},
    )

    assert result.metadata["artifact_bridge_dry_run"] is True
    assert result.metadata["adapter_registry"]["metadata"]["artifact_bridge"]["accepted_artifacts"][1]["kind"] == "ev"
    assert result.shared_weather_driver_ids == ("weather-artifact-1",)
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


def test_artifact_bridge_rejects_missing_kind_node_gap_and_weather_mismatch() -> None:
    with pytest.raises(ValueError, match=r"missing accepted component adapter artifact kind\(s\): ev"):
        build_component_adapter_registry_from_artifacts(
            registry_id="missing-ev",
            node_ids=("node-a", "node-b"),
            artifacts=[artifact for artifact in _accepted_adapter_artifacts() if artifact.kind != "ev"],
        )

    with pytest.raises(ValueError, match="lack adapter artifact coverage"):
        build_component_adapter_registry_from_artifacts(
            registry_id="missing-node-coverage",
            node_ids=("node-a", "node-b", "node-c"),
            artifacts=_accepted_adapter_artifacts(),
        )

    artifacts = _accepted_adapter_artifacts()
    artifacts[3] = AcceptedComponentAdapterArtifact(
        artifact_id="pv-artifact",
        kind="pv",
        source_id="weather-pv-readiness",
        member_id="pv-member-placeholder",
        node_ids=("node-b",),
        calendar_id="calendar-2035-15min",
        shared_weather_driver_id="different-weather",
        provenance={"readiness_artifact": "E2.S4"},
    )
    with pytest.raises(ValueError, match="accepted adapter artifacts must share"):
        build_component_adapter_registry_from_artifacts(
            registry_id="weather-mismatch",
            node_ids=("node-a", "node-b"),
            artifacts=artifacts,
        )


def test_artifact_bridge_rejects_unmanifestable_provenance_and_cadence() -> None:
    with pytest.raises(ValueError, match="provenance values must not be None"):
        AcceptedComponentAdapterArtifact(
            artifact_id="bad-provenance",
            kind="baseline",
            source_id="baseline-readiness",
            member_id="baseline-member-placeholder",
            node_ids=("node-a",),
            calendar_id="calendar-2035-15min",
            provenance={"readiness_artifact": None},
        )

    with pytest.raises(ValueError, match="900-second"):
        AcceptedComponentAdapterArtifact(
            artifact_id="bad-cadence",
            kind="ev",
            source_id="ev-readiness",
            member_id="ev-member-placeholder",
            node_ids=("node-a",),
            calendar_id="calendar-2035-15min",
            timestep_seconds=1800,
            provenance={"readiness_artifact": "E2.S2"},
        )

def test_loading_input_readiness_validates_synthetic_window_set_without_events() -> None:
    registry = build_component_adapter_registry_from_artifacts(
        registry_id="loading-input-registry",
        node_ids=("node-a", "node-b"),
        artifacts=_accepted_adapter_artifacts(),
    )
    context = _registry_context(registry, time_domain="window_set")

    readiness = prepare_loading_input_from_registry_outputs(
        registry,
        context,
        _registry_adapter_outputs(context, registry),
        time_domain="window_set",
        metadata={"fixture": "synthetic-minimal"},
    )
    manifest = readiness.manifest_record()

    assert isinstance(readiness, NetLoadLoadingInputReadiness)
    assert manifest["planning_year"] == 2035
    assert manifest["time_domain"] == "window_set"
    assert manifest["primary_probability_domain"] is False
    assert manifest["timestep_seconds"] == 900
    assert manifest["timestep_count"] == 4
    assert manifest["calendar_start"].startswith("2035-01-01T00:00:00")
    assert manifest["node_ids"] == ("node-a", "node-b")
    assert manifest["registry_manifest"]["registry_id"] == "loading-input-registry"
    assert manifest["metadata"]["scaffold_only"] is True
    assert "threshold_pu" not in manifest
    assert "overload" not in manifest


def test_loading_input_readiness_rejects_partial_full_year_payload() -> None:
    registry = build_component_adapter_registry_from_artifacts(
        registry_id="loading-input-registry",
        node_ids=("node-a", "node-b"),
        artifacts=_accepted_adapter_artifacts(),
    )
    context = _registry_context(registry)

    with pytest.raises(ValueError, match="complete planning year"):
        prepare_loading_input_from_registry_outputs(
            registry,
            context,
            _registry_adapter_outputs(context, registry),
        )

def test_loading_input_readiness_rejects_context_year_or_domain_mismatch() -> None:
    registry = build_component_adapter_registry_from_artifacts(
        registry_id="loading-input-registry",
        node_ids=("node-a", "node-b"),
        artifacts=_accepted_adapter_artifacts(),
    )
    context = _registry_context(registry)

    with pytest.raises(ValueError, match="planning_year must match"):
        prepare_loading_input_from_registry_outputs(
            registry,
            context,
            _registry_adapter_outputs(context, registry),
            planning_year=2030,
        )

    with pytest.raises(ValueError, match="time_domain must match"):
        prepare_loading_input_from_registry_outputs(
            registry,
            context,
            _registry_adapter_outputs(context, registry),
            time_domain="window_set",
        )


def test_loading_input_readiness_rejects_non_2035_timestamps() -> None:
    registry = build_component_adapter_registry_from_artifacts(
        registry_id="loading-input-registry",
        node_ids=("node-a", "node-b"),
        artifacts=_accepted_adapter_artifacts(),
    )
    context = _registry_context(registry)
    shifted = _calendar().astype("datetime64[s]") - np.timedelta64(365, "D")
    outputs = [
        ComponentAdapterOutput(
            component_id=output.component_id,
            kind=output.kind,
            node_id=output.node_id,
            p_kw=output.p_kw,
            q_kvar=output.q_kvar,
            timestamps=shifted,
            member_id=output.member_id,
            source_id=output.source_id,
            stream_id=output.stream_id,
            shared_weather_driver_id=output.shared_weather_driver_id,
            metadata=dict(output.metadata),
        )
        for output in _registry_adapter_outputs(context, registry)
    ]

    with pytest.raises(ValueError, match="planning year"):
        prepare_loading_input_from_registry_outputs(
            registry,
            context,
            outputs,
        )


def test_loading_input_readiness_rejects_nonmanifestable_metadata() -> None:
    registry = build_component_adapter_registry_from_artifacts(
        registry_id="loading-input-registry",
        node_ids=("node-a", "node-b"),
        artifacts=_accepted_adapter_artifacts(),
    )
    context = _registry_context(registry)
    net_load = assemble_net_load_from_registry_outputs(
        registry,
        context,
        _registry_adapter_outputs(context, registry),
    )

    with pytest.raises(ValueError, match="metadata values must not be None"):
        NetLoadLoadingInputReadiness(
            net_load=net_load,
            registry_manifest=registry.manifest_record(),
            realization_context_manifest=context.manifest_metadata(),
            time_domain="window_set",
            metadata={"bad": None},
        )


def _executable_input_artifact(
    kind: str,
    *,
    artifact_status: str = "accepted",
    calendar_id: str = "calendar-2035-15min",
    timestep_seconds: int = 900,
    shared_weather_driver_id: str | None = None,
    version_id: str = "synthetic-v1",
    signed_register_ids: tuple[str, ...] | None = None,
    blocking_register_ids: tuple[str, ...] = (),
    manifest_path: str | None = "synthetic-default",
) -> ExecutableInputArtifact:
    if shared_weather_driver_id is None and kind in {"hp", "pv"}:
        shared_weather_driver_id = "weather-executable-1"
    if signed_register_ids is None and artifact_status == "accepted":
        signed_register_ids = {
            "baseline": ("D-001",),
            "ev": ("EV-003", "EV-004", "EV-007A", "EV-CAL-001"),
            "hp": ("HP-001",),
            "pv": ("WEATHER-001", "D004-MC-001"),
            "adoption": ("EV-007A", "A-014"),
            "flexibility": ("FLEX-001",),
        }[kind]
    return ExecutableInputArtifact(
        artifact_id=f"{kind}-executable-artifact",
        kind=kind,
        artifact_status=artifact_status,
        version_id=version_id,
        source_id=f"{kind}-source",
        member_id=f"{kind}-member",
        calendar_id=calendar_id,
        node_ids=("node-a",) if kind not in {"hp", "pv"} else ("node-b",),
        signed_register_ids=() if signed_register_ids is None else signed_register_ids,
        blocking_register_ids=blocking_register_ids,
        timestep_seconds=timestep_seconds,
        shared_weather_driver_id=shared_weather_driver_id,
        manifest_path=None if manifest_path is None else f"data/metadata/synthetic/{kind}.json",
        provenance={"fixture": "executable-input-gate"},
    )


def _executable_input_artifacts() -> list[ExecutableInputArtifact]:
    return [
        _executable_input_artifact("baseline"),
        _executable_input_artifact("ev"),
        _executable_input_artifact("hp"),
        _executable_input_artifact("pv"),
        _executable_input_artifact("adoption"),
        _executable_input_artifact("flexibility"),
    ]


def _executable_adapter_outputs(
    context,
    artifacts: list[ExecutableInputArtifact],
) -> list[ComponentAdapterOutput]:
    by_kind = {artifact.kind: artifact for artifact in artifacts}
    outputs = [
        _adapter_output(
            context,
            "baseline-a",
            "baseline",
            [10.0, 11.0, 12.0, 13.0],
            member_id=by_kind["baseline"].member_id,
            source_id=by_kind["baseline"].source_id,
            artifact_status=by_kind["baseline"].artifact_status,
        ),
        _adapter_output(
            context,
            "ev-a",
            "ev",
            [1.0, 2.0, 3.0, 4.0],
            member_id=by_kind["ev"].member_id,
            source_id=by_kind["ev"].source_id,
            artifact_status=by_kind["ev"].artifact_status,
        ),
        _adapter_output(
            context,
            "hp-b",
            "hp",
            [4.0, 5.0, 6.0, 7.0],
            node_id="node-b",
            member_id=by_kind["hp"].member_id,
            source_id=by_kind["hp"].source_id,
            shared_weather_driver_id=context.shared_weather_driver_id,
            artifact_status=by_kind["hp"].artifact_status,
        ),
        _adapter_output(
            context,
            "pv-b",
            "pv",
            [0.0, -2.0, -3.0, 0.0],
            node_id="node-b",
            member_id=by_kind["pv"].member_id,
            source_id=by_kind["pv"].source_id,
            shared_weather_driver_id=context.shared_weather_driver_id,
            artifact_status=by_kind["pv"].artifact_status,
        ),
        _adapter_output(
            context,
            "adoption-a",
            "adoption",
            [0.0, 0.0, 0.0, 0.0],
            member_id=by_kind["adoption"].member_id,
            source_id=by_kind["adoption"].source_id,
            artifact_status=by_kind["adoption"].artifact_status,
        ),
        _adapter_output(
            context,
            "flex-a",
            "flexibility",
            [-0.2, -0.2, 0.0, 0.0],
            member_id=by_kind["flexibility"].member_id,
            source_id=by_kind["flexibility"].source_id,
            artifact_status=by_kind["flexibility"].artifact_status,
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
            metadata={**dict(output.metadata), "calendar_id": by_kind[output.kind].calendar_id},
        )
        for output in outputs
    ]


def test_executable_input_gate_records_manifestable_ready_inputs_without_arrays() -> None:
    readiness = validate_executable_input_gate(
        _executable_input_artifacts(),
        intended_use="e3_s2b_screen_prerequisite",
    )

    assert readiness["ready_for_execution"] is True
    assert readiness["intended_use"] == "e3_s2b_screen_prerequisite"
    assert readiness["present_component_kinds"] == (
        "adoption",
        "baseline",
        "ev",
        "flexibility",
        "hp",
        "pv",
    )
    assert readiness["calendar_id"] == "calendar-2035-15min"
    assert readiness["timestep_seconds"] == 900
    assert readiness["shared_weather_driver_id"] == "weather-executable-1"
    assert readiness["signed_register_ids_by_kind"]["flexibility"] == ("FLEX-001",)
    assert readiness["manifest_paths_by_kind"]["ev"].endswith("ev.json")
    assert all("p_kw" not in artifact for artifact in readiness["artifacts"])
    assert all("q_kvar" not in artifact for artifact in readiness["artifacts"])


def test_executable_input_gate_rejects_missing_required_component() -> None:
    artifacts = [artifact for artifact in _executable_input_artifacts() if artifact.kind != "adoption"]

    with pytest.raises(ValueError, match=r"missing executable input artifact kind\(s\): adoption"):
        validate_executable_input_gate(artifacts)


def test_executable_input_gate_rejects_self_attested_pending_or_unsigned_ids() -> None:
    artifacts = _executable_input_artifacts()
    artifacts[2] = _executable_input_artifact(
        "hp",
        signed_register_ids=("D-013",),
    )

    with pytest.raises(ValueError, match=r"D-013 .*unsigned"):
        validate_executable_input_gate(artifacts)

    artifacts = _executable_input_artifacts()
    artifacts[5] = _executable_input_artifact(
        "flexibility",
        signed_register_ids=("A-013",),
    )

    with pytest.raises(ValueError, match=r"A-013 .*not valid for flexibility"):
        validate_executable_input_gate(artifacts)


def test_executable_input_gate_rejects_arbitrary_approved_ids_for_wrong_component() -> None:
    artifacts = _executable_input_artifacts()
    artifacts[1] = _executable_input_artifact(
        "ev",
        signed_register_ids=("G0",),
    )

    with pytest.raises(ValueError, match=r"G0 .*not valid for ev"):
        validate_executable_input_gate(artifacts)

def test_executable_input_gate_rejects_unsigned_inputs_with_blocking_ids() -> None:
    artifacts = _executable_input_artifacts()
    artifacts[2] = _executable_input_artifact(
        "hp",
        artifact_status="unsigned",
        signed_register_ids=(),
        blocking_register_ids=("D-013", "HP-LOCAL-SCALING", "D-004"),
    )

    with pytest.raises(ValueError, match="hp: D-013, HP-LOCAL-SCALING, D-004"):
        validate_executable_input_gate(
            artifacts,
            intended_use="e3_s2b_screen_prerequisite",
        )


def test_executable_input_gate_rejects_calendar_and_weather_mismatches() -> None:
    artifacts = _executable_input_artifacts()
    artifacts[1] = _executable_input_artifact("ev", calendar_id="calendar-2030-15min")
    with pytest.raises(ValueError, match="share one calendar_id"):
        validate_executable_input_gate(artifacts)

    artifacts = _executable_input_artifacts()
    artifacts[3] = _executable_input_artifact("pv", shared_weather_driver_id="different-weather")
    with pytest.raises(ValueError, match="share one weather driver"):
        validate_executable_input_gate(artifacts)


def test_executable_input_gate_requires_version_and_signed_or_blocking_ids() -> None:
    with pytest.raises(ValueError, match="version_id"):
        _executable_input_artifact("baseline", version_id="")

    with pytest.raises(ValueError, match="accepted executable inputs must cite signed_register_ids"):
        _executable_input_artifact("baseline", signed_register_ids=())

    with pytest.raises(ValueError, match="accepted executable inputs must cite manifest_path"):
        _executable_input_artifact("baseline", manifest_path=None)

    with pytest.raises(ValueError, match="non-accepted executable inputs must list"):
        _executable_input_artifact("flexibility", artifact_status="scaffold", signed_register_ids=())

class _CountingComponentAdapter:
    def __init__(self, output: ComponentAdapterOutput) -> None:
        self.output = output
        self.calls = 0

    def get_component_outputs(self, context, node_ids) -> list[ComponentAdapterOutput]:
        self.calls += 1
        return [self.output]


def _gated_provider(
    artifacts: list[ExecutableInputArtifact],
    context,
    *,
    adapters: tuple[object, ...] | None = None,
) -> GatedAdapterBackedNetLoadProvider:
    plan = NetLoadAssemblyPlan(node_ids=("node-a", "node-b"))
    if adapters is None:
        adapters = tuple(
            _CountingComponentAdapter(output)
            for output in _adapter_outputs(context)
        )
    return GatedAdapterBackedNetLoadProvider(
        plan=plan,
        adapters=adapters,
        executable_input_artifacts=tuple(artifacts),
        intended_use="e3_s2b_screen_prerequisite",
        calendar_metadata={"calendar_id": "calendar-2035-15min"},
        mapping_version_metadata={"node_mapping_version": "synthetic-v1"},
        metadata={"scaffold_only": True},
    )


def test_gated_provider_blocks_unsigned_inputs_before_adapter_calls() -> None:
    artifacts = _executable_input_artifacts()
    artifacts[1] = _executable_input_artifact(
        "ev",
        artifact_status="unsigned",
        signed_register_ids=(),
        blocking_register_ids=("EV-005B",),
    )
    context = build_realization_context(
        scenario="scenario-a",
        year=2035,
        time_domain="full_year",
        rho=0.0,
        seed=7001,
        shared_weather_driver_id="weather-executable-1",
    )
    adapter = _CountingComponentAdapter(_adapter_outputs(context)[0])
    provider = _gated_provider(artifacts, context, adapters=(adapter,))

    with pytest.raises(ValueError, match="ev: EV-005B"):
        provider.get_net_load("scenario-a", 2035, "full_year", rho=0.0, seed=7001)
    assert adapter.calls == 0


def test_gated_provider_allows_accepted_synthetic_fixture_without_events() -> None:
    context = build_realization_context(
        scenario="scenario-a",
        year=2035,
        time_domain="full_year",
        rho=0.5,
        seed=7001,
        shared_weather_driver_id="weather-executable-1",
    )
    provider = _gated_provider(_executable_input_artifacts(), context)

    result = provider.get_net_load("scenario-a", 2035, "full_year", rho=0.5, seed=7001)

    assert result.metadata["provider"] == "gated_adapter_backed_ic1_preflight"
    assert result.metadata["executable_input_gate"]["ready_for_execution"] is True
    assert result.metadata["executable_input_gate"]["intended_use"] == "e3_s2b_screen_prerequisite"
    assert result.metadata["scaffold_only"] is True
    assert result.shared_weather_driver_ids == ("weather-executable-1",)
    assert "threshold_pu" not in result.metadata
    assert "overload" not in result.metadata
    assert "capacity_screen" not in result.metadata
    np.testing.assert_array_equal(
        result.p_net_kw,
        np.array(
            [
                [10.8, 12.8, 15.0, 17.0],
                [4.0, 3.0, 3.0, 7.0],
            ]
        ),
    )

def _screen_preflight_config() -> FutureLayerScreenPreflightConfig:
    return FutureLayerScreenPreflightConfig(
        config_id="synthetic-e3-s2b-preflight",
        scenario_ids=("low", "middle", "high"),
        planning_years=(2030, 2033, 2035),
        rho_values=(0.0, 1.0),
        node_ids=("node-a", "node-b"),
        metadata={"calendar_id": "calendar-2035-15min", "scaffold_only": True},
    )


def test_executable_assembly_scaffold_prepares_synthetic_loading_input_without_events() -> None:
    context = build_realization_context(
        scenario="scenario-a",
        year=2035,
        time_domain="window_set",
        rho=0.5,
        seed=7001,
        shared_weather_driver_id="weather-executable-1",
        calendar_metadata={"calendar_id": "calendar-2035-15min"},
        mapping_version_metadata={"node_mapping_version": "synthetic-v1"},
    )

    artifacts = _executable_input_artifacts()
    readiness = prepare_executable_net_load_assembly_from_artifacts(
        assembly_id="synthetic-executable-assembly",
        executable_input_artifacts=artifacts,
        context=context,
        adapter_outputs=_executable_adapter_outputs(context, artifacts),
        intended_use="e3_s2_ic1_assembly_scaffold",
        time_domain="window_set",
        metadata={"fixture": "tiny-synthetic"},
    )

    manifest = readiness.manifest_record()
    assert manifest["primary_probability_domain"] is False
    assert manifest["metadata"]["source"] == "executable_artifact_assembly_scaffold"
    assert manifest["metadata"]["no_event_detection"] is True
    assert manifest["metadata"]["no_probability_estimate"] is True
    assert manifest["metadata"]["no_capacity_screen_result"] is True
    registry = manifest["registry_manifest"]
    assert registry["metadata"]["assembly_id"] == "synthetic-executable-assembly"
    assert registry["metadata"]["executable_input_gate"]["ready_for_execution"] is True
    assert registry["metadata"]["governed_event_metadata"] == {
        "basis": "G0-A3",
        "primary_threshold_pu": 1.0,
        "strict_import_loading_gt_threshold": True,
        "min_consecutive_15_minute_steps": 4,
        "not_evaluated_here": True,
    }
    assert "threshold_pu" not in readiness.net_load.metadata
    assert "overload" not in readiness.net_load.metadata
    np.testing.assert_array_equal(
        readiness.net_load.p_net_kw,
        np.array(
            [
                [10.8, 12.8, 15.0, 17.0],
                [4.0, 3.0, 3.0, 7.0],
            ]
        ),
    )


def test_executable_assembly_scaffold_rejects_current_unsigned_project_readiness() -> None:
    artifacts = _executable_input_artifacts()
    artifacts[0] = _executable_input_artifact(
        "baseline",
        artifact_status="scaffold",
        signed_register_ids=(),
        blocking_register_ids=("E2.S5-BASELINE-EXECUTABLE-ARTIFACT",),
    )
    artifacts[2] = _executable_input_artifact(
        "hp",
        artifact_status="unsigned",
        signed_register_ids=("HP-001", "D-013", "WEATHER-001"),
        blocking_register_ids=(
            "E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET",
            "value_column",
            "denominator",
            "unit_conversion",
            "sfh_mfh_split",
            "adoption_electrification",
            "d004_paired_weather_acceptance",
            "cold_spell_tolerances",
        ),
    )
    artifacts[3] = _executable_input_artifact(
        "pv",
        artifact_status="unsigned",
        signed_register_ids=("WEATHER-001", "D004-MC-001", "D004-SOURCE-MEMBER-ACCEPTANCE", "PV-CAP-001"),
        blocking_register_ids=("PV-PARAM-001", "FINAL-PAIRED-HP-PV-ACCEPTANCE", "COLD-SPELL-ACCEPTANCE"),
    )
    artifacts[4] = _executable_input_artifact(
        "adoption",
        artifact_status="unsigned",
        signed_register_ids=("EV-007A", "A-014"),
        blocking_register_ids=("E2.S6-PER-NODE-EXECUTABLE-ADOPTION-ARTIFACT",),
    )
    context = build_realization_context(
        scenario="middle",
        year=2035,
        time_domain="window_set",
        rho=0.0,
        seed=7001,
        shared_weather_driver_id="weather-executable-1",
    )
    adapter = _CountingComponentAdapter(_adapter_outputs(context)[0])

    with pytest.raises(ValueError, match="baseline: E2.S5-BASELINE-EXECUTABLE-ARTIFACT"):
        prepare_executable_net_load_assembly_from_artifacts(
            assembly_id="current-project-readiness",
            executable_input_artifacts=artifacts,
            context=context,
            adapter_outputs=(adapter.output,),
            intended_use="e3_s2_ic1_assembly_scaffold",
            time_domain="window_set",
        )
    assert adapter.calls == 0


def _trajectory_prerun_config() -> LoadingTrajectoryPreRunConfig:
    return LoadingTrajectoryPreRunConfig(
        config_id="synthetic-e3-s2-loading-bridge",
        purpose="e3_s2b_future_layer_screen",
        planning_years=(2030, 2033, 2035),
        metadata={"scaffold_only": True},
    )


def _synthetic_capacity_provenance() -> dict[str, object]:
    return {
        "s_nom_agg_kva": 80000.0,
        "convention_status": "pending_g1_a2_e3_s2b",
        "source": "synthetic-transformer-denominator-fixture",
        "metadata": {"no_capacity_convention_choice": True},
    }


def test_executable_loading_bridge_links_ic1_gate_to_ic2_prerun_metadata_only() -> None:
    bridge = build_executable_loading_bridge_preflight(
        _screen_preflight_config(),
        _executable_input_artifacts(),
        _trajectory_prerun_config(),
        capacity_provenance=_synthetic_capacity_provenance(),
    )

    assert bridge["dry_run_only"] is True
    assert bridge["metadata_preflight_only"] is True
    assert bridge["ready_for_ic1_input_assembly"] is True
    assert bridge["ready_for_synthetic_loading_manifest"] is True
    assert bridge["ready_for_first_real_experiment"] is False
    assert bridge["no_real_net_load_arrays"] is True
    assert bridge["no_event_detection"] is True
    assert bridge["no_event_counts"] is True
    assert bridge["no_probability_estimate"] is True
    assert bridge["no_capacity_screen_result"] is True
    assert bridge["trajectory_prerun_manifest"]["governed_event_metadata"] == {
        "basis": "G0-A3",
        "primary_threshold_pu": 1.0,
        "strict_import_loading_gt_threshold": True,
        "sensitivity_thresholds_pu": (1.1, 1.2),
        "min_consecutive_15_minute_steps": 4,
        "not_evaluated_here": True,
    }
    assert bridge["manifest_fields"]["capacity_provenance"]["convention_status"] == "pending_g1_a2_e3_s2b"
    assert bridge["blockers"]["downstream_gate_blockers"] == ("A-013", "G2", "G1-A2", "A-016")
    assert "threshold_pu" not in bridge
    assert "overload" not in bridge
    assert "p_event" not in bridge


def test_executable_loading_bridge_reports_current_real_project_blockers_fail_closed() -> None:
    artifacts = _executable_input_artifacts()
    artifacts[2] = _executable_input_artifact(
        "hp",
        artifact_status="unsigned",
        signed_register_ids=("HP-001", "D-013", "WEATHER-001"),
        blocking_register_ids=("D-013", "HP-SCENARIO-CONSISTENCY", "D004-PAIRED-ACCEPTANCE"),
    )
    artifacts[3] = _executable_input_artifact(
        "pv",
        artifact_status="unsigned",
        signed_register_ids=("D004-SOURCE-MEMBER-ACCEPTANCE", "PV-CAP-001"),
        blocking_register_ids=("PV-PARAM-001", "D-014", "PV-CAPACITY-VALUE"),
    )

    bridge = build_executable_loading_bridge_preflight(
        _screen_preflight_config(),
        artifacts,
        _trajectory_prerun_config(),
        capacity_provenance=None,
    )

    assert bridge["ready_for_ic1_input_assembly"] is False
    assert bridge["ready_for_synthetic_loading_manifest"] is False
    assert bridge["ready_for_first_real_experiment"] is False
    assert bridge["blockers"]["component_artifact_blockers_by_kind"]["hp"] == (
        "D-013",
        "HP-SCENARIO-CONSISTENCY",
        "D004-PAIRED-ACCEPTANCE",
    )
    assert bridge["blockers"]["component_artifact_blockers_by_kind"]["pv"] == (
        "PV-PARAM-001",
        "D-014",
        "PV-CAPACITY-VALUE",
    )
    assert bridge["blockers"]["capacity_provenance_missing"] is True
    assert bridge["executable_input_preflight"]["executable_input_gate"] is None
    assert bridge["no_event_detection"] is True
    assert bridge["no_probability_estimate"] is True


def test_executable_loading_bridge_rejects_bad_bridge_metadata() -> None:
    bad_capacity = {
        "s_nom_agg_kva": 0.0,
        "convention_status": "pending_g1_a2_e3_s2b",
        "source": "synthetic",
    }
    with pytest.raises(ValueError, match="s_nom_agg_kva"):
        build_executable_loading_bridge_preflight(
            _screen_preflight_config(),
            _executable_input_artifacts(),
            _trajectory_prerun_config(),
            capacity_provenance=bad_capacity,
        )

    mismatched_trajectory_config = LoadingTrajectoryPreRunConfig(
        config_id="bad-years",
        purpose="e3_s2b_future_layer_screen",
        planning_years=(2035,),
    )
    with pytest.raises(ValueError, match="planning_years"):
        build_executable_loading_bridge_preflight(
            _screen_preflight_config(),
            _executable_input_artifacts(),
            mismatched_trajectory_config,
            capacity_provenance=_synthetic_capacity_provenance(),
        )


def test_future_layer_screen_preflight_records_manifest_fields_without_results() -> None:
    preflight = validate_future_layer_screen_preflight(
        _screen_preflight_config(),
        _executable_input_artifacts(),
    )

    assert preflight["ready_for_input_assembly"] is True
    assert preflight["screen_prerequisite_only"] is True
    assert preflight["no_event_detection"] is True
    assert preflight["no_capacity_screen_result"] is True
    assert preflight["config_manifest"]["planned_case_count"] == 18
    assert preflight["manifest_fields"]["shared_weather_driver_id"] == "weather-executable-1"
    assert preflight["manifest_fields"]["manifest_paths_by_kind"]["pv"].endswith("pv.json")
    assert "threshold_pu" not in preflight
    assert "overload" not in preflight
    assert "capacity_screen" not in preflight

def test_integrated_input_preflight_dry_run_reports_ready_artifacts_without_results() -> None:
    report = dry_run_integrated_input_preflight(
        _screen_preflight_config(),
        _executable_input_artifacts(),
    )

    assert report["dry_run_only"] is True
    assert report["ready_for_input_assembly"] is True
    assert report["accepted_component_kinds"] == (
        "adoption",
        "baseline",
        "ev",
        "flexibility",
        "hp",
        "pv",
    )
    assert report["missing_component_kinds"] == ()
    assert report["blocked_component_kinds"] == ()
    assert report["component_reports"]["ev"]["state"] == "accepted"
    assert report["executable_input_gate"]["ready_for_execution"] is True
    assert report["no_real_net_load_arrays"] is True
    assert report["no_event_detection"] is True
    assert report["no_probability_estimate"] is True
    assert report["no_capacity_screen_result"] is True
    assert "threshold_pu" not in report
    assert "overload" not in report
    assert "capacity_screen" not in report


def test_integrated_input_preflight_dry_run_reports_missing_artifacts_with_blockers() -> None:
    artifacts = [
        artifact
        for artifact in _executable_input_artifacts()
        if artifact.kind not in {"hp", "pv"}
    ]

    report = dry_run_integrated_input_preflight(
        _screen_preflight_config(),
        artifacts,
        missing_artifact_blockers={
            "hp": ("D-013", "HP-LOCAL-SCALING"),
            "pv": ("PV-PARAM-001", "D004-SOURCE-MEMBER-ACCEPTANCE"),
        },
    )

    assert report["ready_for_input_assembly"] is False
    assert report["present_component_kinds"] == ("adoption", "baseline", "ev", "flexibility")
    assert report["accepted_component_kinds"] == ("adoption", "baseline", "ev", "flexibility")
    assert report["missing_component_kinds"] == ("hp", "pv")
    assert report["blocked_component_kinds"] == ()
    assert report["component_reports"]["hp"]["state"] == "missing"
    assert report["component_reports"]["hp"]["blocking_register_ids"] == ("D-013", "HP-LOCAL-SCALING")
    assert report["component_reports"]["pv"]["blocking_register_ids"] == (
        "PV-PARAM-001",
        "D004-SOURCE-MEMBER-ACCEPTANCE",
    )
    assert report["executable_input_gate"] is None


def test_integrated_input_preflight_dry_run_reports_register_blocked_artifacts() -> None:
    artifacts = _executable_input_artifacts()
    artifacts[2] = _executable_input_artifact("hp", signed_register_ids=("D-013",))
    artifacts[3] = _executable_input_artifact("pv", signed_register_ids=("PV-PARAM-001",))

    report = dry_run_integrated_input_preflight(
        _screen_preflight_config(),
        artifacts,
    )

    assert report["ready_for_input_assembly"] is False
    assert report["missing_component_kinds"] == ()
    assert report["blocked_component_kinds"] == ("hp", "pv")
    assert report["component_reports"]["hp"]["reason"] == "register_backing_not_accepted"
    assert report["component_reports"]["pv"]["reason"] == "register_backing_not_accepted"
    assert "D-013" in report["component_reports"]["hp"]["register_backing_errors"][0]
    assert "values/adoption" in report["component_reports"]["hp"]["register_backing_errors"][0]
    assert "PV-PARAM-001" in report["component_reports"]["pv"]["register_backing_errors"][0]
    assert "proposed" in report["component_reports"]["pv"]["register_backing_errors"][0]
    assert report["executable_input_gate"] is None



def test_executable_readiness_report_separates_packet_status_from_gate_result() -> None:
    preflight = {
        "required_component_kinds": ("baseline", "hp", "ev"),
        "component_reports": {
            "baseline": {
                "state": "blocked",
                "artifact_status": "scaffold",
                "artifact_id": "baseline-readiness",
                "manifest_path": "reports/baseline.md",
                "signed_register_ids": (),
                "blocking_register_ids": ("E2.S5-BASELINE-EXECUTABLE-ARTIFACT",),
                "artifact": {
                    "provenance": {
                        "packet_status": "scaffold present; accepted executable artifact missing"
                    }
                },
            },
            "hp": {
                "state": "blocked",
                "artifact_status": "unsigned",
                "artifact_id": "hp-value-binding-packet",
                "manifest_path": "data/metadata/hp.json",
                "signed_register_ids": ("HP-001",),
                "blocking_register_ids": ("E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET",),
                "artifact": {
                    "provenance": {
                        "packet_status": "proposed executable-value-binding decision packet"
                    }
                },
            },
            "ev": {
                "state": "accepted",
                "artifact_status": "accepted",
                "artifact_id": "ev-artifact",
                "manifest_path": "data/metadata/ev.json",
                "signed_register_ids": ("EV-003",),
                "blocking_register_ids": (),
                "artifact": {"provenance": {}},
            },
        },
    }

    groups = _component_groups(preflight)
    rows = _table_rows(preflight)

    assert groups["accepted"] == "ev"
    assert groups["blocked"] == "baseline, hp"
    assert groups["proposed_or_unsigned"] == "baseline, hp"
    assert "| hp | blocked | proposed executable-value-binding decision packet |" in rows
    assert "| ev | accepted | accepted |" in rows


def test_future_layer_screen_preflight_reports_missing_artifact_blocker_ids() -> None:
    artifacts = [artifact for artifact in _executable_input_artifacts() if artifact.kind != "pv"]

    with pytest.raises(
        ValueError,
        match="pv: D004-SOURCE-MEMBER-ACCEPTANCE, WEATHER-001",
    ):
        validate_future_layer_screen_preflight(
            _screen_preflight_config(),
            artifacts,
            missing_artifact_blockers={
                "pv": ("D004-SOURCE-MEMBER-ACCEPTANCE", "WEATHER-001"),
            },
        )


def test_future_layer_screen_preflight_reports_unsigned_artifact_blockers() -> None:
    artifacts = _executable_input_artifacts()
    artifacts[2] = _executable_input_artifact(
        "hp",
        artifact_status="unsigned",
        signed_register_ids=(),
        blocking_register_ids=("D-013", "HP-LOCAL-SCALING"),
    )

    with pytest.raises(ValueError, match="hp: D-013, HP-LOCAL-SCALING"):
        validate_future_layer_screen_preflight(_screen_preflight_config(), artifacts)


def test_future_layer_screen_preflight_rejects_invalid_config_and_blocker_metadata() -> None:
    with pytest.raises(ValueError, match="rho_values"):
        FutureLayerScreenPreflightConfig(
            config_id="bad-rho",
            scenario_ids=("middle",),
            planning_years=(2035,),
            rho_values=(0.0, 1.2),
            node_ids=("node-a",),
        )

    with pytest.raises(ValueError, match="missing_artifact_blockers values"):
        validate_future_layer_screen_preflight(
            _screen_preflight_config(),
            [artifact for artifact in _executable_input_artifacts() if artifact.kind != "ev"],
            missing_artifact_blockers={"ev": ()},
        )
