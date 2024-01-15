import tqdm

from optimake.archive.archive_record import ArchiveRecord
from optimake.archive.utils import get_all_records, get_parsed_records

DEFAULT_ARCHIVE_URL = "https://archive.materialscloud.org/"



def process_records(records: list, archive_url: str=DEFAULT_ARCHIVE_URL):
    """
    Scan the Materials Cloud Archive entries, read the file info
    and check if there is a file called "optimade.y(ml|aml)".
    If so, triger the conversion step.
    """
    # get the old records by looping through the optimade_id.json files in the folders
    old_record_ids = get_parsed_records()
    for record in tqdm.tqdm(records, desc="Processing records"):
        record_id = record["id"]
        if record_id in old_record_ids:
            continue
        record = ArchiveRecord(record_id, archive_url=archive_url)
        if record.is_optimade_record():
            print(f"Record {record_id} is a OPTIMADE record.")
            record.process()


def scan_records(archive_url=DEFAULT_ARCHIVE_URL):
    """This script can be run as a cron job to check for new optimade entries in the Materials Cloud Archive, and convert them to OPTIMADE format."""
    print("Start scanning the Materials Cloud Archive for new OPTIMADE entries...")
    records = get_all_records(archive_url)
    process_records(records, archive_url)


if __name__ == "__main__":
    url = "https://staging-archive.materialscloud.org/"
    scan_records(url)
