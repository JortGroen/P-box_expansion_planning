# E2.S3 HP-001 Executable Value-Binding Decision Brief

Decision brief ID: `E2-S3-HP001-EXECUTABLE-VALUE-BINDING-BRIEF`

Status: proposed decision brief only. This brief translates the merged executable value-binding packet into concrete PI approval options. It does not approve annual HP TWh values, does not make any annual HP load executable, does not sign D-004 paired-weather acceptance or cold-spell tolerances, and does not run net-load/event/`P(E)`/capacity/manuscript analysis.

## Plain-Language Decision

The HP model already knows the approved When2Heat shape/COP boundary: residential SFH/MFH space heat plus domestic hot water. What remains is deciding how much local Alkmaar heat demand becomes 2035 heat-pump-served demand, and proving the weather member used by HP is the same realization used by PV.

A later executable binding PR needs explicit PI approval IDs for seven keys:

| Key | Simple meaning | Proposed approval option |
|---|---|---|
| `value_column` | Which PBL scenario/reference column supplies local heat intensity. | Approve `Referentie_2030`, or name a replacement column from `Alkmaar_strategie.csv`. |
| `denominator` | What multiplies PBL `[GJ/weq/jaar]` intensities into local annual GJ. | Approve `I11_woningequivalenten [Woning]`, or name a replacement denominator. |
| `unit_conversion` | How annual GJ becomes annual TWh. | Confirm division by `3,600,000` because `1 TWh = 3,600,000 GJ`. |
| `sfh_mfh_split` | How local heat demand is split across HP-001 building classes. | Approve CBS 85035NED count-share split, or choose area-weighted CBS split as a signed sensitivity/alternative. |
| `adoption_electrification` | What share of local residential heat demand is served by HPs in 2035. | Choose one of the options below and state whether it applies to both space heat and DHW. |
| `d004_paired_weather_acceptance` | Proof HP and PV profiles are driven by the same WEATHER-001 member. | Still blocked until paired evidence is run and signed. |
| `cold_spell_tolerances` | Numerical tolerances for accepting HP cold-weather behavior. | Still blocked until PI signs tolerance values before the real check. |

## Annual Value-Binding Choices

### 1. PBL value column

Recommended approval: use `Referentie_2030` from PBL Startanalyse 2025 Alkmaar `Alkmaar_strategie.csv`.

Reason: it is a reference heat-demand column, not a strategy/pathway output. This keeps local heat-demand estimation separate from adoption/electrification.

Amendment option: the PI may instead select another named PBL value column, such as a strategy or variant column, but that would mix heat-demand intensity with pathway assumptions and should be recorded as a different signed route.

### 2. Denominator

Recommended approval: use `I11_woningequivalenten [Woning]` from the same PBL neighbourhood rows.

Reason: the approved D013-PBL-MAPPING/A-015 interpretation treats `H23_Vraag_RV_w` and `H24_Vraag_TW_w` as residential `[GJ/weq/jaar]` intensities, so residential dwelling equivalents are the direct multiplier.

Amendment option: use a CBS dwelling count denominator only if the PI wants a CBS-normalized proxy instead of PBL's own neighbourhood WEQ denominator. That would need a new formula note because the source unit is per WEQ, not per CBS dwelling.

### 3. Unit conversion

Recommended approval: divide summed GJ/year by `3,600,000` to obtain TWh/year.

Reason: `1 GJ = 277.777... kWh`, and `1 TWh = 1,000,000,000 kWh`, so `1 TWh = 3,600,000 GJ`.

### 4. SFH/MFH split

Recommended approval: use CBS 85035NED Alkmaar `2026JJ00` count shares between `Eengezinswoningen totaal` and `Meergezinswoningen totaal`.

Reason: it is the simplest public CBS class crosswalk and avoids treating average floor area as an unapproved heat-demand proxy.

Alternative: use an area-weighted CBS split as a sensitivity if the PI wants SFH/MFH heat allocation to reflect larger average SFH dwelling area. This is more physical, but it is also an extra scientific assumption.

## 2035 HP Adoption/Electrification Options

The adoption multiplier is not a data-cleaning choice. It determines how much of the local residential space/DHW heat demand becomes HP-served 2035 thermal demand:

```text
H_HP_TWh[class,end_use,scenario] = H_local_TWh[class,end_use] * f_HP_service[class,end_use,scenario]
```

DHW must be explicit. A space-heating adoption fraction may be reused for DHW only if the signed scenario means full residential HP service for both space heat and domestic hot water.

| Option | Candidate approval | Provenance | Boundary |
|---|---|---|---|
| A: first-pass single value | PI signs one explicit service fraction for all four HP-001 components. A simple first-pass candidate is `f_HP_service = 0.50` for SFH/MFH space and DHW. | Author-specified PI scenario applied to D-013 local heat-demand evidence. | Transparent planning sensitivity, not source-estimated adoption and not a forecast. |
| B: low/mid/high scenario set | PI signs `low = 0.25`, `mid = 0.50`, `high = 0.75`, applied to both space and DHW unless amended. | Author-specified PI scenario grid applied to D-013 local heat-demand evidence. | No probabilities are assigned to the three cases; use only as labelled scenarios/sensitivities. |
| C: PBL pathway sensitivity | PI signs a PBL pathway column, with `A08_Aandeel_eWP_GJ` as the candidate HP-served heat-share field, plus `A07_Aandeel_eWP_WEQ` and `A02_Aansl_eWP` as diagnostics. `Variant_s1a_B_LuchtWP` is the most directly named air-heat-pump pathway column visible in the schema. | D-013 PBL Startanalyse 2025 Alkmaar ZIP, `Alkmaar_strategie.csv`. | Treat as pathway/suitability sensitivity unless PI explicitly accepts it as the 2035 adoption/electrification scenario; Startanalyse pathway output is not automatically a 2035 forecast. |
| D: external adoption source | PI supplies or approves a public 2035 residential HP adoption/electrification source, including whether it covers DHW. | Future public source/register row or signed PI scenario. | Most source-driven option, but not executable until source, license/provenance, and class/end-use mapping are recorded. |

Agent C recommendation for the next executable-binding approval: approve choices 1-4 as the heat-demand formula if acceptable, then choose either Option A for the smallest first-pass executable scaffold or Option B for a simple sensitivity set. Keep Option C as a PBL-pathway sensitivity and Option D as a future source-driven replacement if a better public 2035 adoption source is preferred.

## What Still Blocks Final HP Executable Use

Even after annual value binding is signed, final integrated HP use still needs two weather/cold-spell approvals.

For `d004_paired_weather_acceptance`, the later evidence must show that HP and PV outputs preserve the same `member_id`, `shared_weather_driver_id`, source/provenance, UTC/local timestamp axis, timestep count, cadence, and WEATHER-001 content identity for each paired member. The approved D-004 source/member bundle exists for internal first-screen use, but final paired HP/PV acceptance has not been run or signed.

For `cold_spell_tolerances`, the PI must sign numerical tolerances before the real check is run. The predeclared design calls for coldest-window and near-freezing diagnostics, with plots/tables that compare D-004 weather-driven HP behavior against the When2Heat-derived shape/COP expectations. This brief does not select those tolerances and does not run the check.

## Exact PI Reply That Would Be Sufficient

A complete approval could be recorded later if the PI replies with all of the following, or amended equivalents:

```text
Approve E2-S3-HP001 executable annual value binding with:
value_column = Referentie_2030
denominator = I11_woningequivalenten [Woning]
unit_conversion = GJ_per_year / 3,600,000 = TWh_per_year
sfh_mfh_split = CBS 85035NED count-share split
adoption_electrification = <Option A/B/C/D with exact fractions or source fields, and DHW boundary>
```

That approval would still not sign `d004_paired_weather_acceptance` or `cold_spell_tolerances`; those need separate approval after the paired-weather/cold-spell evidence exists.

## Suggested STATUS Update

E2.S3 HP remains scaffold/readiness. A simple PI-facing HP executable value-binding decision brief now states concrete approval options for value column, denominator, unit conversion, SFH/MFH split, 2035 HP service/adoption/electrification, and the remaining D-004 paired-weather/cold-spell blockers; no annual HP TWh values or integrated results are executable.
