# faststack-mcp

Local-first, read-only MCP server for Claude Code. Indexes and searches full-stack projects
(FastAPI + React + PostgreSQL) with **SQLite-backed FTS**, **cross-reference graph**, and
**file-watcher** auto-reload — so Claude reads only what it needs instead of entire files.

---

## Quick Start

**Step 1 — Install**

```powershell
# From local source (development)
cd C:\path\to\faststack-mcp
pip install -e .

# From GitHub
pip install "git+https://github.com/Evaan-devlops/faststack-mcp.git"

# With optional extras
pip install -e ".[watch]"     # file watcher (watchfiles)
pip install -e ".[postgres]"  # PostgreSQL backend (psycopg2-binary)
pip install -e ".[all]"       # both
```

> **Already have watchfiles / psycopg2 globally?** Nothing extra to install — they're
> picked up automatically.

**Step 2 — Add to Claude Code**

```json
{
  "mcpServers": {
    "faststack": {
      "command": ".venv\\Scripts\\python.exe",
      "args": ["-m", "faststack_mcp"]
    }
  }
}
```

**Step 3 — Index your project**

```
index_folder("/path/to/your/project")          → project_id + counts
index_folder("/path/to/project", watch=True)   → + auto-reindex on file changes
```

**Step 4 — Explore**

```
get_project_outline(project_id)                → structure at a glance (~17 tokens)
search_symbols(project_id, "createUser")       → find functions, routes, hooks, models
get_symbol(project_id, symbol_id)              → exact code snippet only
find_references(project_id, "get_db")          → all files that import / call a symbol
get_file_context(project_id, "db.py", 120)     → 80 lines around line 120
get_file_outline(project_id, "main.py")        → all symbols in one file
search_text(project_id, "HTTPException")       → fallback full-text search
get_file_tree(project_id)                      → directory tree
list_projects()                                → all indexed projects
invalidate_cache(project_id)                   → force full re-index
get_token_usage()                              → cost + per-session averages
```

---

## Tools reference (12 tools)

| Tool | Purpose | Key params |
|------|---------|-----------|
| `index_folder` | Scan & cache a project | `path`, `force`, `watch`, `include_env_files` |
| `list_projects` | Browse cached projects | — |
| `search_symbols` | **Primary nav** — ranked FTS symbol search | `query`, `kind`, `language`, `include_synthetic` |
| `get_symbol` | Read exact code snippet by symbol_id | `symbol_id` |
| `find_references` | **New** — import graph + text scan for a symbol | `symbol_name`, `limit` |
| `get_file_context` | **New** — read N lines around a line number | `file_path`, `around_line`, `radius=40` |
| `search_text` | Full-text search across all files | `query`, `limit` |
| `get_project_outline` | Grouped structure overview | `sections` |
| `get_file_tree` | Directory tree of indexed files | — |
| `get_file_outline` | All symbols in one file | `file_path` |
| `invalidate_cache` | Remove cached index | `project_id` |
| `get_token_usage` | Session cost + tool breakdown | `last_n`, `session_id` |

### `find_references` — dependency impact analysis

```
find_references(project_id, "get_db")
→ {
    symbol_name: "get_db",
    files_found: 3,
    total_usages: 3,
    references: [
      { file_path: "users.py",  usages: [{ line: 5,  context: "from db import get_db" }] },
      { file_path: "auth.py",   usages: [{ line: 12, context: "db = get_db()" }] },
      { file_path: "orders.py", usages: [{ line: 8,  context: "from db import get_db" }] }
    ]
  }
```

Use before modifying a shared symbol to understand blast radius. Uses the import graph built
during `index_folder` (fast path) with a whole-word regex scan as fallback.

### `get_file_context` — surrounding code window

```
get_file_context(project_id, "src/db.py", around_line=120, radius=40)
→ lines 80–160, line 120 marked with >>>
```

Use when `get_symbol` is too narrow — e.g. understanding the code around a symbol boundary,
inspecting a migration function, or reading error-handling context.

---

## Storage backends

Controlled by `FASTSTACK_STORAGE` environment variable.

| Value | Default | When to use |
|-------|---------|-------------|
| `sqlite` | **Yes** | Local dev, any project size. Single `~/.faststack-mcp/faststack.db` with FTS5. |
| `postgres` | No | Shared team index, large projects, or when you want the index in your project DB. Requires `DATABASE_URL`. |
| `json` | No | Backward compat with pre-v0.2 caches. No FTS or reference graph. |

### SQLite (default)

No configuration needed. Features:
- FTS5 virtual table on symbol name + qualified_name + signature
- Combined FTS5 + LIKE fallback (handles `get_db`, `create_user` underscore names)
- `refs` table for `find_references` lookups
- WAL mode — concurrent reads while indexing

### PostgreSQL

```bash
export FASTSTACK_STORAGE=postgres
export DATABASE_URL=postgresql://user:pass@localhost:5433/mydb
```

Features:
- `GENERATED ALWAYS AS` tsvector column + GIN index (zero-maintenance FTS)
- `ts_rank` relevance ordering + ILIKE supplement
- Tables prefixed `faststack_*` (no conflicts with your app tables)
- Batch inserts via `execute_values` (500 rows/page)
- `faststack_references` table for `find_references`

> `psycopg2-binary` must be installed (`pip install psycopg2-binary` or `pip install faststack-mcp[postgres]`).

---

## File watcher (auto-reindex)

```python
# Start watcher alongside indexing
index_folder("/path/to/project", watch=True)
```

- Uses `watchfiles` (install: `pip install watchfiles` or `pip install faststack-mcp[watch]`)
- 1.5 s debounce — rapid saves are batched before re-index fires
- Background daemon thread — does not block Claude
- Falls back silently if `watchfiles` is not installed

---

## Cross-reference graph

Built automatically during `index_folder`. Tracks every `import` and `from X import Y`
statement across Python and TypeScript/JavaScript files.

The graph is stored in the index and queried by `find_references`. It enables:
- "What calls / imports this symbol?" in one tool call
- Impact analysis before refactoring shared utilities
- Understanding FastAPI dependency injection (`Depends(get_db)`)

---

## Search — `include_synthetic` behaviour

Synthetic symbols (auto-generated model fields, config keys) are shown or hidden depending
on context:

| Query kind | Default |
|-----------|---------|
| `pydantic_model`, `model`, `type`, `interface` | **Shown** (fields are useful) |
| `config_key`, `config_file`, `tsconfig`, `json_key` | **Shown** |
| Everything else | Hidden |

Override explicitly: `search_symbols(project_id, "User", include_synthetic=True)`

---

## Token usage analytics

```
get_token_usage(last_n=20)
→ {
    totals: { input_tokens, output_tokens, estimated_cost_usd },
    averages: { input_tokens_per_session, cost_usd_per_session },
    tool_breakdown: { get_symbol: { calls: 18, est_saved: 136800 }, ... },
    estimated_tokens_saved_by_mcp: 209000
  }
```

Requires the Stop hook in `~/.claude/settings.json` to log session data.

---

## Supported file types

**Source:** `.py` `.ts` `.tsx` `.js` `.jsx` `.sql`

**Config / meta:** `.json` `.jsonl` `.toml` `.yaml` `.yml` `.ini`

**Named files:** `package.json` `pyproject.toml` `tsconfig.json` `tsconfig.app.json`
`tsconfig.node.json` `vite.config.*` `alembic.ini` `eslint.config.js`
`tailwind.config.js` `tailwind.config.ts` `manifest.json` `chunks.jsonl`
`index.faiss` `bunfig.toml` `.env.example`

**Skipped dirs:** `.git` `node_modules` `.next` `dist` `build` `coverage` `.venv` `venv`
`__pycache__` `.mypy_cache` `.pytest_cache` `.idea` `.vscode` `.claude`

**Sensitive files skipped:** `.env` `.env.*` `*.pem` `*.key` `*.p12` `id_rsa` `id_ed25519`
(`.env*` files opt-in via `include_env_files=True`)

---

## Parsers

| Language | Parser | Extracts |
|----------|--------|---------|
| Python / FastAPI | `ast` | functions, classes, routes, pydantic models, services, repos, decorators, Depends() |
| TypeScript / React | `tree-sitter` + regex fallback | components, hooks, types, interfaces, backend routes/services/repos |
| SQL | regex | tables, views, indexes, functions, procedures, triggers |
| JSON / JSONL | `json.loads` | root keys, RAG chunk fields, manifest metadata |
| Config | `tomllib` / `json` / `yaml` / `ini` | package scripts/deps, tsconfig, vite, eslint, alembic |
| Env | regex (masked) | variable names — values stored as `***MASKED***` |
| Tailwind | heuristics | config keys, className usage |

---

## Security

- All file reads path-confined to the indexed project root
- Symlink escape checks on every lookup
- Binary file detection (null-byte scan)
- File size cap (default 2 MB)
- Sensitive file patterns skipped by default
- No write or shell operations on project files
- SQLite cache isolated at `~/.faststack-mcp/`

---

## Installation options

```powershell
# Local dev
pip install -e "C:\path\to\faststack-mcp"

# GitHub
pip install "git+https://github.com/Evaan-devlops/faststack-mcp.git"

# With extras
pip install -e ".[watch]"       # watchfiles — file watcher
pip install -e ".[postgres]"    # psycopg2-binary — PostgreSQL backend
pip install -e ".[all]"         # both
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FASTSTACK_STORAGE` | `sqlite` | Storage backend: `sqlite`, `postgres`, `json` |
| `DATABASE_URL` | — | PostgreSQL DSN (required when `FASTSTACK_STORAGE=postgres`) |

## Development

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e .
python -m py_compile src/faststack_mcp/server.py  # syntax check
pytest tests/
```

## Env parsing

- `.env.example` indexed by default with masked values (`***MASKED***`)
- `.env` and `.env.*` skipped unless `include_env_files=True`
- Raw values never persisted
