from pathlib import Path

from faststack_mcp.parsers.python_fastapi import parse_file


def test_python_fastapi_route_and_model_symbols():
    sample = (
        "from fastapi import APIRouter, Depends\n"
        "from pydantic import BaseModel\n\n"
        "router = APIRouter()\n\n"
        "class User(BaseModel):\n"
        "    id: int\n\n"
        "@router.get('/users/{user_id}')\n"
        "def get_user(user_id: int):\n"
        "    return User(id=user_id)\n"
    )
    symbols = parse_file(Path("main.py"), sample)
    kinds = {s.kind for s in symbols}
    assert "pydantic_model" in kinds
    assert "route" in kinds
    assert any(s.qualified_name == "User" for s in symbols)
