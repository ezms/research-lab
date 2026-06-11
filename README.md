# research-lab

A research laboratory for collecting and processing public data to inform domain decisions. Each research lives as an autonomous vertical slice with its own sources, pipeline, and analysis layer. Shared capabilities (HTTP, storage, database) live in a platform layer.

The first research hosted here is **housing reality in Brazil**, collecting Census 2010 microdata from IBGE as the empirical foundation for a long-term smart house project.

## Architecture

```
src/lab/
├── platform/                    # shared capabilities
│   ├── data_source/contract.py  # DataSource protocol (identify, download, parse, map_variables)
│   ├── research/manifest.py     # ResearchManifest base class
│   ├── research/registry.py     # research registry
│   └── storage/                 # database and object storage ports
└── research/
    └── housing_reality/         # vertical slice
        ├── sources/             # DataSource adapters (Census 2010)
        ├── pipeline/            # orchestrates sources → parquet
        ├── domain/              # domain types and rules
        └── manifest.py          # registers the research
```

Each `DataSource` implements four steps:

| Method | Input | Output |
|---|---|---|
| `identify()` | — | `SourceIdentity` (name, version, provider) |
| `download()` | — | `Path` to raw file |
| `parse(file_path)` | raw file | `dict[str, Path]` to typed parquets |
| `map_variables(parsed)` | typed parquets | `dict[str, Path]` to named parquets |

Intermediate data is always stored as Parquet (Snappy-compressed). Steps are idempotent — if the output already exists the step is skipped.

## Research catalog

| ID | Name | Source | Status |
|---|---|---|---|
| `housing_reality` | Realidade Habitacional | IBGE — Censo Demográfico 2010 | active |

See [docs/researches/housing_reality.md](docs/researches/housing_reality.md) for detailed variable documentation.

## Stack

- Python 3.13 · [uv](https://docs.astral.sh/uv/) package manager
- [DuckDB](https://duckdb.org/) — analytical queries over local parquets
- [Streamlit](https://streamlit.io/) — data exploration UI
- [pandas](https://pandas.pydata.org/) + [pyarrow](https://arrow.apache.org/docs/python/) — data processing
- [httpx](https://www.python-httpx.org/) — HTTP downloads
- [MotherDuck](https://motherduck.com/) — optional cloud DuckDB (see `.env.example`)

## Setup

The project ships with a devcontainer. Open it in VS Code or any devcontainer-compatible editor and the environment builds automatically.

### Without devcontainer

```bash
uv sync
```

### Environment variables

Copy `.env.example` to `.env` and fill in the values you need:

```bash
cp .env.example .env
```

`MOTHERDUCK_TOKEN` is optional — without it the UI stores data locally in `data/research.duckdb`.

## Running the UI

```bash
uv run streamlit run src/lab/ui/streamlit_app.py --server.headless true
```

Open [http://localhost:8501](http://localhost:8501). The catalog lists all registered researches. Click **Coletar** to start a background download, or **Visualizar** if local data already exists.

## Running a pipeline directly

```bash
uv run python -c "
import lab.research.housing_reality.manifest
from lab.research.housing_reality.params import HousingRealityParams
from lab.research.housing_reality.pipeline import runner
from lab.enums.uf import UF

runner.run(HousingRealityParams(ufs=[UF.AC]))
"
```

## Development

```bash
uv sync --all-extras
uv run pytest
```

### Adding a new research

1. Create `src/lab/research/<id>/` with `manifest.py`, `params.py`, `sources/`, `pipeline/`.
2. Implement `DataSource` for each source.
3. Register the manifest with `@register_research` on a subclass of `ResearchManifest`.
4. Import the manifest module somewhere at startup (e.g. in `streamlit_app.py`) so it registers itself.
