from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import aiida
from aiida import orm
from aiida.common.exceptions import (
    CorruptStorage,
    IncompatibleStorageSchema,
    NotExistent,
    ProfileConfigurationError,
    UnreachableStorage,
)
from aiida.storage.sqlite_zip.backend import SqliteZipBackend
from optimade.adapters import Structure
from optimade.models import EntryResource
from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from .config import EntryConfig


class AiidaEntryPath(BaseModel):
    """Config to specify an AiiDA entry path."""

    aiida_file: Optional[str] = Field(
        None, description="AiiDA file that contains the structures."
    )
    aiida_profile: Optional[str] = Field(
        None, description="AiiDA profile that contains the structures."
    )
    aiida_group: str = Field(description="AiiDA group that contains the structures.")

    @model_validator(mode="before")
    @classmethod
    def check_file_or_profile(cls, values):
        if isinstance(values, list):
            # Skip validation for lists
            return values
        if not values.get("aiida_file") and not values.get("aiida_profile"):
            raise ValueError("Either 'aiida_file' or 'aiida_profile' must be defined.")
        if values.get("aiida_file") and values.get("aiida_profile"):
            raise ValueError(
                "Both 'aiida_file' and 'aiida_profile' cannot be defined at the same time."
            )
        return values


class AiidaQueryItem(BaseModel):
    """An item representing a step in an AiiDA query, which allows
        * to project properties of the current node, or
        * to move to a connected node in the AiiDA provenance graph.
    In the case of querying for connected nodes, the usual AiiDA
    QueryBuilder filters and edge_filters can be applied.
    """

    project: Optional[str] = Field(
        None, description="The AiiDA attribute to project in the query."
    )
    incoming_node: Optional[str] = Field(
        None, description="Query for an incoming node of the specified type."
    )
    outgoing_node: Optional[str] = Field(
        None, description="Query for an outgoing node of the specified type."
    )
    filters: Optional[dict[Any, Any]] = Field(
        None, description="filters passed to AiiDA QueryBuilder."
    )
    edge_filters: Optional[dict[Any, Any]] = Field(
        None, description="edge_filters passed to AiiDA QueryBuilder."
    )

    @model_validator(mode="before")
    @classmethod
    def check_required_fields(cls, values):
        if not any(
            values.get(field) for field in ["project", "incoming_node", "outgoing_node"]
        ):
            raise ValueError(
                "One of 'project', 'incoming_node', or 'outgoing_node' must be defined."
            )
        if values.get("filters") or values.get("edge_filters"):
            if not any(
                values.get(field) for field in ["incoming_node", "outgoing_node"]
            ):
                raise ValueError(
                    "'filters' and 'edge_filters' can only be defined for 'incoming_node' or 'outgoing_node'."
                )
        return values


def query_for_aiida_structures(structure_group: str) -> dict[str, orm.StructureData]:
    """
    Query for all aiida structures in the specified group
    """
    qb = orm.QueryBuilder()
    qb.append(orm.Group, filters={"label": structure_group}, tag="group")
    qb.append(orm.StructureData, with_group="group", project=["uuid", "*"])
    return {uuid: node for uuid, node in qb.all()}


def query_for_aiida_properties(structure_group, aiida_query) -> dict[str, Any]:
    """
    Query for structure properties based on the custom aiida query format
    specified in the yaml file.
    """

    # query for the structures
    qb = orm.QueryBuilder()
    qb.append(orm.Group, filters={"label": structure_group}, tag="group")

    current_node_class = orm.StructureData
    qb_args: dict[str, Any] = {"with_group": "group", "project": ["uuid"], "tag": "0"}

    # ensure that the aiida_query is a list
    aiida_query = aiida_query if isinstance(aiida_query, list) else [aiida_query]

    for i_step, step in enumerate(aiida_query):
        if step.project:
            # project for the current node and execute the query
            qb_args["project"] += [step.project]
            qb.append(current_node_class, **qb_args)
            break
        else:
            # Either incoming or outgoing node must be specified, query for it
            if step.incoming_node and step.outgoing_node:
                raise ValueError(
                    "Cannot have both incoming and outgoing nodes in the same step"
                )

            node_class_str = step.incoming_node or step.outgoing_node
            if not node_class_str:
                raise ValueError("One of incoming and outgoing nodes must be specified")

            # add the previous node to the query
            qb.append(current_node_class, **qb_args)

            # get the new node class
            current_node_class = getattr(aiida.orm, node_class_str, None)
            if not current_node_class:
                raise ValueError(f"Node class {node_class_str} not found in aiida.orm")

            qb_args = {"project": [], "tag": str(i_step + 1)}

            if step.incoming_node:
                qb_args["with_outgoing"] = str(i_step)
            elif step.outgoing_node:
                qb_args["with_incoming"] = str(i_step)

            if step.filters:
                qb_args["filters"] = step.filters
            if step.edge_filters:
                qb_args["edge_filters"] = step.edge_filters

    # import json
    # print(json.dumps(qb.as_dict(), indent=2))
    res = {uuid: val for uuid, val in qb.all()}
    return res


def get_aiida_profile_from_file(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # check if the file is a valid AiiDA archive
    try:
        storage = SqliteZipBackend(SqliteZipBackend.create_profile(path))
    except (UnreachableStorage, CorruptStorage, IncompatibleStorageSchema) as e:
        raise ValueError(f"Error loading AiiDA file: {e}")

    return storage.profile


def convert_aiida_structure_to_optimade(
    aiida_structure: orm.StructureData,
) -> dict:
    pmg_structure = aiida_structure.get_pymatgen()
    optimade_entry = Structure.ingest_from(pmg_structure).entry.dict()
    optimade_entry["id"] = aiida_structure.uuid
    optimade_entry["attributes"]["immutable_id"] = aiida_structure.uuid
    optimade_entry["attributes"]["last_modified"] = aiida_structure.mtime.isoformat()
    return optimade_entry


def _convert_property_type(type, value):
    """Convert properties based on the type specified in the config file.

    What needs conversion either way:
    - timestamp is expected to be a string in ISO format;
    - QueryBuilder seems to return an int for bool

    For the rest, try to convert (excepts if user has specified the wrong type).
    """
    if value is None:
        return None
    if type == "timestamp":
        return value.isoformat()
    if type == "boolean":
        return bool(value)
    if type == "string":
        return str(value)
    if type == "integer":
        return int(value)
    if type == "float":
        return float(value)
    return value


def construct_entries_from_aiida(
    archive_path: Path,
    entry_config: EntryConfig,
    provider_prefix: str,
) -> dict[str, dict]:
    if not isinstance(entry_config.entry_paths, AiidaEntryPath):
        raise RuntimeError("entry_paths is not AiiDA-specific.")
    if entry_config.entry_type != "structures":
        raise RuntimeError(
            "Only 'structures' entry_type is supported for the AiiDA plugin."
        )

    try:
        if aiida_profile := entry_config.entry_paths.aiida_profile:
            aiida.load_profile(aiida_profile, allow_switch=True)
        elif aiida_file := entry_config.entry_paths.aiida_file:
            file_path = archive_path / aiida_file
            aiida.load_profile(
                get_aiida_profile_from_file(file_path), allow_switch=True
            )
    except ProfileConfigurationError as e:
        raise ValueError(f"Error loading AiiDA profile: {e}")

    # check that the AiiDA group exists
    group_label = entry_config.entry_paths.aiida_group
    try:
        orm.load_group(group_label)
    except NotExistent:
        raise ValueError(f"AiiDA group '{group_label}' does not exist.")

    aiida_structures = query_for_aiida_structures(group_label)

    optimade_entries: dict[str, EntryResource] = {}

    for id, node in aiida_structures.items():
        optimade_entries[id] = convert_aiida_structure_to_optimade(node)

    # Add also the (custom) AiiDA properties
    for prop_def in entry_config.property_definitions or []:
        aiida_query = prop_def.aiida_query
        if aiida_query:
            props = query_for_aiida_properties(group_label, aiida_query)
            for uuid, prop in props.items():
                prop_name = f"_{provider_prefix}_{prop_def.name}"
                optimade_entries[uuid]["attributes"][prop_name] = (
                    _convert_property_type(prop_def.type, prop)
                )

    return optimade_entries
