"""
This module provides the OptimakeServer class to handle the configuration and
startup of an OPTIMADE API server using optimade-python-tools.

The OptimakeServer also allows to prepare the API by
* populating the MongoDB database; and
* generating the optimade-python-tools configuration file,
which allows to easily start the API externally (e.g. by another service).

What requires special attention is the provider prefix, which is used
to distinguish custom properties in the OPTIMADE entries. If the specified
prefix is different from the one in the JSONL file, it needs to be replaced
in the 1) configuration file, and 2) in the data entries themselves.

Note also that when optimade python tools is first imported, it 1) loads the
config; and 2) creates the MongoMock database (if used). This means that it
should be imported after config is determined, and before populating the db.
"""

import json
import os
import traceback
import warnings
from pathlib import Path

import bson.json_util
import uvicorn

from optimade_maker.logger import LOGGER
from optimade_maker.mongo_utils import populate_mongodb_from_jsonl

PROVIDER_PREFIX = os.environ.get("OPTIMAKE_PROVIDER_PREFIX", "optimake")


def get_default_provider_info():
    provider = {
        "prefix": PROVIDER_PREFIX,
        "name": "Optimake",
        "description": "Provider created with optimade-maker",
        "homepage": "https://github.com/materialscloud-org/optimade-maker",
    }
    return provider


def set_config_env_variables(config_dict):
    """Set optimade environment variables used by the API, according to a config dictionary.

    Notes:
    When starting the fastapi of optimade-python-tools, the ServerConfig seems to be read
    either from
    * environment variables starting with 'OPTIMADE_'; or
    * config file specified either by OPTIMADE_CONFIG_FILE or DEFAULT_CONFIG_FILE_PATH;
    there doesn't seem to be a way to just pass in the config directly.

    Therefore, just specify the config through environment variables.

    Note also that these variables only persist for this python process or any subprocess.
    """
    for key, value in config_dict.items():
        env_var = f"OPTIMADE_{key}"
        if isinstance(value, (dict, list, bool)):
            os.environ[env_var] = json.dumps(value)
        elif value is None:
            os.environ[env_var] = "null"
        else:
            os.environ[env_var] = str(value)


def replace_provider_prefix(name: str, provider_prefix: str) -> str:
    """Replace the provider prefix in the property name with the new one."""
    parts = name.split("_")
    suffix = "_".join(parts[2:]) if len(parts) > 2 else ""
    return f"_{provider_prefix}" + (f"_{suffix}" if suffix else "")


def get_provider_fields_from_jsonl(
    jsonl_path: Path, replace_prefix: str | None = None
) -> dict:
    """
    Go through the "info" collection of the jsonl and get the
    provider fields (custom properties)
    """

    info_types = ["structures", "references"]

    provider_fields = {}

    def _read_custom_fields(properties, info_type):
        if info_type not in info_types:
            return None

        fields = []
        for prop, val in properties.items():
            # if property name starts with underscore, it's a custom one
            if prop.startswith("_"):
                provider_field_entry = {
                    "name": replace_provider_prefix(prop, replace_prefix)
                    if replace_prefix
                    else prop,
                }
                # add only the keys that are not None.
                for key in ["description", "unit", "type"]:
                    if val.get(key) is not None:
                        provider_field_entry[key] = val.get(key)
                fields.append(provider_field_entry)
        if fields:
            provider_fields[info_type] = fields

    with open(jsonl_path, "r") as fhandle:
        try:
            for line_no, json_str in enumerate(fhandle):
                try:
                    entry = bson.json_util.loads(json_str)
                except json.JSONDecodeError:
                    warnings.warn(f"Found bad JSONL line at L{line_no}")
                    continue

                if "properties" in entry:
                    if "type" not in entry:
                        # possible pre-1.2 info endpoint
                        if "description" in entry:
                            _read_custom_fields(
                                entry["properties"], entry["description"]
                            )
                    else:
                        # 1.2+ info endpoints include type & id
                        if entry["type"] == "info":
                            _read_custom_fields(entry["properties"], entry["id"])

                elif "x-optimade" in entry:
                    continue
                # If this isn't an info endpoint, or the first line header, then we break
                # as presumably we have reached the data itself
                else:
                    break

        except Exception as exc:
            traceback.print_exc()
            print(f"Error {exc}")
    return provider_fields


class OptimakeServer:
    """
    Class to handle input parameters and configuration to start the optimade-python-tools API.
    Uses the MongoMock backend.
    """

    def __init__(
        self,
        path: Path,
        host: str = "127.0.0.1",
        port: int = 5000,
        extra_config_file: Path | None = None,
    ):
        """Initialise the OptimakeServer instance.

        Parameters:
            path: Path to the directory containing the optimade.jsonl file.
            port: Port to run the API on.
            extra_config_file: Additional optimade-python-tools configuration options to pass to the API.
            write_final_config: Output the final config file.

        """
        self.path = path
        self.jsonl_path = self.path / "optimade.jsonl"
        self.host = host
        self.port = port

        if not self.path.exists():
            raise FileNotFoundError(f"Path {self.path} does not exist.")

        self.extra_config_file = extra_config_file
        if self.extra_config_file is not None:
            self.extra_config_file = Path(self.extra_config_file)
            if not self.extra_config_file.is_absolute():
                # if relative path, assume it's w.r.t. the main folder
                self.extra_config_file = self.path / self.extra_config_file
            if not self.extra_config_file.exists():
                raise FileNotFoundError(
                    f"Path {self.extra_config_file} does not exist."
                )

        self.provider_prefix = None
        self.optimade_config = self.get_optimade_config()
        set_config_env_variables(self.optimade_config)

    def get_optimade_config(self):
        # Default configuration options
        config_dict = {
            "debug": False,
            "insert_test_data": False,
            "base_url": f"http://{self.host}:{self.port}",
            "provider": get_default_provider_info(),
            # "log_dir": ".",  # str(self.path.resolve()),
        }

        # Update/override config options if any `OPTIMAKE_` env variables are set
        for env in os.environ:
            if env.startswith("OPTIMAKE_"):
                LOGGER.debug(
                    "Reading environment variable %s into config with value %s",
                    env,
                    os.environ[env],
                )
                config_dict[env.replace("OPTIMAKE_", "").lower()] = os.environ[env]

        # Update/override config options if the extra_config_file is provided
        if self.extra_config_file:
            with open(self.extra_config_file, "r") as f:
                extra_config = json.load(f)
            config_dict.update(extra_config)

        self.provider_prefix = config_dict.get("provider", {}).get("prefix")

        # replace the provider prefix in the provider fields
        provider_fields = get_provider_fields_from_jsonl(
            self.jsonl_path, replace_prefix=self.provider_prefix
        )

        config_dict["provider_fields"] = provider_fields

        LOGGER.debug(f"CONFIG: {json.dumps(config_dict, indent=2)}")

        return config_dict

    def populate_mongodb(self, skip_mock: bool = False, drop_existing_db: bool = False):
        """
        Determine the backend: external or mock MongoDB,
        and populate it from JSONL.
        """
        db_backend = self.optimade_config.get("database_backend", "mongomock")
        db_name = self.optimade_config.get("mongo_database", "optimade")
        if db_backend == "mongodb":
            # External MongoDB backend
            LOGGER.info("`Using an external MongoDB backend.")
            try:
                import pymongo
            except ImportError:
                raise ImportError(
                    "External MongoDB requires the `mongo` extra dependency to be installed."
                )
            mongo_uri = self.optimade_config["mongo_uri"]
            client = pymongo.MongoClient(mongo_uri)

            if db_name in client.list_database_names():
                # DB already exists
                if drop_existing_db:
                    LOGGER.info(f"Dropping existing database '{db_name}'...")
                    client.drop_database(db_name)
                else:
                    LOGGER.info(
                        f"Database '{db_name}' already exists, skipping data injection."
                    )
                    return

            mongo_db = client[db_name]
        elif db_backend == "mongomock":
            # The default MongoMock backend
            LOGGER.info("Using the MongoMock backend.")
            if skip_mock:
                return
            # Importing optimade python tools loads the config and creates the mongomock
            # client that we need to populate.
            from optimade.server.entry_collections.mongo import CLIENT

            mongo_db = CLIENT[db_name]
        else:
            raise ValueError(
                f"Unknown database backend '{db_backend}'. "
                "Supported backends are 'mongodb' and 'mongomock'."
            )

        LOGGER.info("Populating the database...")
        populate_mongodb_from_jsonl(
            self.jsonl_path, mongo_db, replace_prefix=self.provider_prefix
        )

    def start_api(self):
        # Importing optimade loads config (if not imported already before)
        from optimade.server.main import app

        uvicorn.run(app, host=self.host, port=self.port)
