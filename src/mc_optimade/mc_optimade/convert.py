"""This submodule takes an MCloud entry on disk and an `optimade.yaml` config
file as input and then constructs an OPTIMADE JSONL file that desribes a full
OPTIMADE API.

"""

import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import tqdm
from optimade.models import EntryInfoResource, EntryResource
from optimade.server.schemas import ENTRY_INFO_SCHEMAS, retrieve_queryable_properties

from .config import Config, EntryConfig, ParsedFiles, PropertyDefinition
from .parsers import ENTRY_PARSERS, OPTIMADE_CONVERTERS, PROPERTY_PARSERS, TYPE_MAP


def _construct_entry_type_info(
    type: str,
    properties: list[PropertyDefinition],
    provider_prefix: str,
) -> EntryInfoResource:
    """Take the provided property definitions and construct an entry info response.

    Returns:
        The full `EntryInfoResource` object.

    """

    default_properties = {}
    if type in ENTRY_INFO_SCHEMAS:
        default_properties = retrieve_queryable_properties(
            ENTRY_INFO_SCHEMAS[type](), {"id", "type", "attributes"}
        )

    info: dict[str, Any] = {"formats": ["json"], "description": type}
    info["properties"] = {
        f"_{provider_prefix}_{p.name}": {
            "description": p.description,
            "unit": p.unit,
            "type": p.type,
            "title": p.title,
        }
        for p in properties
    }
    info["properties"].update(default_properties)
    info["output_fields_by_format"] = {}
    info["output_fields_by_format"]["json"] = list(info["properties"].keys())
    return EntryInfoResource(**info)


def convert_archive(archive_path: Path) -> Path:
    """Convert an MCloud entry to an OPTIMADE JSONL file.

    Raises:
        FileNotFoundError: If any of the data paths in the config file,
            or config file itself, do not exist.

    """

    # load the config from the root of the archive
    mc_config = Config.from_file(archive_path / "optimade.yaml")

    # first, decompress any provided data paths
    data_paths: set[Path] = set()
    for entry in mc_config.entries:
        for e in entry.entry_paths:
            if e.matches:
                data_paths.add((archive_path / str(e.file)).resolve())
        for p in entry.property_paths:
            if p.matches:
                data_paths.add((archive_path / str(p.file)).resolve())

    for data_path in data_paths:
        inflate_archive(archive_path, data_path)

    optimade_entries: dict[str, list[dict]] = defaultdict(list)

    for entry in mc_config.entries:
        optimade_entries[entry.entry_type].extend(
            construct_entries(archive_path, entry, mc_config.provider_prefix).values()
        )

    property_definitions = defaultdict(list)
    for entry in mc_config.entries:
        property_definitions[entry.entry_type].extend(entry.property_definitions)

    jsonl_path = write_optimade_jsonl(
        archive_path,
        optimade_entries,
        property_definitions,
        mc_config.provider_prefix,
    )

    return jsonl_path


def inflate_archive(archive_path: Path, data_path: Path) -> None:
    """For a given compressed file in an archive entry, decompress it and place
    the contents at the root of the archive entry file system.

    Supports .tar.bz2, .tar.gz and .zip files, as well as individually compressed
    <x>.gz and <x>.bz2 files.

    """
    import bz2
    import gzip
    import tarfile
    import zipfile

    real_path = (Path(archive_path) / data_path).resolve()
    if not real_path.exists():
        raise FileNotFoundError(f"Could not find archive at {real_path=}")

    if real_path.suffix == ".zip":
        with zipfile.ZipFile(real_path, "r") as zip_ref:
            zip_ref.extractall(real_path.parent)

    # If .tar in filename suffixes, use `tarfile`'s compression detection
    elif ".tar" in real_path.suffixes:
        with tarfile.open(real_path, "r") as tar:
            tar.extractall(path=real_path.parent)

    # Otherwise assume this is a single compressed file
    # Decompress it and write it using the appropriate
    # method based on its suffix
    else:
        compressed_open: Callable | None = None
        if real_path.suffix == ".bz2":
            compressed_open = bz2.open
        elif real_path.suffix == ".gz":
            compressed_open = gzip.open

        # Get the compressed data and immediately write it back out, stripping
        # the compression suffix
        if compressed_open:
            with compressed_open(real_path, "r") as zip:
                with open(real_path.with_suffix(""), "w") as f:
                    f.write(zip.read().decode("utf-8"))

    return


def _get_matches(
    archive_path: Path, paths: list[ParsedFiles]
) -> dict[str | None, list[Path]]:
    """Loop through a set of `ParsedFile` objects and collect all
    files that match the provided glob/explicit syntax.

    Returns:
        A dictionary keyed by the archive file name (or None) containing
        a list of paths found within that archive.

    """
    matches_by_file: dict[str | None, list[Path]] = defaultdict(list)
    for path in paths:
        matches = path.matches or []
        for m in matches:
            if "*" in m:
                wildcard = sorted(list(Path(archive_path).glob(m)))
                if not wildcard:
                    raise FileNotFoundError(
                        f"Could not find any files matching wildcard {m!r}"
                    )
                matches_by_file[path.file] += wildcard
            else:
                matches_by_file[path.file] += [Path(archive_path) / m]

        if not matches:
            matches_by_file[path.file] += [Path(archive_path) / path.file]

    return matches_by_file


def _check_missing(matches_by_file: dict[str | None, list[Path]]) -> None:
    """Check if any matching files are missing.

    Raises:
        FileNotFoundError: If any files are missing.

    """
    missing_paths = []
    for archive_file_path in matches_by_file:
        for _path in matches_by_file[archive_file_path]:
            if not _path.exists():
                missing_paths.append(_path)
    if missing_paths:
        raise FileNotFoundError(f"Could not find the following files: {missing_paths}")


def _parse_entries(
    archive_path: Path,
    matches_by_file: dict[str | None, list[Path]],
    entry_type: str,
) -> tuple[list[Any], list[str]]:
    """Loop through the matches by file and parse them into
    the intermediate format, also generating IDs for each.

    Returns:
        A list of parsed entries and a list of IDs.

    """
    parsed_entries = []
    entry_ids: list[str] = []
    for archive_file in matches_by_file:
        for _path in tqdm.tqdm(
            matches_by_file[archive_file],
            desc=f"Parsing {entry_type} files",
        ):
            path_in_archive: Path = Path(_path).relative_to(Path(archive_path))
            exceptions = {}

            id_root = (
                f"{archive_file}/{path_in_archive}"
                if len(matches_by_file[archive_file]) > 1
                else str(archive_file)
            )

            for parser in ENTRY_PARSERS[entry_type]:
                try:
                    doc = parser(_path)
                    if not doc:
                        raise RuntimeError(f"No entries parsed by {parser}")

                    if isinstance(doc, list):
                        parsed_entries.extend(doc)
                        entry_ids.extend(
                            [f"{id_root}/{ind}" for ind, _ in enumerate(doc)]
                        )
                    else:
                        parsed_entries.append(doc)
                        entry_ids.append(id_root)
                    break
                except Exception as exc:
                    exceptions[parser] = exc
                    continue
            else:
                raise RuntimeError(
                    f"None of the provided parsers {ENTRY_PARSERS[entry_type]} could parse {_path}. Errors: {exceptions}"
                )

    return parsed_entries, entry_ids


def _parse_and_assign_properties(
    optimade_entries: dict[str, EntryResource],
    property_matches_by_file: dict[str | None, list[Path]],
    entry_type: str,
    property_definitions: list[PropertyDefinition],
    provider_prefix: str,
) -> None:
    """Loop through the property matches by file and parse them into the combined
    dictionary of OPTIMADE entries.

    """
    parsed_properties: dict[str, dict[str, Any]] = defaultdict(dict)
    errors = []
    all_property_fields: set[str] = set()
    for archive_file in property_matches_by_file:
        for _path in tqdm.tqdm(
            property_matches_by_file[archive_file],
            desc=f"Parsing properties for {entry_type} entries",
        ):
            file_ext = _path.suffix
            for parser in PROPERTY_PARSERS[file_ext]:
                try:
                    properties = parser(_path)
                    for id in parser(_path):
                        parsed_properties[id].update(properties[id])
                        all_property_fields |= set(properties[id].keys())
                    break
                except Exception as exc:
                    errors.append(exc)
                    continue
            else:
                raise RuntimeError(
                    f"Could not parse properties file {_path} with any of the provided parsers {PROPERTY_PARSERS[file_ext]}. Errors: {errors}"
                )

    # Match properties up to the descrptions provided in the config
    property_def_dict: dict[str, PropertyDefinition] = {
        p.name: p for p in property_definitions
    }
    expected_property_fields = set(property_def_dict.keys())

    if expected_property_fields != all_property_fields:
        warnings.warn(
            f"Found {all_property_fields=} in data but {expected_property_fields} in config"
        )

    for id in parsed_properties:
        if id not in optimade_entries:
            raise RuntimeError(
                f"Found {id=} in properties but not in entries {optimade_entries.keys()=}"
            )

        for property in all_property_fields:
            # Loop over all defined properties and assign them to the entry, setting to None if missing
            # Also cast types if provided
            value = parsed_properties[id].get(property, None)
            if value is not None and property_def_dict[property].type in TYPE_MAP:
                value = TYPE_MAP[property_def_dict[property].type](value)

            optimade_entries[id]["attributes"][f"_{provider_prefix}_{property}"] = value


def construct_entries(
    archive_path: Path, entry_config: EntryConfig, provider_prefix: str
) -> dict[str, dict]:
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

    # Collect entry paths using glob/explicit syntax
    entry_matches_by_file = _get_matches(archive_path, entry_config.entry_paths)
    _check_missing(entry_matches_by_file)

    # Parse into intermediate format
    parsed_entries, entry_ids = _parse_entries(
        archive_path,
        entry_matches_by_file,
        entry_config.entry_type,
    )

    # Parse properties
    property_matches_by_file: dict[str | None, list[Path]] = _get_matches(
        archive_path, entry_config.property_paths
    )
    _check_missing(property_matches_by_file)

    # Construct OPTIMADE entries from intermediate format
    optimade_entries: dict[str, EntryResource] = {}
    for entry_id, entry in tqdm.tqdm(
        zip(entry_ids, parsed_entries),
        desc=f"Constructing OPTIMADE {entry_config.entry_type} entries",
    ):
        exceptions = {}
        for converter in OPTIMADE_CONVERTERS[entry_config.entry_type]:
            try:
                entry = converter(entry, properties=entry_config.property_definitions)  # type: ignore[call-arg]
                if not isinstance(entry, dict):
                    entry = entry.entry
                break
            except Exception as exc:
                exceptions[converter] = exc
                continue
        else:
            raise RuntimeError(
                f"Could not convert entry {entry} with any of the provided converters: {OPTIMADE_CONVERTERS[entry_config.entry_type]}. Errors: {exceptions}"
            )

        if not isinstance(entry, dict):
            entry = entry.dict()

        if not entry["id"]:
            entry["id"] = entry_id

        if entry_id in optimade_entries:
            raise RuntimeError(f"Duplicate entry ID found: {entry_id}")

        optimade_entries[entry_id] = entry

    # Now try to parse the properties and assign them to OPTIMADE entries
    _parse_and_assign_properties(
        optimade_entries,
        property_matches_by_file,
        entry_config.entry_type,
        entry_config.property_definitions,
        provider_prefix,
    )

    return optimade_entries


def write_optimade_jsonl(
    archive_path: Path,
    optimade_entries: dict[str, list[EntryResource]],
    property_definitions: dict[str, list[PropertyDefinition]],
    provider_prefix: str,
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
        # write the optimade jsonl header
        header = {"x-optimade": {"meta": {"api_version": "1.1.0"}}}
        jsonl.write(json.dumps(header))
        jsonl.write("\n")

        for entry_type in property_definitions:
            entry_info = _construct_entry_type_info(
                entry_type, property_definitions[entry_type], provider_prefix
            )
            jsonl.write(entry_info.json())
            jsonl.write("\n")

        for entry_type in optimade_entries:
            if optimade_entries[entry_type]:
                for entry_dict in optimade_entries[entry_type]:
                    attributes = {
                        k: entry_dict["attributes"][k]
                        for k in entry_dict["attributes"]
                        if not k.startswith("_ase")
                    }
                    entry_dict["attributes"] = attributes
                    jsonl.write(json.dumps(entry_dict))
                    jsonl.write("\n")

    return jsonl_path
