"""This submodule describes the `optimade.yaml` config file
that can be provided in an MCloud entry and used to indicate
how an OPIMADE API should be constructed from the entry.

"""

__version__ = "0.1.0"

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, root_validator, validator


class UnsupportedConfigVersion(RuntimeError):
    ...


class PropertyDefinition(BaseModel):
    """A short-hand definition of a property to be served by this API.
    This is a subset of the full OPTIMADE v1.2 property definition.

    """

    name: str = Field(
        description="""The field name of the property, as provided in the included
the auxiliary property files.
Will be served with a provider-specific prefix in the actual API, so must not start with an underscore."""
    )

    title: Optional[str] = Field(description="A human-readable title for the property.")
    description: Optional[str] = Field(
        description="A human-readable description of the property."
    )
    unit: Optional[str] = Field(
        description="The unit of the property, e.g. 'eV' or 'Å'."
    )
    type: Optional[str] = Field(
        description="The OPTIMADE type of the property, e.g., `float` or `string`."
    )
    mapsto: Optional[str] = Field(
        description="A URI/URN for a canonical definition of the property, within the OPTIMADE extended format. Where possible, this should be a versioned URI."
    )


class ParsedFiles(BaseModel):
    file: str = Field(description="The filename containing the data to be parsed.")

    matches: Optional[list[str]] = Field(
        description="A list of matches to be used to filter the file contents. Each match can use simple '*' wildcard syntax.",
        examples=[["structures/*.cif", "relaxed-structures/1.cif"]],
    )


class EntryConfig(BaseModel):
    entry_type: str = Field(
        description="The OPTIMADE entry type, e.g. `structures` or `references`."
    )
    entry_paths: list[ParsedFiles] = Field(
        description="A list of paths patterns to parse, provided relative to the top-level of the MCloud archive entry, after any compressed locations have been decompressed. Supports Python glob syntax for wildcards."
    )

    property_paths: Optional[list[ParsedFiles]] = Field(
        description="A list of path patterns of auxiliary files that contain mappings from the entries to additional properties."
    )

    property_definitions: Optional[list[PropertyDefinition]] = Field(
        description="A place to list property metadata for fields included in the auxiliary property files. Fields not present in this list not be served by the API."
    )

    @validator("entry_type")
    def check_optimade_entry_type(cls, v):
        if v not in ("structures", "references") and not v.startswith("_"):
            raise ValueError(
                f"OPTIMADE entry type must be either 'structures', 'references', or contain a custom prefix, not {v}"
            )

        return v


class Config(BaseModel):
    """This class describes the `optimade.yaml` file
    that a user can provide for each MCloud entry.

    """

    config_version: str = Field(
        "0.1.0",
        description="The version of the `optimade.yaml` config specification.",
    )

    database_description: str = Field(
        description="A human-readable description of the overall database to be provided alongside the data in the API."
    )

    entries: list[EntryConfig] = Field(
        description="A list of entry configurations for each entry type."
    )

    data_paths: Optional[list[str]] = Field(
        description="A list of locations of compressed/archived files that must be decompressed before parsing."
    )

    @validator("entries")
    def check_one_entry_per_type(cls, v):
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

    @root_validator(pre=True)
    def validate_config_version(cls, values):
        if values.get("config_version") is None:
            raise UnsupportedConfigVersion(f"Config version must be {__version__}.")
        return values
