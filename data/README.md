# Data Directory

Data enters the project only through `data/get_*.py` retrieval scripts plus a
row in `registers/DATA_REGISTER.md`.

- `raw/`: downloaded source files; not committed.
- `interim/`: intermediate transforms; not a source of truth.
- `processed/`: reproducible downstream data products.
- `metadata/`: checksums, licenses, and retrieval metadata.

Never hand-edit raw data.

