"""This submodule takes an MCloud entry on disk and an `optimade.yaml` config
file as input and then constructs an OPTIMADE JSONL file that desribes a full
OPTIMADE API.

"""

from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List

import ase.io
import pybtex.database
import tqdm
from optimade.adapters import Structure
from optimade.models import EntryResource

from .config import Config, EntryConfig


def pybtex_to_optimade(bib_entry: Any) -> EntryResource:
    raise NotImplementedError


ENTRY_PARSERS: Dict[str, Callable[[Path], Any]] = {
    "structures": ase.io.read,
    "references": pybtex.database.parse_file,
}

OPTIMADE_CONVERTERS: Dict[str, Callable[[Any], EntryResource]] = {
    "structures": Structure.ingest_from,
    "references": pybtex_to_optimade,
}


def convert_archive(archive_path: Path) -> Path:
    """Convert an MCloud entry to an OPTIMADE JSONL file.

    Raises:
        FileNotFoundError: If any of the data paths in the config file,
            or config file itself, do not exist.

    """

    # load the config from the root of the archive
    mc_config = Config.from_file(archive_path / "optimade.yaml")

    # first, decompress any provided data paths
    for data_path in mc_config.data_paths:
        inflate_archive(archive_path, data_path)

    optimade_entries = defaultdict(list)

    for entry in mc_config.entries:
        optimade_entries[entry.entry_type].extend(
            construct_entries(archive_path, entry)
        )

    jsonl_path = write_optimade_jsonl(archive_path, optimade_entries)

    return jsonl_path


def inflate_archive(archive_path: Path, data_path: str) -> None:
    """For a given compressed file in an archive entry, decompress it and place
    the contents at the root of the archive entry file system.

    Supports .bz2, .gz and .zip files, but does not yet support compressed .tar archives.

    """
    import bz2
    import gzip
    import zipfile

    real_path = (Path(archive_path) / data_path).resolve()
    if not real_path.exists():
        raise FileNotFoundError(f"Could not find archive at {real_path=}")

    if real_path.suffix == ".zip":
        with zipfile.ZipFile(real_path, "r") as zip_ref:
            zip_ref.extractall(real_path.parent)

    elif real_path.suffix == ".bz2":
        with bz2.open(real_path, "rb") as bz2_ref:
            with open(real_path.parent / real_path.stem, "wb") as out:
                out.write(bz2_ref.read())

    elif real_path.suffix == ".gz":
        with gzip.open(real_path, "rb") as gz_ref:
            with open(real_path.parent / real_path.stem, "wb") as out:
                out.write(gz_ref.read())

    return


def construct_entries(
    archive_path: Path, entry_config: EntryConfig
) -> List[EntryResource]:
    """Given an archive path and an entry specification,
    loop through the provided paths and try to ingest them
    with the given entry type.

    Raises:
        FileNotFoundError: If any of the data paths in the config
            file do not exist.
        RuntimeError: If the entry type is not supported.
        ValueError: If any of the files cannot be parsed into
            the given entry type.

    """

    if entry_config.entry_type not in ENTRY_PARSERS:
        raise RuntimeError(f"Parsing type {entry_config.entry_type} is not supported.")

    if entry_config.entry_type not in OPTIMADE_CONVERTERS:
        raise RuntimeError(
            f"Converting type {entry_config.entry_type} is not supported."
        )

    # collect entry paths using glob/explicit syntax
    real_entry_paths: List[Path] = []
    for path in entry_config.entry_paths:
        if "*" in path:
            wildcard = list(Path(archive_path).glob(path))
            if not wildcard:
                raise FileNotFoundError(
                    f"Could not find any files matching wildcard {path}"
                )
            real_entry_paths += wildcard
        else:
            real_entry_paths += [Path(archive_path) / path]

    # Check all files exist
    missing_paths = []
    for path in real_entry_paths:
        if not path.exists():
            missing_paths.append(path)
    if missing_paths:
        raise FileNotFoundError(f"Could not find the following files: {missing_paths}")

    # Parse all files
    parsed_entries = []
    entry_ids = []
    for path in tqdm.tqdm(
        real_entry_paths, desc=f"Parsing {entry_config.entry_type} files"
    ):
        parsed_entries.append(ENTRY_PARSERS[entry_config.entry_type](path))
        entry_ids.append(path.name)

    # Construct OPTIMADE entries
    optimade_entries = []
    for entry_id, entry in tqdm.tqdm(
        zip(entry_ids, parsed_entries),
        desc=f"Constructing OPTIMADE {entry_config.entry_type} entries",
    ):
        optimade_entries.append(
            OPTIMADE_CONVERTERS[entry_config.entry_type](entry).entry
        )

        optimade_entries[-1].id = entry_id

    return optimade_entries


def write_optimade_jsonl(
    archive_path: Path, optimade_entries: Dict[str, List[EntryResource]]
) -> Path:
    """Write OPTIMADE entries to a JSONL file.

    Raises:
        RuntimeError: If the JSONL file already exists.

    """
    import json

    jsonl_path = archive_path / "optimade.jsonl"

    if jsonl_path.exists():
        raise RuntimeError(f"Not overwriting existing file at {jsonl_path}")

    with open(archive_path / "optimade.jsonl", "a") as jsonl:
        for entry_type in optimade_entries:
            if optimade_entries[entry_type]:
                for entry in optimade_entries[entry_type]:
                    entry_dict = entry.dict()
                    attributes = {
                        k: entry_dict["attributes"][k]
                        for k in entry_dict["attributes"]
                        if not k.startswith("_")
                    }
                    entry_dict["attributes"] = attributes
                    jsonl.write(json.dumps(entry_dict))
                    jsonl.write("\n")

    return jsonl_path
