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


def pybtex_to_optimade(bib_entry: Any) -> EntryResource:
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


def wrapped_json_parser(parser):
    """This wrapper allows `from_dict` parser functions to be called
    on a single JSON file.

    """

    def _wrapped_json_parser(path: Path) -> Any:
        import json

        with open(path) as f:
            data = json.load(f)
        entries = []
        if isinstance(data, dict):
            for k in data:
                if isinstance(data[k], list):
                    for entry in data[k]:
                        entries.append(parser(entry))

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


def parse_computed_structure_entry(pmg_entry: ComputedStructureEntry) -> dict:
    """Convert a pymatgen ComputedStructureEntry to an OPTIMADE EntryResource."""

    entry = Structure.ingest_from(pmg_entry.structure).entry.dict()
    entry["attributes"].update(pmg_entry.data)
    entry["attributes"]["energy"] = pmg_entry.energy
    # try to find any unique ID fields and use it to overwrite the generated one
    for key in ("id", "mat_id", "task_id"):
        entry["id"] = pmg_entry.data.get(key, entry["id"])
        break
    return entry


OPTIMADE_CONVERTERS: dict[str, list[Callable[[Any], EntryResource | dict]]] = {
    "structures": [Structure.ingest_from, parse_computed_structure_entry],
    "references": [pybtex_to_optimade],
}
