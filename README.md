# faststack-mcp

`faststack-mcp` is a local-first, read-only MCP server for Claude Code that indexes and
searches modern full-stack projects with focus on:

- FastAPI backends
- React frontends (TypeScript / JavaScript, TSX / JSX)
- PostgreSQL projects with SQL/migrations
- JSON / JSONL + manifest and RAG artifact metadata
- common frontend and backend config files

It is intentionally conservative:

- local folder indexing only (no GitHub/network access),
- read-only operations on indexed files,
- JSON caches stored under `~/.faststack-mcp/`,
- compact symbol + text retrieval for AI coding workflows.

## What is included

- MCP server over stdio with tools:
  - `index_folder`
  - `list_projects`
  - `get_file_tree`
  - `get_file_outline`
  - `search_symbols`
  - `get_symbol`
  - `search_text`
  - `get_project_outline`
  - `invalidate_cache`
- Local parsers for:
  - Python / FastAPI (`ast`)
  - TypeScript / TSX (`regex` + optional Tree-sitter fallback)
  - SQL / migrations (`regex` parser + heuristics)
  - JSON / JSONL (`dict` + `list` roots, chunks, manifest extraction)
  - config parsing (`package.json`, `pyproject.toml`, `vite`, `eslint`, `tsconfig`, `toml`, `yaml`, `ini`)
  - Tailwind config / class usage heuristics
  - env files (`.env.example` by default; `.env*` opt-in)
- Cached JSON indexes at:
  - `~/.faststack-mcp/projects/<project_id>/index.json`

## Supported inputs

- `py`
- `ts`
- `tsx`
- `js`
- `jsx`
- `json`
- `jsonl`
- `sql`
- `toml`
- `yml`
- `yaml`
- `ini`
- `.env`
- `.env.local`
- `env.example`
- `.env.*`
- `tailwind.config.js`
- `tailwind.config.ts`
- `package.json`
- `pyproject.toml`
- `alembic.ini`
- `vite.config.js`
- `vite.config.ts`
- `vite.config.mjs`
- `vite.config.cjs`
- `eslint.config.js`
- `tsconfig.json`
- `tsconfig.app.json`
- `tsconfig.node.json`
- `manifest.json`
- `chunks.jsonl`
- `index.faiss`

Files in common generated/fail-safe directories (and sensitive files) are skipped:

`.git`, `node_modules`, `.next`, `dist`, `build`, `coverage`, `.venv`, `venv`,
`__pycache__`, `.mypy_cache`, `.pytest_cache`, `.idea`, `.vscode`, `.claude`,
as well as `.env*`, `*.key`, `*.pem`, `id_rsa`, `id_ed25519`, etc.

## Installation, Publishing, and Supported Indexes

### Installation options

`faststack-mcp` can be used in 3 ways:

- from a local folder
- from GitHub
- from PyPI after publishing

---

### Local development install

If the project lives at:

`C:\Users\91997\faststack-mcp`

use:

```powershell
cd C:\Users\91997\faststack-mcp
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

### GitHub install

```powershell
pip install "git+https://github.com/Evaan-devlops/mcp.git"
```

## Claude Code setup (example)

Add a server entry pointing to the `faststack-mcp` command and prefer stdio transport.
No network access is required by design; all indexing and retrieval is local.

Example JSON (adjust paths as needed):

```json
{
  "mcpServers": {
    "faststack": {
      "command": "faststack-mcp"
    }
  }
}
```

## CLI

- `faststack-mcp` starts the MCP server via stdio.
- `faststack-mcp --help` prints CLI usage.

## Tool behavior

- `index_folder(path, force=False, max_file_size=2097152, include_env_files=False)`
  - indexes a local folder once per project fingerprint
  - returns `project_id`, file and symbol counts, detected languages and frameworks
- `list_projects()`
  - lists all cached local projects and stats
- `get_file_tree(project_id)`
  - returns a filtered tree of indexed files
- `get_file_outline(project_id, file_path)`
  - returns symbols for one file
- `search_symbols(project_id, query, kind?, language?)`
  - practical ranked search over indexed symbols
- `get_symbol(project_id, symbol_id)`
  - reads symbol by stored byte range and returns exact snippet + metadata
- `search_text(project_id, query)`
  - fallback text search with small context windows
- `get_project_outline(project_id)`
  - grouped summary for:
    - backend routes
    - backend models/services/repos
    - frontend app/pages/components/hooks/store/api/utils/types
    - frontend hooks/store/api/types/lib/http pages by path when symbols are sparse
    - database migrations
    - config files
    - RAG/artifact files
    - env/config templates
- parser metadata in symbols is preserved for debugging (`parser` and `rag`/`env` markers)
- `invalidate_cache(project_id)`
  - removes one cached project index

## Security notes

- Path normalization and root confinement on every file lookup.
- Symlink escape checks during reads and indexing.
- Binary detection and size cap (default 2MB).
- Query/result caps for searches.
- Cache isolated at `~/.faststack-mcp`.
- No write/shell operations against indexed project files.

## Limitations

- Symbol parsing is intentionally heuristic.
- TypeScript/TSX and Tailwind parsing is best-effort and optimized for speed.
- SQL parsing is lightweight but practical for migrations and schema-level scans.
- No source-file network fetch or remote indexing in normal operation.

## Development

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e .
pytest
```


## Env parsing behavior

- `.env.example` is indexed by default and parsed as `env_variable` metadata with masked values.
- `.env` and `.env.*` are skipped unless `include_env_files=True` is passed to `index_folder`.
- Raw values are never persisted or surfaced in signatures/metadata (`***MASKED***` only is stored).

## Project structure coverage

- Frontend-first paths are recognized and bucketed in `get_project_outline` for:
  - `src/app`, `src/pages`, `src/components`, `src/hooks`, `src/store`, `src/utils`,
    `src/types`, `src/lib/http`, `src/features/*/components`, `src/features/*/api`
- Backend/backend-like paths are grouped as routes, models/services/repos, and migrations.
- `backend/rag_artifacts/` is detected as RAG storage; `manifest.json` and `chunks.jsonl`
  are treated as artifact metadata sources while `index.faiss` is metadata-only.

   What feature and functionality are we getting from faststack-mcp? How is it beneficial for us?

● Searched for 1 pattern, read 2 files (ctrl+o to expand)

● Here's a clear breakdown of what faststack-mcp gives us:

  ---
  What is faststack-mcp?

  A local-first, read-only MCP server that indexes your codebase and exposes it to Claude Code via structured tools —  
  so Claude can navigate and understand large projects efficiently without reading every file blindly.

  ---
  Tools you Get (9 total)

  ┌─────────────────────┬─────────────────────────────────────────────────────────────────┐
  │        Tool         │                          What it does                           │
  ├─────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ index_folder        │ Scans and indexes a project folder, returns project_id + stats  │
  ├─────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ list_projects       │ Lists all previously indexed projects                           │
  ├─────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ get_file_tree       │ Returns the filtered file tree of an indexed project            │
  ├─────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ get_file_outline    │ Lists all symbols (functions, classes, routes) in a single file │
  ├─────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ search_symbols      │ Ranked search for a symbol by name/kind/language                │
  ├─────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ get_symbol          │ Fetches the exact code snippet for a specific symbol            │
  ├─────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ search_text         │ Fallback text search with context windows                       │
  ├─────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ get_project_outline │ High-level grouped summary of the whole project                 │
  ├─────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ invalidate_cache    │ Clears a project's cached index to force re-indexing            │
  └─────────────────────┴─────────────────────────────────────────────────────────────────┘

  ---
  Languages & Frameworks Supported

  - Python / FastAPI (AST-based parsing)
  - TypeScript / JavaScript / TSX / JSX (React frontends)
  - SQL / migrations
  - JSON / JSONL (including RAG artifact metadata)
  - Config files: package.json, pyproject.toml, tsconfig.json, vite.config, eslint.config, tailwind.config,
  .env.example, YAML, TOML, INI

  ---
  Key Benefits for Us

  1. Faster codebase navigation — Instead of grepping raw files, Claude gets structured symbol maps. Finding
  AuthService or a FastAPI route is instant.
  2. Project outline in one call — get_project_outline gives a grouped summary (routes, models, services, components,  
  hooks, store, migrations) without reading individual files.
  3. Context window efficiency — Claude fetches only the relevant symbol snippet (get_symbol) rather than loading      
  entire files, preserving context for actual reasoning.
  4. Secure & local — No network access, no writes, no secret leakage (.env values are masked as ***MASKED***), cached 
  locally under ~/.faststack-mcp/.
  5. Full-stack aware — It understands both the backend (FastAPI routes, models, repos) and frontend (React pages,     
  components, hooks, store, API layers) structure simultaneously.

  ---
  Practical Workflow

  index_folder(".")          → get project_id
  get_project_outline(id)    → understand full structure
  search_symbols(id, "Foo")  → find a specific class/function
  get_symbol(id, symbol_id)  → read exact code snippet
  search_text(id, "query")   → fallback for non-symbol content

  In short: it makes Claude significantly faster and more accurate on large codebases by replacing blind file reads    
  with structured, indexed lookups.

