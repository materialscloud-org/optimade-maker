import traceback

import pytest
import requests
import urllib3

from optimade_maker.config import UnsupportedConfigVersion

archive_url = "https://staging-archive.materialscloud.org/"
test_record_id = 1419


def test_archive_record_metadata():
    """Test ArchiveRecord to read metadata."""
    from optimade_maker.archive.archive_record import ArchiveRecord

    try:
        record = ArchiveRecord(test_record_id, archive_url=archive_url)
        assert len(record.files_w_checksums) == 5
        assert record.is_optimade_record() is True
    except UnsupportedConfigVersion:
        traceback.print_exc()
    except (urllib3.exceptions.ConnectTimeoutError, requests.exceptions.ConnectTimeout):
        pytest.skip(f"Unable to connect to {archive_url}")


def test_archive_record_process():
    """Test ArchiveRecord to download files."""
    import os

    from optimade_maker.archive.archive_record import ArchiveRecord

    try:
        record = ArchiveRecord(
            test_record_id,
            archive_url=archive_url,
        )
        record.process()
        files = os.listdir(record.default_path)
        assert "structures.tar.gz" in files
    except UnsupportedConfigVersion:
        traceback.print_exc()
    except (urllib3.exceptions.ConnectTimeoutError, requests.exceptions.ConnectTimeout):
        pytest.skip(f"Unable to connect to {archive_url}")
