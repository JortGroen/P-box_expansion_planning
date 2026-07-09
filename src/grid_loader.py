"""Candidate grid loading and inventory helpers for E1.S1.

The heavy grid packages are imported lazily so tests and metadata utilities can
run even when pandapower or simbench are not installed in the active Python
environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CandidateGridSpec:
    """Description of a candidate distribution grid.

    Parameters
    ----------
    key:
        Stable project-local identifier for the grid.
    source:
        Loader family. Supported values are ``"simbench"`` and ``"pandapower"``.
    code:
        Source-specific grid code or constructor selector.
    role:
        Intended G0 role for the candidate grid.
    """

    key: str
    source: str
    code: str
    role: str


CANDIDATE_GRIDS: Mapping[str, CandidateGridSpec] = {
    "simbench_semiurb": CandidateGridSpec(
        key="simbench_semiurb",
        source="simbench",
        code="1-MV-semiurb--0-sw",
        role="primary candidate",
    ),
    "simbench_urban": CandidateGridSpec(
        key="simbench_urban",
        source="simbench",
        code="1-MV-urban--0-sw",
        role="secondary SimBench candidate",
    ),
    "cigre_mv": CandidateGridSpec(
        key="cigre_mv",
        source="pandapower",
        code="create_cigre_network_mv",
        role="cross-check candidate",
    ),
}


def candidate_grid_specs() -> tuple[CandidateGridSpec, ...]:
    """Return the E1.S1 candidate grid specifications."""

    return tuple(CANDIDATE_GRIDS.values())


def load_candidate_grid(key: str) -> Any:
    """Load a candidate grid by key.

    Parameters
    ----------
    key:
        One of the keys from :data:`CANDIDATE_GRIDS`.

    Returns
    -------
    Any
        A pandapower network object.
    """

    try:
        spec = CANDIDATE_GRIDS[key]
    except KeyError as exc:
        valid = ", ".join(sorted(CANDIDATE_GRIDS))
        raise KeyError(f"Unknown candidate grid {key!r}. Valid keys: {valid}") from exc

    if spec.source == "simbench":
        import simbench as sb

        return sb.get_simbench_net(spec.code)

    if spec.source == "pandapower" and spec.code == "create_cigre_network_mv":
        import pandapower.networks as networks

        return networks.create_cigre_network_mv(with_der="pv_wind")

    raise ValueError(f"Unsupported candidate grid spec: {spec}")


def run_deterministic_power_flow(net: Any) -> bool:
    """Run a deterministic pandapower AC power flow.

    Parameters
    ----------
    net:
        pandapower network object.

    Returns
    -------
    bool
        ``True`` when pandapower marks the network as converged.
    """

    import pandapower as pp

    pp.runpp(net, algorithm="nr", calculate_voltage_angles=True, init="auto")
    return bool(getattr(net, "converged", False))


def _table_len(net: Any, table_name: str) -> int:
    table = getattr(net, table_name, None)
    if table is None:
        return 0
    return int(len(table))


def _sum_column(net: Any, table_name: str, column_name: str) -> float | None:
    table = getattr(net, table_name, None)
    if table is None or column_name not in table:
        return None
    return float(table[column_name].sum())


def _max_column(net: Any, table_name: str, column_name: str) -> float | None:
    table = getattr(net, table_name, None)
    if table is None or len(table) == 0 or column_name not in table:
        return None
    return float(table[column_name].max())


def summarize_grid(spec: CandidateGridSpec, net: Any, *, converged: bool | None) -> dict[str, Any]:
    """Summarize a loaded grid for the G0 inventory.

    Parameters
    ----------
    spec:
        Candidate grid metadata.
    net:
        pandapower network object.
    converged:
        Result of the deterministic baseline power flow, or ``None`` when not
        run because loading failed.
    """

    return {
        "key": spec.key,
        "source": spec.source,
        "code": spec.code,
        "role": spec.role,
        "buses": _table_len(net, "bus"),
        "lines": _table_len(net, "line"),
        "trafos": _table_len(net, "trafo"),
        "trafo3w": _table_len(net, "trafo3w"),
        "loads": _table_len(net, "load"),
        "static_generators": _table_len(net, "sgen"),
        "storages": _table_len(net, "storage"),
        "total_load_mw": _sum_column(net, "load", "p_mw"),
        "total_sgen_mw": _sum_column(net, "sgen", "p_mw"),
        "line_length_km": _sum_column(net, "line", "length_km"),
        "max_line_i_ka": _max_column(net, "line", "max_i_ka"),
        "trafo_s_rated_mva": _sum_column(net, "trafo", "sn_mva"),
        "baseline_converged": converged,
    }


def inventory_rows() -> list[dict[str, Any]]:
    """Load all candidate grids, run baselines, and return inventory rows."""

    rows: list[dict[str, Any]] = []
    for spec in candidate_grid_specs():
        net = load_candidate_grid(spec.key)
        converged = run_deterministic_power_flow(net)
        rows.append(summarize_grid(spec, net, converged=converged))
    return rows


def _format_float(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def inventory_markdown(rows: list[dict[str, Any]]) -> str:
    """Render grid inventory rows as a Markdown table."""

    columns = [
        "key",
        "role",
        "code",
        "buses",
        "lines",
        "trafos",
        "loads",
        "static_generators",
        "total_load_mw",
        "total_sgen_mw",
        "line_length_km",
        "trafo_s_rated_mva",
        "baseline_converged",
    ]
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(_format_float(row.get(column)) for column in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])
