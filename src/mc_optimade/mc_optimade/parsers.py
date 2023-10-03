from pathlib import Path
from typing import Any, Callable

import ase.io
import pandas
import pybtex.database
import pymatgen.core
import pymatgen.entries.computed_entries
from optimade.adapters import Structure
from optimade.models import EntryResource
from pymatgen.entries.computed_entries import ComputedStructureEntry

from mc_optimade.config import PropertyDefinition


def pybtex_to_optimade(bib_entry: Any, properties=None) -> EntryResource:
    raise NotImplementedError


def load_csv_file(p: Path) -> dict[str, dict[str, Any]]:
    """Parses a CSV file found at path `p` and returns a dictionary
    of properties keyed by ID.

    Requires the `id` column to be present in the CSV file, which will
    be matched with the generated IDs.

    Returns:
        A dictionary of ID -> properties.

    """
    df = pandas.read_csv(p)
    if "id" not in df:
        raise RuntimeError(
            "CSV file {p} must have an 'id' column: not just {df.columns}"
        )

    df = df.set_index("id")

    return df.to_dict(orient="index")


PROPERTY_PARSERS: dict[str, list[Callable[[Path], Any]]] = {
    ".csv": [load_csv_file],
}

TYPE_MAP: dict[str | None, type] = {
    "float": float,
    "string": str,
    "integer": int,
    "boolean": bool,
}


def wrapped_json_parser(parser):
    """This wrapper allows `from_dict` parser functions to be called
    on a single JSON file.

    """

    def _wrapped_json_parser(path: Path) -> Any:
        import json

        with open(path) as f:
            data = json.load(f)

        entries = []
        # Either we already have a list of entries, or we need to find which key they are stored under
        if isinstance(data, list):
            for entry in data:
                entries.append(entry)

        elif isinstance(data, dict):
            for k in data:
                if isinstance(data[k], list):
                    for entry in data[k]:
                        entries.append(entry)

        for ind, e in enumerate(entries):
            try:
                entries[ind] = parser(e)
            except Exception as e:
                raise RuntimeError(f"Error parsing entry {entry} in {path}: {e}")

        return entries

    return _wrapped_json_parser


ENTRY_PARSERS: dict[str, list[Callable[[Path], Any]]] = {
    "structures": [
        ase.io.read,
        wrapped_json_parser(
            pymatgen.entries.computed_entries.ComputedStructureEntry.from_dict
        ),
        wrapped_json_parser(pymatgen.core.Structure.from_dict),
    ],
    "references": [pybtex.database.parse_file],
}


def parse_computed_structure_entry(
    pmg_entry: ComputedStructureEntry,
    properties: list[PropertyDefinition] | None = None,
) -> dict:
    """Convert a pymatgen ComputedStructureEntry to an OPTIMADE EntryResource."""

    entry = Structure.ingest_from(pmg_entry.structure).entry.dict()
    entry["attributes"].update(pmg_entry.data)
    entry["attributes"]["energy"] = pmg_entry.energy
    # try to find any unique ID fields and use it to overwrite the generated one
    for key in ("id", "mat_id", "task_id"):
        id = pmg_entry.data.get(key)
        if id:
            entry["id"] = id
            break

    for p in properties or []:
        # loop through any property aliases, saving the value if found and only checking
        # the real name if not
        for alias in p.aliases or []:
            if value := pmg_entry.data.get(alias) is not None:
                entry["attributes"][p.name] = value
                break
        else:
            entry["attributes"][p.name] = pmg_entry.data.get(p.name)

    return entry


def structure_ingest_wrapper(entry, properties=None):  # type: ignore
    return Structure.ingest_from(entry)


OPTIMADE_CONVERTERS: dict[
    str, list[Callable[[Any, list[PropertyDefinition] | None], EntryResource | dict]]
] = {
    "structures": [structure_ingest_wrapper, parse_computed_structure_entry],
    "references": [pybtex_to_optimade],
}
