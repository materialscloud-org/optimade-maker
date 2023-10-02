import json
import shutil
from pathlib import Path

import pytest
from optimade.models import EntryInfoResource, StructureResource

from mc_optimade.convert import convert_archive, inflate_archive

EXAMPLE_ARCHIVES = (Path(__file__).parent.parent / "examples").glob("*")


@pytest.mark.parametrize("archive_path", EXAMPLE_ARCHIVES)
def test_convert_example_archives(archive_path, tmp_path):
    """This test will run through all examples in the examples folder and
    attempt to convert them to OPTIMADE data following the provided config.

    If a file `.testing/first_entry.json` is found, the first entry in the resulting
    OPTIMADE API will be compared against this file.

    """
    # copy example into temporary path
    tmp_path = tmp_path / archive_path.name
    shutil.copytree(archive_path, tmp_path)

    jsonl_path = convert_archive(tmp_path)
    assert jsonl_path.exists()

    first_entry_path = archive_path / ".testing" / "first_entry.json"
    first_entry = None
    if first_entry_path.exists():
        first_entry = json.loads(first_entry_path.read_text())

    with open(jsonl_path, "r") as fhandle:
        # check that header exists
        header_jsonl = fhandle.readline()
        header = json.loads(header_jsonl)
        assert "x-optimade" in header

        # if provided, check that the first entry matches
        if first_entry is not None:
            while next_line := fhandle.readline():
                try:
                    next_entry = json.loads(next_line)
                except json.JSONDecodeError:
                    assert False, f"Could not read line {next_line} as JSON"

                if next_entry.get("type") == first_entry["type"]:
                    break
            else:
                assert (
                    False
                ), "No structures found in archive but test first entry was provided"

            # @ml-evs: species is the only key that can be written in any order, so here we
            # just sort before comparing. This will be fixed in the next optimade-python-tools
            if species := next_entry.get("attributes", {}).get("species"):
                next_entry["attributes"]["species"] = sorted(
                    species, key=lambda x: x["name"]
                )

            for key in ("id", "type", "relationships"):
                assert next_entry[key] == first_entry[key]

            assert next_entry["attributes"] == pytest.approx(first_entry["attributes"])


def test_decompress_bz2(tmp_path):
    archive_path = Path(__file__).parent.parent / "examples" / "bzipped_pymatgen"
    # copy example into temporary path
    tmp_path = tmp_path / archive_path.name
    shutil.copytree(archive_path, tmp_path)

    inflate_archive(tmp_path, "part_1.json.bz2")
    assert (tmp_path / "part_1.json").exists()


def test_example_archive_structure_id(tmp_path):
    STRUCT_ID = (
        "structures.zip/structures/cifs/55c564f6-ac6a-4122-b8d9-0ad9fe61e961.cif"
    )
    archive_path = Path(__file__).parent.parent / "examples" / "folder_of_cifs"

    # copy example into temporary path
    tmp_path = tmp_path / archive_path.name
    shutil.copytree(archive_path, tmp_path)

    jsonl_path = convert_archive(tmp_path)
    assert jsonl_path.exists()

    with open(jsonl_path, "r") as fhandle:
        header = json.loads(fhandle.readline())
        assert "x-optimade" in header
        info = json.loads(fhandle.readline())
        # TODO: need to include default OPTIMADE properties
        assert len(info["properties"]) == 3
        assert EntryInfoResource(**info)

        for _ in range(3):
            structure_jsonl = fhandle.readline()
            structure_dict = json.loads(structure_jsonl)
            assert StructureResource(**structure_dict)

            if structure_dict["id"] == STRUCT_ID:
                assert structure_dict["id"] == STRUCT_ID
                assert structure_dict["attributes"]["_mcloudarchive_energy"] == -0.54
                assert structure_dict["attributes"]["_mcloudarchive_property_b"] == 0.99
                assert (
                    structure_dict["attributes"]["_mcloudarchive_structure_description"]
                    == "some description"
                )
                break
        else:
            assert False, f"Could not find structure with id {STRUCT_ID}"
