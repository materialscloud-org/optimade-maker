"""This submodule describes the `optimade.yaml` config file that is used
to indicate how an OPTIMADE API should be constructed from the entry.

"""

from optimade.models.optimade_json import DataType
from pydantic import ConfigDict, field_validator, model_validator

IDENTIFIER_REGEX = r"^[a-z_][a-z_0-9]*$"
__version__ = "0.1.0"

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class UnsupportedConfigVersion(RuntimeError): ...


class PropertyDefinition(BaseModel):
    """A short-hand definition of a property to be served by this API.
    This is a subset of the full OPTIMADE v1.2 property definition.

    """

    name: str = Field(
        description="""The field name of the property to use in the API. Will be searched for in the included
the auxiliary property files, unless `aliases` is also specified.
Will be served with a provider-specific prefix in the actual API, so must not start with an underscore or contain upper case characters.""",
        pattern=IDENTIFIER_REGEX,
    )

    title: Optional[str] = Field(
        None, description="A human-readable title for the property."
    )
    description: Optional[str] = Field(
        None, description="A human-readable description of the property."
    )
    unit: Optional[str] = Field(
        None, description="The unit of the property, e.g. 'eV' or 'Å'."
    )
    type: Optional[DataType] = Field(
        description="The OPTIMADE type of the property, e.g., `float` or `string`.",
    )
    maps_to: Optional[str] = Field(
        None,
        description="A URI/URN for a canonical definition of the property, within the OPTIMADE extended format. Where possible, this should be a versioned URI.",
    )
    aliases: Optional[list[str]] = Field(
        None,
        description="A list of aliases to also search for for this property; `name` will be used for the field in the actual OPTIMADE API.",
    )
    model_config = ConfigDict(extra="forbid")


class ParsedFiles(BaseModel):
    file: str = Field(
        description="The path to an archive or file to be unzipped/decompressed."
    )

    matches: Optional[list[str]] = Field(
        None,
        description="A list of matches to be used to filter the file contents. Each match can use simple '*' wildcard syntax.",
        examples=[["structures/*.cif", "relaxed-structures/1.cif"]],
    )
    model_config = ConfigDict(extra="forbid")


class EntryConfig(BaseModel):
    entry_type: str = Field(
        description="The OPTIMADE entry type, e.g. `structures` or `references`."
    )
    entry_paths: list[ParsedFiles] = Field(
        description="A list of paths patterns to parse, provided relative to the top-level of the archive entry, after any compressed locations have been decompressed. Supports Python glob syntax for wildcards."
    )

    property_paths: list[ParsedFiles] = Field(
        default_factory=list,
        description="A list of path patterns of auxiliary files that contain mappings from the entries to additional properties.",
    )

    property_definitions: list[PropertyDefinition] = Field(
        default_factory=list,
        description="A place to list property metadata for fields included in the auxiliary property files. Fields not present in this list not be served by the API.",
    )

    @field_validator("entry_type")
    @classmethod
    def check_optimade_entry_type(cls, v):
        if not isinstance(v, JSONLConfig):
            if v not in ("structures", "references") and not v.startswith("_"):
                raise ValueError(
                    f"OPTIMADE entry type must be either 'structures', 'references', or contain a custom prefix, not {v}"
                )

        return v

    model_config = ConfigDict(extra="forbid")


class JSONLConfig(BaseModel):
    """A description of a single JSON lines file that describes
    the target API.

    """

    file: Optional[str] = Field(
        None, description="The archive filename containing the JSONL data to be parsed."
    )

    jsonl_path: str = Field(
        description="The path of the JSON-L file within the archive (or directly in the entry, if `archive_file` is `None`)."
    )
    model_config = ConfigDict(extra="forbid")


class Config(BaseModel):
    """This class describes the `optimade.yaml` file
    that describes the raw data format.
    """

    config_version: str = Field(
        "0.1.0",
        description="The version of the `optimade.yaml` config specification.",
    )

    database_description: str = Field(
        description="A human-readable description of the overall database to be provided alongside the data in the API."
    )

    entries: list[EntryConfig] | JSONLConfig = Field(
        description="A list of entry configurations for each entry type or a JSONL file."
    )

    @field_validator("entries")
    @classmethod
    def check_one_entry_per_type(cls, v):
        if not isinstance(v, JSONLConfig):
            if len({e.entry_type for e in v}) != len(v):
                raise ValueError(
                    "Each entry type must be listed only once in the config file."
                )
        return v

    @staticmethod
    def from_file(path: str | Path):
        """Load a `optimade.yaml` file from a path, and return a `Config` instance."""
        return Config(**yaml.safe_load(open(path)))

    @staticmethod
    def from_string(data: str):
        return Config(**yaml.safe_load(data))

    @model_validator(mode="before")
    @classmethod
    def validate_config_version(cls, values):
        if values.get("config_version") is None:
            raise UnsupportedConfigVersion(f"Config version must be {__version__}.")
        return values

    model_config = ConfigDict(extra="forbid")
