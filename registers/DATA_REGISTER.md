# DATA_REGISTER.md

External data, citations, and numeric anchors go here before use. Status
`proposed` means an agent has identified the item; it is not approved for paper
claims until the PI signs it.

| ID | Item | Source | DOI/URL | License | Retrieval script | Checksum | Verification tag | Status | PI sign-off |
|---|---|---|---|---|---|---|---|---|---|
| D-001 | SimBench benchmark grids and time series | SimBench dataset paper and package | DOI/URL to verify in E2.S1 | to check | `data/get_simbench.py` | TBD | review tag to import | proposed | -- |
| D-002 | EV charging behavior profiles | ElaadNL Laadprofielengenerator generated profiles | Dashboard: https://charging.elaad.nl/; API docs: https://api.charging.data.elaad.nl/docs#; generation spec: `reports/elaad_profile_generation_spec.md` | Terms of use for generated profiles still to verify before redistribution or manuscript data-availability claims | `data/get_elaad_profiles.py` | TBD after one-profile API probe; raw responses stay under ignored `data/raw/elaad_profiles/`, manifests under `data/metadata/elaad_profiles/` | EV-001; profile-generator spec added by PI | proposed | -- |
| D-003 | Heat-pump profiles | When2Heat, Open Power System Data | DOI 10.25832/when2heat | to check | `data/get_when2heat.py` | TBD | review tag to import | proposed | -- |
| D-004 | PV and weather inputs | PVGIS plus KNMI or DWD/ERA5 weather | URLs to verify in E2.S1 | to check | `data/get_weather_pv.py` | TBD | review tag to import | proposed | -- |
| D-005 | Flexibility delivery statistics | Mueller and Jansen 2019, Applied Energy 239:836-845 | DOI/URL to verify in E2.S1 | citation only | TBD | TBD | review tag to import | proposed | -- |
| D-006 | EU flexibility procurement framing | EU Directive 2019/944 Article 32 | URL to verify in E2.S1 | public law | TBD | TBD | review tag to import | proposed | -- |
| D-007 | Transformer loading rationale | IEC 60076-7 loading guide | standard reference to verify | standard; access limits to check | TBD | TBD | review tag to import | proposed | -- |
| D-008 | Indicative Dutch unit costs | Cicenas 2025 TU Delft MSc thesis with Stedin/Eneco context; PI-supplied local PDF | Local raw source: `data/raw/cicenas_2025_thesis.pdf`; bibliographic anchor: `Literature_review_combined.md` line 133 | Internal/project source approved by PI; do not commit or redistribute PDF; cite thesis exactly; every extracted number needs value/unit/context/page/table provenance and PI sign-off before manuscript use | `data/get_unit_costs.py` | PDF sha256 `96EF9625BA0AFEE2910189A61967943BA3BCD460AE3AC080B847C4D8DD7D99C0`; metadata: `data/metadata/unit_costs/cicenas_2025_thesis_metadata.json`; raw PDF ignored | [V] `Literature_review_combined.md` line 133; COST-001 | source-approved; extracted values pending | PI approved source use in chat, 2026-07-10; extracted values not yet signed |

