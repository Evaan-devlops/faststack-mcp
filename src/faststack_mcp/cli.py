from __future__ import annotations

import click

from . import __version__
from .server import run_server


@click.command(help="Run the faststack MCP server over stdio.")
@click.version_option(__version__)
def main() -> None:
    run_server()


if __name__ == "__main__":
    main()
