from pathlib import Path

from faststack_mcp.parsers.sql_parser import parse_file


def test_sql_parser_detects_table_and_view():
    sample = """
    CREATE TABLE users(
      id INTEGER PRIMARY KEY
    );
    ALTER TABLE users ADD COLUMN email TEXT;
    CREATE VIEW active_users AS SELECT * FROM users WHERE active = TRUE;
    """
    symbols = parse_file(Path("migrations/20260101.sql"), sample)
    kinds = {s.kind for s in symbols}
    assert "table" in kinds
    assert "alter_table" in kinds
    assert "view" in kinds
