"""PostgreSQL-backed storage with tsvector full-text search and reference graph.
Set DATABASE_URL to enable: postgresql://user:pass@host:5433/dbname
Tables are prefixed with faststack_ to avoid conflicts.
Optional: CREATE EXTENSION IF NOT EXISTS vector; for future pgvector semantic search.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .config import DEFAULT_CACHE_ROOT
from .models import FileRecord, ProjectIndex, ProjectStats, Symbol


def _dsn() -> str:
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL environment variable is required for PostgreSQL storage. "
            "Example: postgresql://user:pass@localhost:5433/mydb"
        )
    return dsn


# DDL — generated tsvector column on symbols for zero-maintenance FTS
_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS faststack_projects (
    project_id   TEXT PRIMARY KEY,
    project_path TEXT NOT NULL,
    indexed_at   TEXT NOT NULL,
    fingerprint  TEXT DEFAULT '',
    errors       JSONB DEFAULT '[]'::jsonb,
    stats        JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS faststack_files (
    project_id  TEXT NOT NULL,
    path        TEXT NOT NULL,
    language    TEXT NOT NULL,
    size        INTEGER NOT NULL,
    hashed      TEXT NOT NULL,
    symbols     JSONB  DEFAULT '[]'::jsonb,
    line_count  INTEGER DEFAULT 0,
    indexed_at  TEXT NOT NULL,
    metadata    JSONB  DEFAULT '{}'::jsonb,
    PRIMARY KEY (project_id, path),
    FOREIGN KEY (project_id) REFERENCES faststack_projects(project_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS faststack_symbols (
    sym_id         TEXT NOT NULL,
    project_id     TEXT NOT NULL,
    name           TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    kind           TEXT NOT NULL,
    language       TEXT NOT NULL,
    file_path      TEXT NOT NULL,
    line_start     INTEGER NOT NULL,
    line_end       INTEGER NOT NULL,
    byte_start     INTEGER NOT NULL,
    byte_end       INTEGER NOT NULL,
    signature      TEXT,
    metadata       JSONB DEFAULT '{}'::jsonb,
    search_vector  TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('simple',
            coalesce(name, '') || ' ' ||
            coalesce(qualified_name, '') || ' ' ||
            coalesce(signature, ''))
    ) STORED,
    PRIMARY KEY (sym_id, project_id),
    FOREIGN KEY (project_id) REFERENCES faststack_projects(project_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS faststack_references (
    project_id   TEXT NOT NULL,
    symbol_name  TEXT NOT NULL,
    file_path    TEXT NOT NULL,
    line_number  INTEGER NOT NULL,
    context      TEXT DEFAULT '',
    PRIMARY KEY (project_id, symbol_name, file_path, line_number),
    FOREIGN KEY (project_id) REFERENCES faststack_projects(project_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fstk_sym_proj   ON faststack_symbols(project_id);
CREATE INDEX IF NOT EXISTS idx_fstk_sym_name   ON faststack_symbols(project_id, name);
CREATE INDEX IF NOT EXISTS idx_fstk_sym_fts    ON faststack_symbols USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_fstk_ref_name   ON faststack_references(project_id, symbol_name);
CREATE INDEX IF NOT EXISTS idx_fstk_file_proj  ON faststack_files(project_id);
"""


class PostgresStorage:
    """PostgreSQL storage backend.
    Requires: pip install psycopg2-binary
    """

    def __init__(self) -> None:
        try:
            import psycopg2
            import psycopg2.extras
            self._pg = psycopg2
            self._extras = psycopg2.extras
        except ImportError as exc:
            raise RuntimeError(
                "psycopg2 is required for PostgreSQL storage: pip install psycopg2-binary"
            ) from exc
        self._conn = None
        self._ensure_schema()

    def _get_conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = self._pg.connect(_dsn())
        return self._conn

    def _ensure_schema(self) -> None:
        conn = self._get_conn()
        # Execute each statement separately to handle IF NOT EXISTS properly
        with conn.cursor() as cur:
            for stmt in _PG_SCHEMA.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    try:
                        cur.execute(stmt)
                    except Exception:
                        conn.rollback()
                        raise
        conn.commit()

    def cache_root(self) -> Path:
        return DEFAULT_CACHE_ROOT

    def project_exists(self, project_id: str) -> bool:
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM faststack_projects WHERE project_id = %s", (project_id,))
            return cur.fetchone() is not None

    def load_project(self, project_id: str) -> ProjectIndex:
        conn = self._get_conn()
        with conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM faststack_projects WHERE project_id = %s", (project_id,))
            row = cur.fetchone()
        if not row:
            raise RuntimeError(f"Project not found: {project_id}")

        stats_data = dict(row["stats"] or {})
        errors = list(row["errors"] or [])

        files: dict[str, FileRecord] = {}
        with conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM faststack_files WHERE project_id = %s", (project_id,))
            for frow in cur.fetchall():
                fr = FileRecord(
                    path=frow["path"],
                    language=frow["language"],
                    size=frow["size"],
                    hashed=frow["hashed"],
                    symbols=list(frow["symbols"] or []),
                    line_count=frow["line_count"],
                    indexed_at=frow["indexed_at"],
                    metadata=dict(frow["metadata"] or {}),
                )
                files[fr.path] = fr

        symbols: dict[str, Symbol] = {}
        with conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT sym_id, project_id, name, qualified_name, kind, language, "
                "file_path, line_start, line_end, byte_start, byte_end, signature, metadata "
                "FROM faststack_symbols WHERE project_id = %s",
                (project_id,),
            )
            for srow in cur.fetchall():
                sym = Symbol(
                    id=srow["sym_id"],
                    name=srow["name"],
                    qualified_name=srow["qualified_name"],
                    kind=srow["kind"],
                    language=srow["language"],
                    file_path=srow["file_path"],
                    line_start=srow["line_start"],
                    line_end=srow["line_end"],
                    byte_start=srow["byte_start"],
                    byte_end=srow["byte_end"],
                    signature=srow["signature"],
                    metadata=dict(srow["metadata"] or {}),
                )
                symbols[sym.id] = sym

        references_graph: dict[str, list[str]] = {}
        with conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT symbol_name, file_path, line_number FROM faststack_references "
                "WHERE project_id = %s",
                (project_id,),
            )
            for rrow in cur.fetchall():
                references_graph.setdefault(rrow["symbol_name"], []).append(
                    f"{rrow['file_path']}:{rrow['line_number']}"
                )

        return ProjectIndex(
            project_id=project_id,
            project_path=row["project_path"],
            indexed_at=row["indexed_at"],
            fingerprint=row["fingerprint"] or "",
            files=files,
            symbols=symbols,
            errors=errors,
            stats=ProjectStats(**stats_data),
            references_graph=references_graph,
        )

    def save_project(self, index: ProjectIndex) -> None:
        conn = self._get_conn()
        stats_json = json.dumps({
            "files_indexed": index.stats.files_indexed,
            "symbols_indexed": index.stats.symbols_indexed,
            "languages": index.stats.languages,
            "frameworks": index.stats.frameworks,
        })
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO faststack_projects
                   (project_id, project_path, indexed_at, fingerprint, errors, stats)
                   VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb)
                   ON CONFLICT (project_id) DO UPDATE SET
                       project_path = EXCLUDED.project_path,
                       indexed_at   = EXCLUDED.indexed_at,
                       fingerprint  = EXCLUDED.fingerprint,
                       errors       = EXCLUDED.errors,
                       stats        = EXCLUDED.stats""",
                (
                    index.project_id, index.project_path, index.indexed_at,
                    index.fingerprint, json.dumps(index.errors), stats_json,
                ),
            )
            cur.execute("DELETE FROM faststack_files WHERE project_id = %s", (index.project_id,))
            cur.execute("DELETE FROM faststack_symbols WHERE project_id = %s", (index.project_id,))
            cur.execute("DELETE FROM faststack_references WHERE project_id = %s", (index.project_id,))

            if index.files:
                self._extras.execute_values(
                    cur,
                    """INSERT INTO faststack_files
                       (project_id, path, language, size, hashed, symbols,
                        line_count, indexed_at, metadata)
                       VALUES %s""",
                    [
                        (
                            index.project_id, fr.path, fr.language, fr.size, fr.hashed,
                            json.dumps(fr.symbols), fr.line_count, fr.indexed_at,
                            json.dumps(fr.metadata),
                        )
                        for fr in index.files.values()
                    ],
                    template="(%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb)",
                    page_size=500,
                )

            if index.symbols:
                self._extras.execute_values(
                    cur,
                    """INSERT INTO faststack_symbols
                       (sym_id, project_id, name, qualified_name, kind, language,
                        file_path, line_start, line_end, byte_start, byte_end,
                        signature, metadata)
                       VALUES %s""",
                    [
                        (
                            s.id, index.project_id, s.name, s.qualified_name, s.kind,
                            s.language, s.file_path, s.line_start, s.line_end,
                            s.byte_start, s.byte_end, s.signature, json.dumps(s.metadata),
                        )
                        for s in index.symbols.values()
                    ],
                    template="(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    page_size=500,
                )

            if index.references_graph:
                ref_rows: list[tuple[Any, ...]] = []
                for name, entries in index.references_graph.items():
                    for entry in entries:
                        parts = entry.rsplit(":", 1)
                        fp = parts[0]
                        ln = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                        ref_rows.append((index.project_id, name, fp, ln))
                if ref_rows:
                    self._extras.execute_values(
                        cur,
                        """INSERT INTO faststack_references
                           (project_id, symbol_name, file_path, line_number)
                           VALUES %s ON CONFLICT DO NOTHING""",
                        ref_rows,
                        page_size=1000,
                    )
        conn.commit()

    def list_projects(self) -> list[ProjectIndex]:
        conn = self._get_conn()
        with conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM faststack_projects ORDER BY indexed_at DESC")
            rows = cur.fetchall()
        result = []
        for row in rows:
            stats_data = dict(row["stats"] or {})
            result.append(ProjectIndex.model_construct(
                project_id=row["project_id"],
                project_path=row["project_path"],
                indexed_at=row["indexed_at"],
                fingerprint=row["fingerprint"] or "",
                files={},
                symbols={},
                errors=[],
                references_graph={},
                stats=ProjectStats(**stats_data),
            ))
        return result

    def remove_project(self, project_id: str) -> bool:
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM faststack_projects WHERE project_id = %s", (project_id,))
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted

    def search_symbols_fts(
        self,
        project_id: str,
        query: str,
        kind: str | None = None,
        language: str | None = None,
        limit: int = 10,
    ) -> list[Symbol]:
        """PostgreSQL tsvector + ILIKE search for robust symbol lookup."""
        conn = self._get_conn()
        q = query.strip()
        if not q:
            return []
        # Build tsquery: each token gets prefix matching via :*
        ts_query = " | ".join(f"{t}:*" for t in q.split() if t)

        where = ["s.project_id = %s", "s.search_vector @@ to_tsquery('simple', %s)"]
        params: list[Any] = [project_id, ts_query]
        if kind:
            where.append("s.kind = %s")
            params.append(kind)
        if language:
            where.append("s.language = %s")
            params.append(language)
        params_full = params + [ts_query, limit * 2]

        with conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
            cur.execute(
                f"""SELECT sym_id, name, qualified_name, kind, language, file_path,
                           line_start, line_end, byte_start, byte_end, signature, metadata
                    FROM faststack_symbols s
                    WHERE {' AND '.join(where)}
                    ORDER BY ts_rank(s.search_vector, to_tsquery('simple', %s)) DESC
                    LIMIT %s""",
                params_full,
            )
            fts_rows = cur.fetchall()

            # ILIKE supplement for underscore names
            ilike_where = ["project_id = %s", "name ILIKE %s"]
            ilike_params: list[Any] = [project_id, f"%{q}%"]
            if kind:
                ilike_where.append("kind = %s")
                ilike_params.append(kind)
            if language:
                ilike_where.append("language = %s")
                ilike_params.append(language)
            ilike_params.append(limit)
            cur.execute(
                f"""SELECT sym_id, name, qualified_name, kind, language, file_path,
                           line_start, line_end, byte_start, byte_end, signature, metadata
                    FROM faststack_symbols
                    WHERE {' AND '.join(ilike_where)}
                    LIMIT %s""",
                ilike_params,
            )
            ilike_rows = cur.fetchall()

        seen: set[str] = set()
        symbols: list[Symbol] = []
        for rows in (fts_rows, ilike_rows):
            for row in rows:
                if row["sym_id"] in seen:
                    continue
                seen.add(row["sym_id"])
                symbols.append(Symbol(
                    id=row["sym_id"],
                    name=row["name"],
                    qualified_name=row["qualified_name"],
                    kind=row["kind"],
                    language=row["language"],
                    file_path=row["file_path"],
                    line_start=row["line_start"],
                    line_end=row["line_end"],
                    byte_start=row["byte_start"],
                    byte_end=row["byte_end"],
                    signature=row["signature"],
                    metadata=dict(row["metadata"] or {}),
                ))

        ql = q.lower()

        def _rank(s: Symbol) -> int:
            nl = s.name.lower()
            if nl == ql:
                return 300
            if nl.startswith(ql):
                return 200
            if ql in nl:
                return 100
            return 20

        symbols.sort(key=_rank, reverse=True)
        return symbols[:limit]

    def get_references(self, project_id: str, symbol_name: str) -> list[dict]:
        """Fetch reference graph entries from PostgreSQL."""
        conn = self._get_conn()
        with conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT file_path, line_number, context FROM faststack_references
                   WHERE project_id = %s AND symbol_name = %s
                   ORDER BY file_path, line_number""",
                (project_id, symbol_name.lower()),
            )
            rows = cur.fetchall()
        return [
            {"file_path": r["file_path"], "line": r["line_number"], "context": r["context"] or ""}
            for r in rows
        ]
