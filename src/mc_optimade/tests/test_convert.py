import json
import shutil
from pathlib import Path

import pytest

from mc_optimade.convert import convert_archive

EXAMPLE_ARCHIVES = (Path(__file__).parent.parent / "examples").glob("*")


@pytest.mark.parametrize("archive_path", EXAMPLE_ARCHIVES)
def test_convert_example_archives(archive_path, tmp_path):
    # copy example into temporary path
    tmp_path = tmp_path / archive_path.name
    shutil.copytree(archive_path, tmp_path)

    jsonl_path = convert_archive(tmp_path)
    assert jsonl_path.exists()

    with open(jsonl_path, "r") as fhandle:
        # check that header exists
        header_jsonl = fhandle.readline()
        header = json.loads(header_jsonl)
        assert "x-optimade" in header


def test_example_archive_structure_id(tmp_path):
    STRUCT_ID = (
        "structures.zip/structures/cifs/55c564f6-ac6a-4122-b8d9-0ad9fe61e961.cif"
    )
    archive_path = Path(__file__).parent.parent / "examples/folder_of_cifs"

    # copy example into temporary path
    tmp_path = tmp_path / archive_path.name
    shutil.copytree(archive_path, tmp_path)

    jsonl_path = convert_archive(tmp_path)
    assert jsonl_path.exists()

    with open(jsonl_path, "r") as fhandle:
        fhandle.readline()  # skip header

        # check that 2nd line is a structure and the ID is correct
        # note: can be we assume that the order will always be the same?
        structure_jsonl = fhandle.readline()
        structure_dict = json.loads(structure_jsonl)
        assert structure_dict["id"] == STRUCT_ID
