# research-lab

A research laboratory for domain studies. Each research lives as an autonomous vertical slice with its own domain, data sources, pipeline and analysis. Shared capabilities (HTTP, storage, database, observability) live in the platform layer.

The first research hosted here is **housing reality in Brazil**, supporting the conceptual foundation of a long-term smart house project.

## Structure

```
src/lab/
├── platform/       # shared capabilities (http, storage, database, observability)
└── research/       # vertical slices, one per research
    └── ...
notebooks/          # exploratory analysis notebooks
tests/
data/               # local data (not versioned)
```

## Stack

- Python 3.13
- uv (package manager)
- DuckDB (analytical database)
- pandas (data manipulation)
- httpx (HTTP client)
- boto3 (S3-compatible object storage)
- pyarrow (Parquet I/O)

## Development

The project ships with a devcontainer. Open the folder in a devcontainer-compatible editor and the environment will build automatically.

To run locally without a devcontainer:

```bash
uv sync --all-extras
```
