
archive_url = "https://staging-archive.materialscloud.org/"
test_record_id = 1407

def test_archive_record_metadata():
    """Test ArchiveRecord to read metadata."""
    from mc_optimade.archive.archive_record import ArchiveRecord
    record = ArchiveRecord(test_record_id, archive_url=archive_url)
    assert len(record.files) == 4
    assert record.is_optimade_record() == True

def test_archive_record_process():
    """Test ArchiveRecord to download files."""
    from mc_optimade.archive.archive_record import ArchiveRecord
    import os
    record = ArchiveRecord(test_record_id,
                           archive_url=archive_url,
                           dir="/tmp/archive")
    record.process()
    files = os.listdir(record.dir)
    assert "structures.zip" in files
