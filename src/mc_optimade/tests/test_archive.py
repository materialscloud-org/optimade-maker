from mc_optimade.config import UnsupportedConfigVersion
import traceback

archive_url = "https://staging-archive.materialscloud.org/"
test_record_id = 1408


def test_archive_record_metadata():
    """Test ArchiveRecord to read metadata."""
    from mc_optimade.archive.archive_record import ArchiveRecord

    try:
        record = ArchiveRecord(test_record_id, archive_url=archive_url)
        assert len(record.files) == 4
        assert record.is_optimade_record() is True
    except UnsupportedConfigVersion:
        traceback.print_exc()


def test_archive_record_process():
    """Test ArchiveRecord to download files."""
    import os

    from mc_optimade.archive.archive_record import ArchiveRecord

    try:
        record = ArchiveRecord(
            test_record_id,
            archive_url=archive_url,
        )
        record.process()
        files = os.listdir(record.default_path)
        assert "structures.zip" in files
    except UnsupportedConfigVersion as e:
        traceback.print_exc()
