"""This submodule takes an MCloud entry on disk and an `optimade.yaml` config
file as input and then constructs an OPTIMADE JSONL file that desribes a full
OPTIMADE API.

"""

import datetime
import os
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import tqdm
from optimade import __api_version__ as OPTIMADE_API_VERSION
from optimade.models import EntryInfoResource, EntryResource
from optimade.server.schemas import ENTRY_INFO_SCHEMAS, retrieve_queryable_properties

from .aiida_plugin import AiidaEntryPath, construct_entries_from_aiida
from .config import Config, EntryConfig, JSONLConfig, ParsedFiles, PropertyDefinition

PROVIDER_PREFIX = os.environ.get("OPTIMAKE_PROVIDER_PREFIX", "optimake")


def _construct_entry_type_info(
    type: str,
    properties: list[PropertyDefinition] | list[dict],
    provider_prefix: str,
) -> EntryInfoResource:
    """Take the provided property definitions and construct an entry info response.

    Returns:
        The full `EntryInfoResource` object.

    """

    default_properties = {}
    if type in ENTRY_INFO_SCHEMAS:
        default_properties = retrieve_queryable_properties(
            ENTRY_INFO_SCHEMAS[type], {"id", "type", "attributes"}
        )

    info: dict[str, Any] = {"formats": ["json"], "description": type}
    info["properties"] = {}
    for p in properties:
        if isinstance(p, PropertyDefinition):
            p = p.model_dump()

        p_name = (
            f"_{provider_prefix}_{p['name']}"
            if not p["name"].startswith(f"_{provider_prefix}")
            else p["name"]
        )
        info["properties"][p_name] = {
            "description": p.get("description"),
            "unit": p.get("unit"),
            "type": p.get("type"),
            "title": p.get("title"),
        }

    info["properties"].update(default_properties)
    info["output_fields_by_format"] = {}
    info["output_fields_by_format"]["json"] = list(info["properties"].keys())
    return EntryInfoResource(**info)


def convert_archive(
    archive_path: Path,
    jsonl_path: Path | None = None,
    limit: int | None = None,
    overwrite: bool = False,
) -> Path:
    """Convert a raw data archive to an OPTIMADE JSONL file.

    Parameters:
        archive_path: The location of the `optimade.yaml` file to convert.
        jsonl_path: The location to write the JSONL file to. If not provided,
            write to `<archive_path>/optimade.jsonl`.
        limit: The maximum number of entries to parse (useful for testing).

    Raises:
        FileNotFoundError: If any of the data paths in the config file,
            or config file itself, do not exist.
        FileExistsError: If the JSONL file already exists at the provided path.

    """

    # load the config from the root of the archive
    mc_config = Config.from_file(archive_path / "optimade.yaml")

    if not jsonl_path:
        jsonl_path = archive_path / "optimade.jsonl"
    if jsonl_path.exists() and not overwrite:
        raise RuntimeError(f"Not overwriting existing file at {jsonl_path}")

    # if the config specifies just a JSON-L, then extract any archives
    # and return the JSONL path
    if isinstance(mc_config.entries, JSONLConfig):
        if mc_config.entries.file is not None:
            inflate_archive(archive_path, Path(mc_config.entries.file))
        src_jsonl_path = archive_path / mc_config.entries.jsonl_path
        if jsonl_path != src_jsonl_path:
            # add a symlink to the specified jsonl_path
            if jsonl_path.exists():
                if overwrite:
                    jsonl_path.unlink()
                else:
                    raise RuntimeError(f"Not overwriting existing file at {jsonl_path}")
            jsonl_path.symlink_to(archive_path / src_jsonl_path)
        return jsonl_path

    # first, decompress any provided data archives
    decompress_paths: set[Path] = set()
    for entry in mc_config.entries:
        for entry_path in entry.entry_paths:
            if getattr(entry_path, "matches", None):
                decompress_paths.add((archive_path / str(entry_path.file)).resolve())
        for prop_path in entry.property_paths:
            if getattr(prop_path, "matches", None):
                decompress_paths.add((archive_path / str(prop_path.file)).resolve())

    for decompress_path in decompress_paths:
        inflate_archive(archive_path, decompress_path)

    optimade_entries: dict[str, list[dict]] = defaultdict(list)

    for entry in mc_config.entries:
        optimade_entries[entry.entry_type].extend(
            construct_entries(
                archive_path, entry, PROVIDER_PREFIX, limit=limit
            ).values()
        )

    property_definitions = defaultdict(list)
    for entry in mc_config.entries:
        property_definitions[entry.entry_type].extend(entry.property_definitions)

    jsonl_path = write_optimade_jsonl(
        archive_path,
        optimade_entries,
        property_definitions,
        PROVIDER_PREFIX,
        jsonl_path,
        overwrite,
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
        CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB
        if compressed_open:
            with compressed_open(real_path, "rb") as compressed_file:
                with open(real_path.with_suffix(""), "wb") as output_file:
                    # Read and write data in chunks to conserve memory
                    while True:
                        chunk = compressed_file.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        output_file.write(chunk)

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
    limit: int | None = None,
) -> tuple[list[Any], list[str]]:
    """Loop through the matches by file and parse them into
    the intermediate format, also generating IDs for each.

    Parameters:
        archive_path: The path to the archive.
        matches_by_file: A dictionary of matches by file.
        entry_type: The type of entry to parse.
        limit: The maximum number of entries to parse

    Returns:
        A list of parsed entries and a list of IDs.

    """
    from .parsers import ENTRY_PARSERS

    parsed_entries = []
    entry_ids: list[str] = []
    for archive_file in matches_by_file:
        for ind, _path in enumerate(
            tqdm.tqdm(
                matches_by_file[archive_file],
                desc=f"Parsing {entry_type} files",
            )
        ):
            if limit and ind >= limit:
                break

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

    if len(set(entry_ids)) != len(entry_ids):
        raise RuntimeError(
            "Duplicate entry IDs found even when generated directly from filepaths. This should not be possible."
        )

    return parsed_entries, entry_ids


def _set_unique_entry_ids(entry_ids: list[str]) -> list[str]:
    """Attempt to make a unique set of entry IDs, following a
    series of deterministic rules.

    Parameters:
        entry_ids: A list of entry IDs derived from file paths.

    Returns:
        A list of unique entry IDs.

    """

    if len(entry_ids) == 1:
        return [os.path.splitext(os.path.basename(entry_ids[0]))[0]]

    new_ids: list[str] = list(entry_ids)

    def _strip_common_path(ids, from_back=False):
        if not from_back:
            ids_split = [id.split("/") for id in ids]
        else:
            ids_split = [id.split("/")[::-1] for id in ids]

        index = 0
        while True:
            try:
                element = ids_split[0][index]
                if all(id_split[index] == element for id_split in ids_split):
                    index += 1
                else:
                    break
            except IndexError:
                break

        if from_back:
            res = ["/".join(id_split[index:][::-1]) for id_split in ids_split]
        else:
            res = ["/".join(id_split[index:]) for id_split in ids_split]

        return res

    new_ids = _strip_common_path(new_ids)
    new_ids = _strip_common_path(new_ids, from_back=True)

    def _strip_common_extensions(ids):
        new_ids = list(ids)
        while True:
            ext = os.path.splitext(new_ids[0])[1]
            if ext == "":
                break
            if all(os.path.splitext(id)[1] == ext for id in new_ids):
                new_ids = [os.path.splitext(id)[0] for id in new_ids]
            else:
                break
        return new_ids

    new_ids = _strip_common_extensions(new_ids)

    return new_ids


def _parse_properties_from_files(
    property_matches_by_file: dict[str | None, list[Path]],
    property_definitions: list[PropertyDefinition],
) -> dict[str, dict[str, Any]]:
    """Loop through the property matches by file and parse them into a dictionary"""
    from .parsers import PROPERTY_PARSERS

    parsed_properties: dict[str, dict[str, Any]] = defaultdict(dict)
    errors = []

    if not property_matches_by_file:
        return {}

    for archive_file in property_matches_by_file:
        for _path in tqdm.tqdm(
            property_matches_by_file[archive_file],
            desc="Parsing property files",
        ):
            file_ext = _path.suffix
            for parser in PROPERTY_PARSERS[file_ext]:
                try:
                    properties = parser(_path, property_definitions)
                    for id in properties:
                        parsed_properties[id].update(properties[id])
                    break
                except Exception as exc:
                    errors.append(exc)
                    continue
            else:
                raise RuntimeError(
                    f"Could not parse properties file {_path} with any of the provided parsers {PROPERTY_PARSERS[file_ext]}. Errors: {errors}"
                )
    if not parsed_properties:
        raise RuntimeError(
            f"Could not parse properties files with any of the provided parsers. Errors: {errors}"
        )
    return parsed_properties


def _assign_and_validate_properties(
    optimade_entries: dict[str, EntryResource],
    parsed_properties: dict[str, dict[str, Any]],
    property_definitions: list[PropertyDefinition],
    provider_prefix: str,
) -> None:
    """Assign parsed properties to the OPTIMADE entries."""
    from .parsers import TYPE_MAP

    # Collect all property fields that are already present in the OPTIMADE entries
    existing_property_fields: set[str] = set()
    # Only check the first entry for property fields (it should have all the fields)
    first_entry = next(iter(optimade_entries.values()), None)
    if first_entry:
        prefix = f"_{provider_prefix}_"
        existing_property_fields |= set(
            k[len(prefix) :]
            for k in first_entry["attributes"].keys()
            if k.startswith(prefix)
        )

    all_parsed_fields: set[str] = set()
    for properties in parsed_properties.values():
        all_parsed_fields |= set(properties.keys())

    # Warn if any parsed property IDs does not exist in the OPTIMADE entries
    optimade_immutable_ids = {
        entry["attributes"].get("immutable_id") for entry in optimade_entries.values()
    }
    for id in parsed_properties:
        if id not in optimade_entries and id not in optimade_immutable_ids:
            warnings.warn(
                f"Could not find entry {id!r} in OPTIMADE entries.",
            )

    # Match properties up to the descriptions provided in the config
    property_def_dict: dict[str, PropertyDefinition] = {
        p.name: p for p in property_definitions
    }

    if parsed_properties:
        # Assign parsed properties to the OPTIMADE entries
        # Look for precisely matching IDs, or 'filename' matches
        for id in optimade_entries:
            # detect any other compatible IDs; either those matching immutable ID or those matching the filename rule
            property_entry_id = optimade_entries[id]["attributes"].get(
                "immutable_id", None
            )
            if property_entry_id is None:
                # try to find a matching ID based on the filename
                property_entry_id = id.split("/")[-1].split(".")[0]

            if (property_entry_id not in parsed_properties) and (
                id not in parsed_properties
            ):
                warnings.warn(
                    f"Could not find entry {id!r} (or fully-qualified {property_entry_id!r}) in parsed properties",
                )
                continue

            # Loop over all defined properties and assign them to the entry, setting to None if missing
            # Also cast types if provided
            for property in all_parsed_fields:
                # Look up both IDs: the file path-based ID or the ergonomic one
                # Different property sources can use different ID schemes internally
                value = parsed_properties.get(property_entry_id, {}).get(
                    property, None
                ) or parsed_properties.get(id, {}).get(property, None)
                if property not in property_def_dict:
                    # Fields that are not configured but are present in the property file, will be warned later
                    continue
                if value is not None and property_def_dict[property].type in TYPE_MAP:
                    try:
                        value = TYPE_MAP[property_def_dict[property].type](value)
                    except Exception as exc:
                        raise RuntimeError(
                            f"Could not cast {value=} for {property=} to type {property_def_dict[property].type!r} for entry {id!r}"
                        ) from exc

                optimade_entries[id]["attributes"][f"_{provider_prefix}_{property}"] = (
                    value
                )

    # Finally, check that all expected property fields are present
    expected_property_fields = set(p.name for p in property_definitions)
    all_property_fields = existing_property_fields | all_parsed_fields

    if expected_property_fields != all_property_fields:
        warning_message = "Mismatch between parsed property fields (A) and those defined in config (B)."
        if all_property_fields - expected_property_fields:
            warning_message += f"\n(A - B) = {all_property_fields - expected_property_fields} (will be omitted from API; if intended this can be ignored)."
        if expected_property_fields - all_property_fields:
            warning_message += f"\n(B - A) = {expected_property_fields - all_property_fields} (configured, but missing; check for typos or missing aliases)"

        warnings.warn(warning_message)


def construct_entries_from_files(
    archive_path: Path,
    entry_config: EntryConfig,
    provider_prefix: str,
    limit: int | None = None,
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
    from .parsers import ENTRY_PARSERS, OPTIMADE_CONVERTERS

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
    parsed_entries, file_path_entry_ids = _parse_entries(
        archive_path,
        entry_matches_by_file,
        entry_config.entry_type,
        limit=limit,
    )

    # Generate a better set of entry IDs
    unique_entry_ids = _set_unique_entry_ids(file_path_entry_ids)

    timestamp = datetime.datetime.now().isoformat()

    # Construct OPTIMADE entries from intermediate format
    optimade_entries: dict[str, EntryResource] = {}
    for file_path_entry_id, unique_entry_id, entry in tqdm.tqdm(
        zip(file_path_entry_ids, unique_entry_ids, parsed_entries),
        desc=f"Constructing OPTIMADE {entry_config.entry_type} entries",
    ):
        exceptions = {}
        for converter in OPTIMADE_CONVERTERS[entry_config.entry_type]:
            try:
                entry = converter(
                    entry,
                    properties=entry_config.property_definitions,
                    prefix=provider_prefix,
                )  # type: ignore[call-arg]
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
            entry = entry.model_dump()

        if not entry["id"]:
            entry["id"] = unique_entry_id
        else:
            # If entry ID is already set, this means it has been hardcoded somehow in the submitted data
            # so this should also be used for the immutable ID
            entry["attributes"]["immutable_id"] = entry["id"]

        if entry["id"] in optimade_entries:
            raise RuntimeError(f"Duplicate entry ID found: {entry['id']}")

        optimade_entries[entry["id"]] = entry

        if not entry["attributes"].get("immutable_id"):
            entry["attributes"]["immutable_id"] = file_path_entry_id

        entry["attributes"]["last_modified"] = timestamp
    return optimade_entries


def construct_entries(
    archive_path: Path,
    entry_config: EntryConfig,
    provider_prefix: str,
    limit: int | None = None,
) -> dict[str, dict]:
    if isinstance(entry_config.entry_paths, AiidaEntryPath):
        optimade_entries = construct_entries_from_aiida(
            archive_path, entry_config, provider_prefix
        )

    else:
        optimade_entries = construct_entries_from_files(
            archive_path, entry_config, provider_prefix, limit=limit
        )

    # Parse properties from `property_paths` and assign them to the OPTIMADE entries
    property_matches_by_file: dict[str | None, list[Path]] = _get_matches(
        archive_path, entry_config.property_paths
    )
    _check_missing(property_matches_by_file)

    parsed_properties = _parse_properties_from_files(
        property_matches_by_file,
        entry_config.property_definitions,
    )

    _assign_and_validate_properties(
        optimade_entries,
        parsed_properties,
        entry_config.property_definitions,
        provider_prefix,
    )

    return optimade_entries


def write_optimade_jsonl(
    archive_path: Path,
    optimade_entries: dict[str, list[EntryResource]],
    property_definitions: dict[str, list[PropertyDefinition]],
    provider_prefix: str,
    jsonl_path: Path | None = None,
    overwrite: bool = False,
) -> Path:
    """Write OPTIMADE entries to a JSONL file.

    Parameters:
        archive_path: Path to the archive.
        optimade_entries: OPTIMADE entries to write.
        property_definitions: Property definitions to write.
        provider_prefix: Prefix to use for the provider.
        jsonl_path: Path to write the JSONL file to. If not provided,
            will write to `<archive_path>/optimade.jsonl`.

    Raises:
        RuntimeError: If the JSONL file already exists.

    """
    import json

    if not jsonl_path:
        jsonl_path = archive_path / "optimade.jsonl"

    if jsonl_path.exists() and not overwrite:
        raise RuntimeError(f"Not overwriting existing file at {jsonl_path}")

    with open(jsonl_path, "w") as jsonl:
        # write the optimade jsonl header
        header = {"x-optimade": {"meta": {"api_version": OPTIMADE_API_VERSION}}}
        jsonl.write(json.dumps(header))
        jsonl.write("\n")

        for entry_type in property_definitions:
            entry_info = _construct_entry_type_info(
                entry_type, property_definitions[entry_type], provider_prefix
            )
            jsonl.write(entry_info.model_dump_json())
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
