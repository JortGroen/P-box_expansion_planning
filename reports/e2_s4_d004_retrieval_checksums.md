# E2.S4 D-004 Retrieval Checksums

Status: proposed for PI review. This PR performs only the PI-approved narrow
retrieval for `d004_alkmaar_berkhout_2014_2023_v1`; it records checksums and
metadata, keeps raw files ignored, and does not accept D-004 for analysis.

## Retrieved Files

| Role | Raw path | Size bytes | SHA-256 |
|---|---:|---:|---|
| PVGIS hourly series reference | `data/raw/weather_pv/pvgis/d004_alkmaar_berkhout_2014_2023_v1/pvgis_seriescalc_d004_alkmaar_berkhout_2014_2023_v1.json` | 8212761 | `dca94839809cefd165edd964ddd269fbf6cc9fde7c5875905a84eb0ae830e2dc` |
| PVGIS typical-year reference | `data/raw/weather_pv/pvgis/d004_alkmaar_berkhout_2014_2023_v1/pvgis_tmy_d004_alkmaar_berkhout_2014_2023_v1.json` | 1269604 | `54af286aad35a675c9993eafe122ad2d742dc28fac71608052b02c47387cdc34` |
| KNMI station 249 hourly ZIP, 2011-2020 | `data/raw/weather_pv/knmi/d004_alkmaar_berkhout_2014_2023_v1/uurgeg_249_2011-2020.zip` | 1536802 | `f83f255b4f1b7a1f48dba935f8396a99989fa600364425e3a45b6b5218dd4f0e` |
| KNMI station 249 hourly ZIP, 2021-2030 | `data/raw/weather_pv/knmi/d004_alkmaar_berkhout_2014_2023_v1/uurgeg_249_2021-2030.zip` | 838086 | `f68e3797217a91a4121d7aab7146da7f989f96d561c92cb613b70a77d8ed9ef2` |

## Metadata

- Aggregate retrieval manifest:
  `data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_retrieval_manifest.json`
- Per-file checksum metadata:
  `data/metadata/weather_pv/d004_pvgis_pvgis_seriescalc_d004_alkmaar_berkhout_2014_2023_v1_metadata.json`
- Per-file checksum metadata:
  `data/metadata/weather_pv/d004_pvgis_pvgis_tmy_d004_alkmaar_berkhout_2014_2023_v1_metadata.json`
- Per-file checksum metadata:
  `data/metadata/weather_pv/d004_knmi_uurgeg_249_2011-2020_metadata.json`
- Per-file checksum metadata:
  `data/metadata/weather_pv/d004_knmi_uurgeg_249_2021-2030_metadata.json`

## Boundaries

PVGIS-SARAH3 output is recorded as calibration/validation reference material
only. The PVGIS TMY file is not a realized weather member. The KNMI ZIPs are
the approved first D-004 route for later filtering to complete annual members
from 2014 through 2023, but this PR does not implement Q-8 shared-weather
contract code and does not run net-load, congestion, event, `P(E)`, or
manuscript-result analysis.

D-004 remains proposed until the PI reviews the concrete files, versions,
checksums, source-use evidence, and later completeness checks.
