# E2.S3 HP Route PI Approval Note

Status: approval note only. No executable HP scaling values are introduced.

PI decision requested: approve or amend the following HP-001 local scaling route.

| Choice | Proposed route |
|---|---|
| PBL space heat indicator | `Alkmaar_strategie.csv`: `Code_Indicator = H23_Vraag_RV_w`, unit `[GJ/weq/jaar]`, value column `Referentie_2030`. |
| PBL DHW indicator | `Alkmaar_strategie.csv`: `Code_Indicator = H24_Vraag_TW_w`, unit `[GJ/weq/jaar]`, value column `Referentie_2030`. |
| Denominator | PBL `I11_woningequivalenten [Woning]`; convert local demand as `sum(intensity_GJ/weq/year * WEQ) / 3,600,000` to TWh/year. |
| SFH/MFH allocation | CBS `85035NED`, Alkmaar `GM0361`, period `2026JJ00`: `SFH = ZW10290 Eengezinswoningen totaal`, `MFH = ZW10340 Meergezinswoningen totaal`. Agent C recommends count-share allocation unless PI explicitly wants area-weighted sensitivity. |
| Space/DHW separation | Keep `H23` and `H24` separate through SFH/MFH allocation and map later to the four HP-001 components; do not aggregate before component provenance is recorded. |
| Still missing | A signed 2035 HP adoption/electrification multiplier `f_HP_service[class,end_use,scenario]`, including full-electric versus hybrid boundary and whether DHW is served. |

Until the PI approves or amends this route and signs the missing 2035 adoption/electrification assumption, annual HP TWh values remain unsigned and non-executable. This note does not sign D-004, cold-spell tolerances, paired-weather acceptance, net-load/event/`P(E)`, capacity screens, threshold runs, manuscript numbers, or probability results.