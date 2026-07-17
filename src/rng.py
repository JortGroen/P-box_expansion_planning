"""Seed-tree and common-random-number helpers.

The E3.S4 harness separates one complete aleatory realization from analysis
branches such as alpha level, interval endpoint, or treatment. Downstream
code can therefore reuse the same physical sample while changing epistemic
or policy branches.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np

UINT64_MODULUS = 2**64


def sample_seed(root_seed: int, sample_index: int) -> int:
    """Return the stable root seed for one whole-system aleatory sample."""

    if sample_index < 0:
        raise ValueError("sample_index must be non-negative")
    # Alpha, endpoint, and treatment are deliberately absent: CRN requires the
    # same complete aleatory sample to be replayed under every analysis branch.
    return _stable_u64("sample", root_seed, sample_index)


def component_seed(root_seed: int, sample_index: int, component: str) -> int:
    """Return an independent component-stream seed inside one sample."""

    component_name = _require_name(component, "component")
    # The component name is part of the derivation path so EV, baseline, HP,
    # PV, and future components do not silently consume one shared RNG stream.
    return _stable_u64("component", sample_seed(root_seed, sample_index), component_name)


@dataclass(frozen=True)
class ComponentStream:
    """Deterministic RNG stream for one component of one aleatory sample."""

    sample_index: int
    component: str
    seed: int

    @property
    def stream_id(self) -> str:
        return f"sample_{self.sample_index}:{self.component}"

    def rng(self) -> np.random.Generator:
        """Create a fresh NumPy generator positioned at the stream start."""

        return np.random.default_rng(self.seed)

    def manifest_record(self) -> dict[str, int | str]:
        """Return a compact, JSON-serializable stream record."""

        return {
            "component": self.component,
            "sample_index": self.sample_index,
            "seed": self.seed,
            "stream_id": self.stream_id,
        }


@dataclass(frozen=True)
class ComponentSelection:
    """Manifestable source-member selection made from a component stream."""

    component: str
    source_member_id: str
    stream_id: str
    selection_index: int | None = None
    source_batch_id: str | None = None

    def __post_init__(self) -> None:
        _require_name(self.component, "component")
        _require_name(self.source_member_id, "source_member_id")
        _require_name(self.stream_id, "stream_id")
        if self.selection_index is not None and self.selection_index < 0:
            raise ValueError("selection_index must be non-negative when provided")

    def manifest_record(self) -> dict[str, int | str]:
        record: dict[str, int | str] = {
            "component": self.component,
            "source_member_id": self.source_member_id,
            "stream_id": self.stream_id,
        }
        if self.selection_index is not None:
            record["selection_index"] = self.selection_index
        if self.source_batch_id is not None:
            record["source_batch_id"] = self.source_batch_id
        return record


@dataclass(frozen=True)
class SeedTree:
    """Rooted seed tree for whole-system Monte Carlo samples."""

    root_seed: int

    def __post_init__(self) -> None:
        if self.root_seed < 0:
            raise ValueError("root_seed must be non-negative")

    def sample_seed(self, sample_index: int) -> int:
        return sample_seed(self.root_seed, sample_index)

    def component_stream(self, sample_index: int, component: str) -> ComponentStream:
        component_name = _require_name(component, "component")
        seed = component_seed(self.root_seed, sample_index, component_name)
        return ComponentStream(
            sample_index=sample_index,
            component=component_name,
            seed=seed,
        )

    def realization(
        self,
        sample_index: int,
        *,
        component_names: Sequence[str] = (),
        component_selections: Sequence[ComponentSelection] = (),
        shared_driver_ids: Mapping[str, str] | None = None,
    ) -> "AleatoryRealization":
        if sample_index < 0:
            raise ValueError("sample_index must be non-negative")
        component_set = {_require_name(component, "component") for component in component_names}
        component_set.update(selection.component for selection in component_selections)
        streams = {
            component: self.component_stream(sample_index, component)
            for component in component_set
        }
        return AleatoryRealization(
            tree=self,
            sample_index=sample_index,
            streams=dict(sorted(streams.items())),
            component_selections=tuple(component_selections),
            shared_driver_ids=dict(sorted((shared_driver_ids or {}).items())),
        )


@dataclass(frozen=True)
class AleatoryRealization:
    """One complete physical aleatory sample, independent of branch labels."""

    tree: SeedTree
    sample_index: int
    streams: Mapping[str, ComponentStream] = field(default_factory=dict)
    component_selections: tuple[ComponentSelection, ...] = ()
    shared_driver_ids: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sample_index < 0:
            raise ValueError("sample_index must be non-negative")
        normalized_streams = dict(self.streams)
        for component, stream in normalized_streams.items():
            if component != stream.component:
                raise ValueError("stream mapping key must match stream component")
            if stream.sample_index != self.sample_index:
                raise ValueError("stream sample_index must match realization sample_index")
        for selection in self.component_selections:
            stream = normalized_streams.get(selection.component)
            if stream is None:
                raise ValueError(
                    "component selection requires its component stream in the realization"
                )
            if selection.stream_id != stream.stream_id:
                raise ValueError(
                    "component selection stream_id must match the realization stream"
                )
        for name, value in self.shared_driver_ids.items():
            _require_name(name, "shared_driver_id key")
            _require_name(value, "shared_driver_id value")

    def stream(self, component: str) -> ComponentStream:
        component_name = _require_name(component, "component")
        if component_name in self.streams:
            return self.streams[component_name]
        return self.tree.component_stream(self.sample_index, component_name)

    def branch(
        self,
        *,
        alpha: float | str,
        endpoint: str,
        treatment: str,
        component_names: Sequence[str] = (),
    ) -> "CRNBranch":
        branch_streams = dict(self.streams)
        for component in component_names:
            stream = self.stream(component)
            branch_streams[stream.component] = stream
        return CRNBranch(
            realization=AleatoryRealization(
                tree=self.tree,
                sample_index=self.sample_index,
                streams=dict(sorted(branch_streams.items())),
                component_selections=self.component_selections,
                shared_driver_ids=dict(sorted(self.shared_driver_ids.items())),
            ),
            alpha=alpha,
            endpoint=_require_name(endpoint, "endpoint"),
            treatment=_require_name(treatment, "treatment"),
        )


@dataclass(frozen=True)
class CRNBranch:
    """Analysis branch view over an unchanged aleatory realization."""

    realization: AleatoryRealization
    alpha: float | str
    endpoint: str
    treatment: str

    def aleatory_fingerprint(self) -> str:
        """Return a branch-invariant digest of sample, streams, and selections."""

        return hashlib.sha256(
            _stable_json(
                {
                    "root_seed": self.realization.tree.root_seed,
                    "sample_seed": self.realization.tree.sample_seed(
                        self.realization.sample_index
                    ),
                    "sample_index": self.realization.sample_index,
                    "component_selections": self._selection_records(),
                    "component_streams": self._stream_records(),
                    "shared_driver_ids": dict(
                        sorted(self.realization.shared_driver_ids.items())
                    ),
                }
            ).encode("utf-8")
        ).hexdigest()

    def manifest_record(self) -> dict[str, object]:
        """Return a JSON-serializable record suitable for experiment manifests."""

        return {
            "aleatory_fingerprint": self.aleatory_fingerprint(),
            "branch": {
                "alpha": self.alpha,
                "endpoint": self.endpoint,
                "treatment": self.treatment,
            },
            "component_selections": self._selection_records(),
            "component_streams": self._stream_records(),
            "root_seed": self.realization.tree.root_seed,
            "sample_seed": self.realization.tree.sample_seed(
                self.realization.sample_index
            ),
            "sample_index": self.realization.sample_index,
            "shared_driver_ids": dict(sorted(self.realization.shared_driver_ids.items())),
        }

    def _stream_records(self) -> list[dict[str, int | str]]:
        return [
            stream.manifest_record()
            for _component, stream in sorted(self.realization.streams.items())
        ]

    def _selection_records(self) -> list[dict[str, int | str]]:
        return [
            selection.manifest_record()
            for selection in sorted(
                self.realization.component_selections,
                key=lambda item: (item.component, item.stream_id, item.source_member_id),
            )
        ]


def assert_crn_equivalent(branches: Sequence[CRNBranch]) -> None:
    """Raise if branches do not share one complete aleatory realization."""

    if not branches:
        raise ValueError("at least one branch is required")
    reference = branches[0].aleatory_fingerprint()
    for branch in branches[1:]:
        if branch.aleatory_fingerprint() != reference:
            raise ValueError("CRN branches do not share the same aleatory realization")


def _stable_u64(*parts: object) -> int:
    payload = _stable_json(parts).encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False) % UINT64_MODULUS


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _require_name(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value
