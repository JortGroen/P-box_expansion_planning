from __future__ import annotations

import pandas as pd
import pytest

from src.grid_loader import (
    CANDIDATE_GRIDS,
    candidate_grid_specs,
    inventory_markdown,
    load_candidate_grid,
    summarize_grid,
)


class FakeNet:
    def __init__(self) -> None:
        self.bus = pd.DataFrame(index=[0, 1, 2])
        self.line = pd.DataFrame(
            {
                "length_km": [1.5, 2.0],
                "max_i_ka": [0.3, 0.4],
            }
        )
        self.trafo = pd.DataFrame({"sn_mva": [10.0]})
        self.load = pd.DataFrame({"p_mw": [1.0, 2.5]})
        self.sgen = pd.DataFrame({"p_mw": [0.75]})
        self.storage = pd.DataFrame(index=[])


def test_candidate_grid_specs_match_e1_s1_scope() -> None:
    specs = {spec.key: spec for spec in candidate_grid_specs()}

    assert set(specs) == {"simbench_semiurb", "simbench_urban", "cigre_mv"}
    assert specs["simbench_semiurb"].code == "1-MV-semiurb--0-sw"
    assert specs["simbench_urban"].code == "1-MV-urban--0-sw"
    assert specs["cigre_mv"].code == "create_cigre_network_mv"


def test_load_candidate_grid_rejects_unknown_key() -> None:
    with pytest.raises(KeyError, match="Unknown candidate grid"):
        load_candidate_grid("not-a-grid")


def test_summarize_grid_counts_and_ratings() -> None:
    spec = CANDIDATE_GRIDS["simbench_semiurb"]

    row = summarize_grid(spec, FakeNet(), converged=True)

    assert row["key"] == "simbench_semiurb"
    assert row["buses"] == 3
    assert row["lines"] == 2
    assert row["trafos"] == 1
    assert row["loads"] == 2
    assert row["static_generators"] == 1
    assert row["storages"] == 0
    assert row["total_load_mw"] == 3.5
    assert row["total_sgen_mw"] == 0.75
    assert row["line_length_km"] == 3.5
    assert row["max_line_i_ka"] == 0.4
    assert row["trafo_s_rated_mva"] == 10.0
    assert row["baseline_converged"] is True


def test_inventory_markdown_contains_expected_columns() -> None:
    row = summarize_grid(CANDIDATE_GRIDS["cigre_mv"], FakeNet(), converged=False)

    markdown = inventory_markdown([row])

    assert "baseline_converged" in markdown
    assert "cigre_mv" in markdown
    assert "False" in markdown
