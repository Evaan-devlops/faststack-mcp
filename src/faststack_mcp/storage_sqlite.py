"""SQLite-backed storage with FTS5 full-text search and reference graph.
Enabled via FASTSTACK_STORAGE=sqlite (default when watchfiles is not set).
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from .config import DEFAULT_CACHE_ROOT
from .models import FileRecord, ProjectIndex, ProjectStats, Symbol

_DB_NAME = "faststack.db"
_lock = threading.Lock()


def _db_path() -> Path:
    root = DEFAULT_CACHE_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root / _DB_NAME


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    project_id   TEXT PRIMARY KEY,
    project_path TEXT NOT NULL,
    indexed_at   TEXT NOT NULL,
    fingerprint  TEXT DEFAULT '',
    errors       TEXT DEFAULT '[]',
    stats        TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS files (
    project_id  TEXT NOT NULL,
    path        TEXT NOT NULL,
    language    TEXT NOT NULL,
    size        INTEGER NOT NULL,
    hashed      TEXT NOT NULL,
    symbols     TEXT DEFAULT '[]',
    line_count  INTEGER DEFAULT 0,
    indexed_at  TEXT NOT NULL,
    metadata    TEXT DEFAULT '{}',
    PRIMARY KEY (project_id, path),
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS symbols (
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
    metadata       TEXT DEFAULT '{}',
    PRIMARY KEY (sym_id, project_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
    sym_id      UNINDEXED,
    project_id  UNINDEXED,
    name,
    qualified_name,
    signature
);

CREATE TABLE IF NOT EXISTS refs (
    project_id   TEXT NOT NULL,
    symbol_name  TEXT NOT NULL,
    file_path    TEXT NOT NULL,
    line_number  INTEGER NOT NULL,
    context      TEXT DEFAULT '',
    PRIMARY KEY (project_id, symbol_name, file_path, line_number),
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sym_project  ON symbols(project_id);
CREATE INDEX IF NOT EXISTS idx_sym_name     ON symbols(project_id, name);
CREATE INDEX IF NOT EXISTS idx_ref_name     ON refs(project_id, symbol_name);
CREATE INDEX IF NOT EXISTS idx_file_project ON files(project_id);
"""


def _row_to_symbol(row: sqlite3.Row) -> Symbol:
    return Symbol(
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
        metadata=json.loads(row["metadata"] or "{}"),
    )


def _row_to_file(row: sqlite3.Row) -> FileRecord:
    return FileRecord(
        path=row["path"],
        language=row["language"],
        size=row["size"],
        hashed=row["hashed"],
        symbols=json.loads(row["symbols"] or "[]"),
        line_count=row["line_count"],
        indexed_at=row["indexed_at"],
        metadata=json.loads(row["metadata"] or "{}"),
    )


class SqliteStorage:
    def __init__(self) -> None:
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = _connect()
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        return self._conn

    def cache_root(self) -> Path:
        return DEFAULT_CACHE_ROOT

    def project_exists(self, project_id: str) -> bool:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
        return row is not None

    def load_project(self, project_id: str) -> ProjectIndex:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
        if not row:
            raise RuntimeError(f"Project not found: {project_id}")

        stats_data = json.loads(row["stats"] or "{}")
        errors = json.loads(row["errors"] or "[]")

        files: dict[str, FileRecord] = {}
        for frow in conn.execute("SELECT * FROM files WHERE project_id = ?", (project_id,)):
            fr = _row_to_file(frow)
            files[fr.path] = fr

        symbols: dict[str, Symbol] = {}
        for srow in conn.execute("SELECT * FROM symbols WHERE project_id = ?", (project_id,)):
            sym = _row_to_symbol(srow)
            symbols[sym.id] = sym

        references_graph: dict[str, list[str]] = {}
        for rrow in conn.execute(
            "SELECT symbol_name, file_path, line_number FROM refs WHERE project_id = ?",
            (project_id,),
        ):
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
        with _lock:
            with conn:
                conn.execute(
                    """INSERT OR REPLACE INTO projects
                       (project_id, project_path, indexed_at, fingerprint, errors, stats)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        index.project_id, index.project_path, index.indexed_at,
                        index.fingerprint, json.dumps(index.errors), stats_json,
                    ),
                )
                conn.execute("DELETE FROM files WHERE project_id = ?", (index.project_id,))
                conn.execute("DELETE FROM symbols WHERE project_id = ?", (index.project_id,))
                conn.execute("DELETE FROM symbols_fts WHERE project_id = ?", (index.project_id,))
                conn.execute("DELETE FROM refs WHERE project_id = ?", (index.project_id,))

                conn.executemany(
                    """INSERT OR REPLACE INTO files
                       (project_id, path, language, size, hashed, symbols, line_count, indexed_at, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            index.project_id, fr.path, fr.language, fr.size, fr.hashed,
                            json.dumps(fr.symbols), fr.line_count, fr.indexed_at,
                            json.dumps(fr.metadata),
                        )
                        for fr in index.files.values()
                    ],
                )

                conn.executemany(
                    """INSERT OR REPLACE INTO symbols
                       (sym_id, project_id, name, qualified_name, kind, language,
                        file_path, line_start, line_end, byte_start, byte_end, signature, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            s.id, index.project_id, s.name, s.qualified_name, s.kind, s.language,
                            s.file_path, s.line_start, s.line_end, s.byte_start, s.byte_end,
                            s.signature, json.dumps(s.metadata),
                        )
                        for s in index.symbols.values()
                    ],
                )

                # Populate FTS5 index
                conn.executemany(
                    """INSERT INTO symbols_fts(sym_id, project_id, name, qualified_name, signature)
                       VALUES (?, ?, ?, ?, ?)""",
                    [
                        (s.id, index.project_id, s.name, s.qualified_name, s.signature or "")
                        for s in index.symbols.values()
                    ],
                )

                # Persist reference graph
                ref_rows = []
                for name, entries in index.references_graph.items():
                    for entry in entries:
                        parts = entry.rsplit(":", 1)
                        fp = parts[0]
                        ln = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                        ref_rows.append((index.project_id, name, fp, ln))
                if ref_rows:
                    conn.executemany(
                        """INSERT OR REPLACE INTO refs (project_id, symbol_name, file_path, line_number)
                           VALUES (?, ?, ?, ?)""",
                        ref_rows,
                    )

    def list_projects(self) -> list[ProjectIndex]:
        conn = self._get_conn()
        result = []
        for row in conn.execute("SELECT * FROM projects ORDER BY indexed_at DESC"):
            stats_data = json.loads(row["stats"] or "{}")
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
        cursor = conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        conn.commit()
        return cursor.rowcount > 0

    def search_symbols_fts(
        self,
        project_id: str,
        query: str,
        kind: str | None = None,
        language: str | None = None,
        limit: int = 10,
    ) -> list[Symbol]:
        """Combined FTS5 + LIKE search for symbol names."""
        conn = self._get_conn()
        q = query.strip().lower()
        if not q:
            return []

        safe = q.replace('"', "").replace("'", "")
        fts_query = f'"{safe}"*'

        # FTS5 search
        try:
            fts_ids = {
                row[0]
                for row in conn.execute(
                    "SELECT sym_id FROM symbols_fts WHERE symbols_fts MATCH ? AND project_id = ? LIMIT ?",
                    (fts_query, project_id, limit * 4),
                )
            }
        except sqlite3.OperationalError:
            fts_ids = set()

        # LIKE fallback for underscore-heavy names like get_db, create_user
        like_ids = {
            row[0]
            for row in conn.execute(
                "SELECT sym_id FROM symbols WHERE project_id = ? AND LOWER(name) LIKE ? LIMIT ?",
                (project_id, f"%{q}%", limit),
            )
        }

        all_ids = fts_ids | like_ids
        if not all_ids:
            return []

        placeholders = ",".join("?" * len(all_ids))
        rows = conn.execute(
            f"SELECT * FROM symbols WHERE sym_id IN ({placeholders}) AND project_id = ?",
            [*all_ids, project_id],
        ).fetchall()

        symbols: list[Symbol] = []
        for row in rows:
            sym = _row_to_symbol(row)
            if kind and sym.kind != kind:
                continue
            if language and sym.language != language:
                continue
            symbols.append(sym)

        def _rank(s: Symbol) -> int:
            nl = s.name.lower()
            if nl == q:
                return 300
            if nl.startswith(q):
                return 200
            if q in nl:
                return 100
            return 20

        symbols.sort(key=_rank, reverse=True)
        return symbols[:limit]

    def get_references(self, project_id: str, symbol_name: str) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT file_path, line_number, context FROM refs
               WHERE project_id = ? AND symbol_name = ?
               ORDER BY file_path, line_number""",
            (project_id, symbol_name.lower()),
        ).fetchall()
        return [
            {"file_path": r["file_path"], "line": r["line_number"], "context": r["context"] or ""}
            for r in rows
        ]
