# Script that periodically runs on the MC optimade server and automatically spins up optimade APIs
# consists of multiple independent steps

import mc_optimade
from mc_optimade.archive.scan_records import scan_records
from mc_optimade.archive.archive_record import ArchiveRecord
from mc_optimade.archive.utils import get_all_records, get_parsed_records
from mc_optimade.config import Config

from pymongo import MongoClient

from tqdm import tqdm

import os

from pathlib import Path

WORKING_FOLDER = "/tmp/archive"

# Get list of db names in mongo. The script assumes that these entries are already set up and the process is skipped

existing_dbs = MongoClient().list_database_names()
print("Existing MongoDBs: ", existing_dbs)

# -------------------------------------------------------------------------------
# 1. go through each archive entry and download them if they're optimade-related,
#    to "/tmp/archive/ab-cd", where "ab-cd" is the doi identifier.
#    skipped if
#    * the folder exists
#    * the mongodb has a database with name "ab-cd"

print("#### ---------------------------------------------")
print("#### 1. Checking MC archive")
print("#### ---------------------------------------------")

archive_url = "https://staging-archive.materialscloud.org/"

records = get_all_records(archive_url)

for record in tqdm(records, desc="Processing records"):

    record_id = record["id"]
    record_doi = record["metadata"]["doi"]
    record_doi_id = record_doi.split(":")[-1]
    entry_folder = os.path.join(WORKING_FOLDER, record_doi_id)

    if record_doi_id in existing_dbs:
        print(f"{record_doi} skipped as corresponding MongoDB exists!")
        continue

    try:
        record = ArchiveRecord(record_id, archive_url=archive_url)
        if record.is_optimade_record():
            print(f"Record {record_id} is a OPTIMADE record.")
            if os.path.isdir(entry_folder) and len(os.listdir(entry_folder)) > 0:
                print(f"Folder {entry_folder} exists and is not empty, skipping the download.")
            else:
                record.download_optimade_files(path=entry_folder)
    except Exception as e:
        print(f"Skipping {record_id}, error:", repr(e))


# -------------------------------------------------------------------------------
# 2. check each folder in the WORKING_FOLDER and convert them to jsonl
#    skipped if:
#    * mongodb exists
#    * jsonl exists

print("#### ---------------------------------------------")
print("#### 2. Converting downloaded entries to jsonl")
print("#### ---------------------------------------------")

from mc_optimade.convert import convert_archive
from pathlib import Path

working_folder_contents = os.listdir(WORKING_FOLDER)

for folder_name in working_folder_contents:
    # note: the folder name is the DOI identifier.
    folder_path = os.path.join(WORKING_FOLDER, folder_name)

    # assume that the entries use .yaml instead of .yml extension
    if os.path.isdir(folder_path) and "optimade.yaml" in os.listdir(folder_path):

        jsonl_name = "optimade.jsonl"
        # skip if the jsonl file already exists
        if jsonl_name in os.listdir(folder_path):
            print(f"Skipping {folder_path}! {jsonl_name} already exists.")
            continue
        
        jsonl_path = convert_archive(Path(folder_path))
        if jsonl_path.exists():
            print(f"Generated {os.path.join(folder_path, jsonl_path)}!")

# 3. use optimade-launch to load the jsonl to mongodb and launch the container
#    skipped if:
#    * ...



