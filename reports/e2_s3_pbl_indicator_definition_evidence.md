# E2.S3 PBL Indicator Definition Evidence

Status: PI-facing evidence and decision note only. This packet does not approve PBL Startanalyse columns, annual HP TWh values, 2035 HP adoption, D-004 acceptance, cold-spell tolerances, net-load/event analysis, `P(E)`, capacity-screen conclusions, threshold runs, manuscript numbers, or probability results.

## Question

The current HP-001 local scaling proposal uses these candidate rows from D-013 `Alkmaar_strategie.csv`:

| Proposed use | Candidate PBL row | Unit in CSV | Current interpretation status |
| --- | --- | --- | --- |
| Residential space heat intensity | `H23_Vraag_RV_w` | `[GJ/weq/jaar]` | Inferred, not explicitly documented |
| Residential domestic hot water intensity | `H24_Vraag_TW_w` | `[GJ/weq/jaar]` | Inferred, not explicitly documented |
| Residential total heat diagnostic | `H22_Vraag_totaal_w` | `[GJ/weq/jaar]` | Inferred, not explicitly documented |

The gap is whether public PBL documentation explicitly defines `H22`, `H23`, `H24`, and the `_w` suffix. The current route inference comes from the raw code pattern, the base indicator definitions `H02 = Ruimteverwarming` and `H03 = Warm tapwater`, and the visible woning/utiliteit split in the 2025 municipality files.

## Sources Checked

### D-013 Alkmaar ZIP

Raw file: `data/raw/hp_scaling/pbl_startanalyse_2025_alkmaar.zip`

ZIP members:

| Member | Evidence |
| --- | --- |
| `README_gemeentebestanden.txt` | Explains the municipality bundle contains `_bebouwing.csv`, `_strategie.csv`, and `_totaalbebouwing.csv`. It states `_strategie.csv` contains Startanalyse results where, for every calculated variant and reference situation, neighbourhood-level `Hoofdindicatoren`, `Kostenindicatoren`, `Aansluitingen`, and `Gevoeligheidsanalyses` are written. It does not define `H22`, `H23`, `H24`, `Vraag_RV_w`, `Vraag_TW_w`, or `_w`. |
| `Alkmaar_strategie.csv` | Contains the candidate rows themselves. The first occurrence scan found row 40 `H22_Vraag_totaal_w`, row 41 `H23_Vraag_RV_w`, and row 42 `H24_Vraag_TW_w`, all with unit `[GJ/weq/jaar]`; row 46 `H28_Vraag_totaal_u`, row 47 `H29_Vraag_RV_u`, and row 48 `H30_Vraag_TW_u` appear as parallel `_u` rows. This supports the woning/utiliteit suffix inference but is not an external dictionary. |

The README is useful provenance for the role of `_strategie.csv`, but it is not the missing indicator dictionary.

### ASA25 Excel Template

Local inspection file: `C:\tmp\ASA25_sjabloon_buurttabellen.xlsx`

Public source: PBL Dataportaal lists `ASA25 Sjabloon ter ondersteuning van analyse buurttabellen.xlsx`, 18.8 MB.

Workbook sheets found: `Bestandsgids`, `Bebouwing`, `Strategieresultaten`, `Variantresultaten`, `Data resultaten gemeente`, `Data bebouwing gemeente`, `Zoeklijsten`, `Gefilterde resultaten buurt`, and `Gefilterde bebouwing buurt`.

Exact evidence:

| Sheet/cell | Evidence |
| --- | --- |
| `Strategieresultaten!B202:D204` | Displays the base code table with `Code`, `Indicator`, `Eenheid`; `B203 = H02`, `C203 = Ruimteverwarming`; `B204 = H03`, `C204 = Warm tapwater`. Unit cells are formula lookups into the pasted filtered-result data. |
| `Variantresultaten!B189:D191` | Displays the same base code table for variants; `B190 = H02`, `C190 = Ruimteverwarming`; `B191 = H03`, `C191 = Warm tapwater`. |
| `Gefilterde resultaten buurt!I1:N1` | Preserves separate headers for `I09_aantal_woningen [Aansluiting]`, `I10_aantal_utiliteit [Aansluiting]`, `I11_woningequivalenten [Woning]`, and `I14_WEQ_utiliteit [Aansluiting]`. This supports a woning/utiliteit split in the result schema. |
| Full workbook search | Search terms `H22`, `H23`, `H24`, `Vraag_RV_w`, `Vraag_TW_w`, and `Vraag_totaal_w` did not return an explicit template definition. Search terms `_w` and `_u` found workbook headers and formulas, but not a suffix dictionary. |

The template strengthens the base H02/H03 and woning/utiliteit context. It does not explicitly define the suffixed H22-H24 rows.

### PBL Gebruikershandleiding Startanalyse 2025

Public source: `Gebruikershandleiding. Toelichting op het gebruiken en interpreteren van de resultaten van de Actualisatie van de Startanalyse 2025`, PBL publication number 5633, 13 March 2025.

Exact evidence:

| Page/lines | Evidence |
| --- | --- |
| p. 19, lines 457-472 in the extracted PDF text | Defines energy demand indicators as demand for purposes within the building: space heating, hot tap water, ventilation, cooling, and appliances. It states H02-H06 are parts of H01 and sum to H01. |
| p. 19, lines 474-480 | Table 9 maps `H01` to `Energievraag`, `H02` to `Ruimteverwarming`, and `H03` to `Warm tapwater`, each in `GJ/weq/jaar`. |
| p. 20, lines 482-485 | Text definitions state H02 is the part of total energy demand used for space heating and H03 is the part used for hot tap water. |

Searches for `H22`, `H23`, `H24`, `Vraag_RV_w`, `Vraag_TW_w`, `Vraag_totaal_w`, and `_w` did not find an explicit definition in the user guide.

### PBL Dataportaal and Startanalyse Website

Exact public-source evidence:

| Source | Evidence |
| --- | --- |
| PBL Dataportaal 2025 page | Describes the 2025 Startanalyse data as covering both homes and utility buildings and says data are calculated at neighbourhood level with Vesta MAIS. It states the data can be used under CC BY 4.0 NL and links the ASA25 Excel template. |
| Startanalyse `Gemeentedata` page | States the municipality ZIP contains a table with strategy/variant calculation results per neighbourhood, including national costs and indicators such as energy use, plus the Excel template for pasted CSV data. |
| Startanalyse `Aan de slag` page | Says the user guide contains explanations of indicators and codes, municipality CSVs contain building stock plus all indicators, and PBL/NPLW contact channels are available for interpretation questions. |

These pages establish provenance, license, and product roles. They do not provide a public dictionary for `H22_Vraag_totaal_w`, `H23_Vraag_RV_w`, `H24_Vraag_TW_w`, or `_w`.

### PBL Concept Verdiepend Rapport

Public source: `Verdieping op de actualisatie van de Startanalyse`, concept report, PBL publication number 5630.

The concept report was checked for `H23`, `Vraag_RV_w`, `Vraag_TW_w`, and related terms. It provides methodological background on space heating, hot tap water, and heat-pump variants, including examples where heat pumps serve both space heating and hot tap water. It does not define the suffixed result-row dictionary.

## Evidence Assessment

Explicit evidence found:

- PBL explicitly defines base `H02` as `Ruimteverwarming` and base `H03` as `Warm tapwater` in `GJ/weq/jaar`.
- PBL public pages explicitly identify the municipality ZIP and Excel template as official Startanalyse result products.
- The official `Alkmaar_strategie.csv` contains `H22_Vraag_totaal_w`, `H23_Vraag_RV_w`, and `H24_Vraag_TW_w` rows with `[GJ/weq/jaar]`.
- The official `Alkmaar_strategie.csv` also contains parallel `_u` rows, and the template/result headers separately expose woning and utiliteit counts/WEQ fields.

Explicit evidence not found:

- No public dictionary was found that states `H23_Vraag_RV_w = residential/woningen space-heating demand`.
- No public dictionary was found that states `H24_Vraag_TW_w = residential/woningen hot-tap-water demand`.
- No public dictionary was found that states `H22_Vraag_totaal_w = residential/woningen total demand`.
- No public dictionary was found that defines `_w` as `woningen` or `_u` as `utiliteit`.

Conclusion: the current mapping remains a transparent inference, not a documented PBL definition. The existing HP route proposal should therefore not be upgraded from proposed to approved on this evidence alone.

## PI Options

Recommended option: ask PBL or a Startanalyse/NPLW expert for the result-row dictionary or written confirmation that:

- `_w` means `woningen`;
- `_u` means `utiliteit`;
- `H22_Vraag_totaal_w`, `H23_Vraag_RV_w`, and `H24_Vraag_TW_w` are the residential/woningen split counterparts of base `H01`, `H02`, and `H03`;
- the `Referentie_2030` values may be used as useful-thermal annual heat-demand intensities for HP-001 local scaling after multiplying by the correct residential denominator.

Alternative option: approve the mapping as a transparent assumption. This would keep the inference auditable but would require a signed assumption/decision before any annual HP scaling values become executable.

Conservative option: choose a different HP local scaling source with explicit residential space-heat and DHW definitions, using PBL Startanalyse only as pathway/suitability context.

## Recommendation

Do not approve executable HP annual scaling from `H23_Vraag_RV_w` and `H24_Vraag_TW_w` until the PI either obtains explicit PBL/expert confirmation or signs the mapping as a transparent assumption. The D-013 source-use route should remain proposed; no D-013 value, PBL column, unit conversion, 2035 adoption/electrification multiplier, or integrated HP load is approved by this packet.
