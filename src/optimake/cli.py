from pathlib import Path

import click

from optimake.convert import convert_archive
from optimake.serve.serve_w_docker_compose import serve_archive


@click.group()
def cli():
    """Main CLI entry point."""
    pass


@cli.command()
@click.option("--jsonl_path", default=None, help="The path to write the JSONL file to.")
@click.argument("archive_path")
def convert(
    jsonl_path,
    archive_path,
):
    """
    Use an `optimade.yaml` config to describe archived data and create a OPTIMADE JSONL file for ingestion as an OPTIMADE API.
    """

    if jsonl_path:
        jsonl_path = Path(jsonl_path)
        if jsonl_path.exists():
            raise FileExistsError(f"File already exists at {jsonl_path}.")

    convert_archive(Path(archive_path), jsonl_path=jsonl_path)


@cli.command()
@click.argument("path")
def serve(
    path,
):
    """
    TEST
    """

    serve_archive(path)


if __name__ == "__main__":
    cli()
