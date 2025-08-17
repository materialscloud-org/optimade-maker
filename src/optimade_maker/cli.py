import json
from pathlib import Path

import click

from optimade_maker.convert import convert_archive
from optimade_maker.logger import LOGGER
from optimade_maker.serve import OptimakeServer


@click.group()
def cli():
    """
    Tools for making OPTIMADE APIs for a raw data archives annotated with an
    `optimade.yaml` file.
    """
    pass


@cli.command()
@click.argument(
    "path",
    type=click.Path(),
)
@click.option(
    "--jsonl_path",
    type=click.Path(),
    help="The path to write the JSONL file to.",
)
@click.option(
    "--limit",
    type=int,
    help="Limit the ingestion to a fixed number of structures (useful for testing).",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Overwrite the JSONL file if it already exists.",
)
def convert(path, jsonl_path, limit=None, overwrite=False):
    """
    Convert a raw data archive into OPTIMADE JSONL.

    PATH needs to contain the full raw data archive, with the `optimade.yaml` config
    file at the top level. The data is converted into the OPTIMADE JSON Lines format.
    """

    if jsonl_path:
        jsonl_path = Path(jsonl_path)
        if jsonl_path.exists():
            raise FileExistsError(f"File already exists at {jsonl_path}.")
    convert_archive(Path(path), jsonl_path=jsonl_path, limit=limit, overwrite=overwrite)


@cli.command()
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    help="The host to bind the API to (e.g., 127.0.0.1 or 0.0.0.0).",
)
@click.option(
    "--port",
    type=int,
    default=5000,
    help="The port to serve the API on.",
)
@click.option(
    "--extra_config_file",
    type=click.Path(),
    help="Custom configuration options in a JSON file.",
)
@click.option(
    "--write_config",
    type=click.Path(),
    help="Write the API config file. If not set, the config is not written.",
)
@click.option(
    "--drop_existing_db",
    is_flag=True,
    default=False,
    help="Drop and re-populate MongoDB if it already exists.",
)
@click.option(
    "--prepare_only",
    is_flag=True,
    default=False,
    help="Only prepare the data and config, don't start the API.",
)
@click.argument(
    "path",
    type=click.Path(),
)
def serve(
    host, port, extra_config_file, write_config, drop_existing_db, prepare_only, path
):
    """
    Serve a raw data archive with an OPTIMADE API.

    PATH needs to contain the full raw data archive, with the `optimade.yaml` config
    file at the top level. If needed, the data is first converted into an OPTIMADE JSONL
    file. However, if the JSONL file already exists, the API is started from it.

    Use `--extra_config_file` or set `OPTIMADE_*` env variables to pass in additional
    configuration options such a custom provider or a real MongoDB backend.

    Use `--prepare_only` and `--write_config` to populate a MongoDB and write an optimade
    config file, which allows to easily start the API externally/independently.
    """

    jsonl_file = "optimade.jsonl"
    path = Path(path)

    if not (path / jsonl_file).exists():
        LOGGER.info(f"{jsonl_file} doesn't exist. Converting archive.")
        convert_archive(path)
    else:
        LOGGER.info(f"{jsonl_file} already exists!")

    LOGGER.info("Preparing to start the API...")
    optimake_server = OptimakeServer(path, host, port, extra_config_file)

    if write_config is not None:
        write_config = Path(write_config)
        if not write_config.is_absolute():
            # if relative path, assume it's w.r.t. the main folder
            write_config = path / write_config
        with open(write_config, "w") as f:
            json.dump(optimake_server.optimade_config, f, indent=2)
        LOGGER.info(f"Final config written to {write_config}")

    optimake_server.populate_mongodb(
        skip_mock=prepare_only, drop_existing_db=drop_existing_db
    )

    if not prepare_only:
        LOGGER.info("Starting the API")
        optimake_server.start_api()


if __name__ == "__main__":
    cli()
