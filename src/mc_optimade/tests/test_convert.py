import json
import shutil
from pathlib import Path

import pytest
from optimade.models import EntryInfoResource, StructureResource

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
