import importlib.util
import json
import shutil
from pathlib import Path

import numpy as np
import pytest
from optimade.models import EntryInfoResource

from optimade_maker.convert import convert_archive

AIIDA_AVAILABLE = bool(importlib.util.find_spec("aiida"))

EXAMPLE_ARCHIVES = (Path(__file__).parent.parent / "examples").glob("*")


@pytest.mark.parametrize("archive_path", EXAMPLE_ARCHIVES, ids=lambda path: path.name)
def test_convert_example_archives(archive_path, tmp_path):
    """This test will run through all examples in the examples folder and
    attempt to convert them to OPTIMADE data following the provided config.

    If a file `.testing/first_entry.json` is found, the first entry in the resulting
    OPTIMADE API will be compared against this file.

    """

    if "aiida" in archive_path.name and not AIIDA_AVAILABLE:
        pytest.skip(
            "Skipping test for AiiDA archive, as it requires AiiDA to be installed."
        )
    # copy example into temporary path
    tmp_path = tmp_path / archive_path.name
    shutil.copytree(archive_path, tmp_path)

    jsonl_path = convert_archive(tmp_path, overwrite=True)
    assert jsonl_path.exists()

    jsonl_path_custom = convert_archive(
        tmp_path, jsonl_path=tmp_path / "test.jsonl", overwrite=True
    )
    assert jsonl_path_custom.exists()

    first_entry_path = archive_path / ".testing" / "first_entry.json"
    first_entry = None
    if first_entry_path.exists():
        first_entry = json.loads(first_entry_path.read_text())

    with open(jsonl_path, "r") as fhandle:
        # check that header exists as first line
        header_jsonl = fhandle.readline()
        header = json.loads(header_jsonl)
        assert "x-optimade" in header

        # check that info endpoint equivalent exists as next line
        info = json.loads(fhandle.readline())
        assert EntryInfoResource(**info)

        # now check for entry lines:
        # if provided, check that the first entry matches the tabulated data
        if first_entry is not None:
            while next_line := fhandle.readline():
                try:
                    next_entry = json.loads(next_line)
                except json.JSONDecodeError:
                    assert False, f"Could not read line {next_line} as JSON"

                if next_entry.get("type") == first_entry["type"]:
                    break
            else:
                assert False, (
                    "No structures found in archive but test first entry was provided"
                )

            for key in ("id", "type", "relationships"):
                assert next_entry[key] == first_entry[key]

            def check_arrays(reference, test, field):
                ref_array = reference["attributes"].pop(field, None)
                if ref_array:
                    np.testing.assert_array_almost_equal(
                        ref_array, test["attributes"].pop(field)
                    )

            # check JSON serialization of attributes compared to reference data, handling species and numerical arrays separately
            array_fields = ["cartesian_site_positions", "lattice_vectors"]
            for field in array_fields:
                check_arrays(first_entry, next_entry, field)
                first_entry.pop(field, None)
                next_entry.pop(field, None)

            # check that last_modified is a reasonable date if set in the test data
            # direct JSONL submissions will not have this field
            first_last_modified = first_entry["attributes"].pop("last_modified", None)
            next_last_modified = next_entry["attributes"].pop("last_modified", None)
            assert (next_last_modified is None) == (first_last_modified is None)

            first_entry_species = first_entry["attributes"].pop("species", None)
            next_entry_species = next_entry["attributes"].pop("species", None)
            if first_entry_species:
                assert json.dumps(
                    sorted(first_entry_species, key=lambda _: _["name"])
                ) == json.dumps(sorted(next_entry_species, key=lambda _: _["name"]))

            assert json.dumps(
                first_entry["attributes"], sort_keys=True, indent=2
            ) == json.dumps(next_entry["attributes"], sort_keys=True, indent=2)


def test_unique_id_generator():
    """Unit tests for some common cases of the unique ID generator."""

    from optimade_maker.convert import _set_unique_entry_ids

    entry_ids = [
        "data/structures/1.cif",
        "data/structures/2.cif",
        "data/structures/3.cif",
    ]
    assert _set_unique_entry_ids(entry_ids) == ["1", "2", "3"]

    entry_ids = ["data/structures/1", "data/structures/2", "data/structures/3"]
    assert _set_unique_entry_ids(entry_ids) == ["1", "2", "3"]

    entry_ids = [
        "data/structures/1/POSCAR",
        "data/structures/2/POSCAR",
        "data/structures/3/POSCAR",
    ]
    assert _set_unique_entry_ids(entry_ids) == ["1", "2", "3"]

    entry_ids = [
        "data1",
        "data2",
        "data3",
    ]
    assert _set_unique_entry_ids(entry_ids) == entry_ids

    entry_ids = [
        "data.zip/data/structures/1.cif",
        "data.zip/data/structures/2.cif",
        "data.zip/data/structures/3.cif",
    ]
    assert _set_unique_entry_ids(entry_ids) == ["1", "2", "3"]

    entry_ids = [
        "data.tar.gz/data/structures/1.cif",
        "data.tar.gz/data/structures/2.cif",
        "data.tar.gz/data/structures/3.cif",
    ]
    assert _set_unique_entry_ids(entry_ids) == ["1", "2", "3"]

    entry_ids = [
        "data.tar.gz/data/structures/1.cif.gz",
        "data.tar.gz/data/structures/2.cif.gz",
        "data.tar.gz/data/structures/3.cif.gz",
    ]
    assert _set_unique_entry_ids(entry_ids) == ["1", "2", "3"]

    entry_ids = [
        "data.tar.gz/data/set1/1.cif/file",
        "data.tar.gz/data/set1/2.cif/file",
        "data.tar.gz/data/set2/3.xyz/file",
        "data.tar.gz/data/set2/4.xyz/file",
    ]
    assert _set_unique_entry_ids(entry_ids) == [
        "set1/1.cif",
        "set1/2.cif",
        "set2/3.xyz",
        "set2/4.xyz",
    ]

    entry_ids = [
        "data/structures/1.cif",
    ]
    assert _set_unique_entry_ids(entry_ids) == ["1"]
