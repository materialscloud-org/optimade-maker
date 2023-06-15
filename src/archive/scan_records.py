from archive_record import ArchiveRecord
from utils import get_all_records, get_parsed_records

default_archive_api_url = 'https://archive.materialscloud.org/api/records/?sort=mostrecent&page=1&size=9999'

def process_records(records):
    """
    Scan the Materials Cloud Archive entries, read the file infor
    and check if there is a file called "optimade.yaml".
    If so, triger the conversion step.
    """
    # get the old records by looping through the optimade_id.json files in the folders
    old_record_ids = get_parsed_records()
    for record in records:
        print("process record: ", record["id"])
        record_id = record["id"]
        if record_id in old_record_ids:
            continue
        record = ArchiveRecord(record_id)
        if record.is_optimade_record():
            record.process()

def scan_records(archive_api_url=default_archive_api_url):
    """This script can be run as a cron job to check for new optimade entries in the Materials Cloud Archive, and convert them to OPTIMADE format.
    """
    print("Start scanning the Materials Cloud Archive for new OPTIMADE entries...")
    records = get_all_records(archive_api_url)
    process_records(records)
    
    
if __name__ == "__main__":
    scan_records()