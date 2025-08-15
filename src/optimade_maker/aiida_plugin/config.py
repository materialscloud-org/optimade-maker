from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class AiidaEntryPath(BaseModel):
    """Config to specify an AiiDA entry path."""

    aiida_file: Optional[str] = Field(
        None, description="AiiDA file that contains the structures."
    )
    aiida_profile: Optional[str] = Field(
        None, description="AiiDA profile that contains the structures."
    )
    aiida_group: Optional[str] = Field(
        None,
        description="AiiDA group that contains the structures. 'None' assumes all StructureData nodes",
    )

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
