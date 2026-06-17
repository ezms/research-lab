# research-lab

A research laboratory for collecting and processing public data to inform domain decisions. Each research lives as an autonomous vertical slice with its own sources, pipeline, and analysis layer. Shared capabilities (HTTP, storage, database) live in a platform layer.

The first research hosted here is **housing reality in Brazil**, collecting Census 2010 microdata from IBGE as the empirical foundation for a long-term smart house project.

## Architecture

The project combines three patterns:

- **Vertical Slice Architecture** — each research is a self-contained slice under `research/`. Slices do not share domain logic with each other.
- **Hexagonal (Port/Adapter)** — within each slice, the runner depends on a port (interface), not on concrete sources. Adding a new data source means implementing the port; the runner does not change.
- **DDD vocabulary inside slices** — each slice may have a `domain/` sub-package that declares its own ports and domain types. This keeps slice-specific abstractions out of the platform layer.

```
src/lab/
├── platform/                        # shared infrastructure (no domain logic)
│   ├── data_source/contract.py      # Identifiable, Downloadable, SourceIdentity
│   ├── research/manifest.py         # ResearchManifest base class
│   ├── research/registry.py         # research registry
│   └── storage/                     # DuckDB / MotherDuck ports
└── research/
    └── housing_reality/             # vertical slice
        ├── domain/
        │   └── ports.py             # HousingDataSource port (the slice's own abstraction)
        ├── sources/                 # adapters that implement HousingDataSource
        │   ├── census_2010.py       # Census Demográfico 2010 (per-UF, IBGE FTP)
        │   └── pnadc_visita1.py     # PNADC Anual Visita 1 (national file, split by UF)
        ├── pipeline/
        │   └── runner.py            # iterates _SOURCES, knows nothing source-specific
        ├── params.py                # HousingRealityParams (ufs filter, pnadc_year)
        └── manifest.py              # registers the research in the catalog
```

### HousingDataSource port

Every data source in `housing_reality` implements two methods:

| Method | Returns |
|---|---|
| `collect(params)` | `dict[str, dict[str, Path]]` — `{uf: {file_type: parquet_path}}` |
| `find_local(params)` | same shape, or `None` if nothing collected yet |

The runner iterates `_SOURCES: list[type[HousingDataSource]]`. To add a new source, implement the port and append the class to that list — no other file changes.

Intermediate data is always stored as Parquet (Snappy-compressed). Steps are idempotent — if the output already exists the step is skipped.

## Research catalog

| ID | Name | Sources | Status |
|---|---|---|---|
| `housing_reality` | Realidade Habitacional | Censo Demográfico 2010 · PNADC Anual Visita 1 | active |

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

### Adding a new data source to an existing research

Example: adding Census 2022 to `housing_reality`.

1. Create `src/lab/research/housing_reality/sources/census_2022.py`.
2. Implement `HousingDataSource` — define `collect(params)` and `find_local(params)`.
3. Append the class to `_SOURCES` in `housing_reality/pipeline/runner.py`.

That's it. `manifest.py`, `params.py`, and the runner loop do not change.

### Adding a new research

1. Create `src/lab/research/<id>/` with `manifest.py`, `params.py`, `sources/`, `pipeline/`, and `domain/ports.py`.
2. Define the slice's own port in `domain/ports.py` (equivalent of `HousingDataSource`).
3. Implement the port for each data source under `sources/`.
4. Write a runner that iterates over registered sources via the port.
5. Register the manifest with `@register_research` on a subclass of `ResearchManifest`.
6. Import the manifest at startup (e.g. in `streamlit_app.py`) so it registers itself.
