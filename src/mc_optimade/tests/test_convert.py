import shutil
from pathlib import Path

import pytest

from mc_optimade import convert_archive

EXAMPLE_ARCHIVES = (Path(__file__).parent.parent / "examples").glob("*")


@pytest.mark.parametrize("archive_path", EXAMPLE_ARCHIVES)
def test_convert_example_archives(archive_path, tmp_path):
    # copy example into temporary path
    tmp_path = tmp_path / archive_path.name
    shutil.copytree(archive_path, tmp_path)

    jsonl_path = convert_archive(tmp_path)
    assert jsonl_path.exists()
    breakpoint()
