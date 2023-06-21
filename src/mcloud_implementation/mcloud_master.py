#!/usr/bin/env python3

"""
Script that periodically runs on the MC optimade server and automatically spins up optimade APIs
consists of multiple fairly-independent steps
"""

import mc_optimade
from mc_optimade.archive.scan_records import scan_records
from mc_optimade.archive.archive_record import ArchiveRecord
from mc_optimade.archive.utils import get_all_records, get_parsed_records
from mc_optimade.config import Config

from pymongo import MongoClient

from tqdm import tqdm

import os

from pathlib import Path

from time import time

WORKING_DIR = "/tmp/archive"

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
    entry_folder = os.path.join(WORKING_DIR, record_doi_id)

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
                dl_start_time = time()
                record.download_optimade_files(path=entry_folder)
                print(f"-- Download finished! Time: {time()-dl_start_time:.2f}")
    except Exception as e:
        print(f"Skipping {record_id}, error:", repr(e))


# -------------------------------------------------------------------------------
# 2. check each folder in the WORKING_DIR and convert them to jsonl
#    skipped if:
#    * mongodb exists
#    * jsonl exists

print("#### ---------------------------------------------")
print("#### 2. Converting downloaded entries to jsonl")
print("#### ---------------------------------------------")

from mc_optimade.convert import convert_archive
from pathlib import Path

working_dir_contents = os.listdir(WORKING_DIR)

for folder_name in working_dir_contents:
    # note: the folder name is the DOI identifier.
    folder_path = os.path.join(WORKING_DIR, folder_name)

    # assume that the entries use .yaml instead of .yml extension
    if os.path.isdir(folder_path) and "optimade.yaml" in os.listdir(folder_path):

        jsonl_name = "optimade.jsonl"
        # skip if the jsonl file already exists
        if jsonl_name in os.listdir(folder_path):
            print(f"Skipping {folder_path}! {jsonl_name} already exists.")
            continue

        # skip if the mongodb already exists
        if folder_path in existing_dbs:
            print(f"{folder_path} skipped as corresponding MongoDB exists!")
            continue
        
        conv_start_time = time()
        jsonl_path = convert_archive(Path(folder_path))
        print(f"-- Conversion finished! Time: {time()-conv_start_time:.2f}")
        if jsonl_path.exists():
            print(f"Generated {os.path.join(folder_path, jsonl_path)}!")

# -------------------------------------------------------------------------------
# 3. use optimade-launch to load the jsonl to mongodb and launch the container
#    skipped if:
#    * mongodb database exists
#    * todo: what if db exists but container doesn't?

print("#### ---------------------------------------------")
print("#### 3. populating mongoDB and starting containers")
print("#### ---------------------------------------------")

import subprocess

SOCKET_DIR = "/home/ubuntu/optimade-sockets/"
BASE_URL_BASE = "http://dev-optimade.materialscloud.org/archive/"

olaunch_config_template = """
---
name: {DOI_ID}
jsonl_paths:
   - {JSONL_PATH}
mongo_uri: mongodb://localhost:27017
db_name: {DOI_ID}
unix_sock: {SOCKET_PATH}
optimade_base_url: {BASE_URL}
optimade_index_base_url: http://localhost
"""

working_dir_contents = os.listdir(WORKING_DIR)

for folder_name in working_dir_contents:
    # note: the folder name is the DOI identifier.
    folder_path = os.path.join(WORKING_DIR, folder_name)

    if os.path.isdir(folder_path) and "optimade.jsonl" in os.listdir(folder_path):
        doi_id = folder_name

        # skip if the mongodb already exists
        if doi_id in existing_dbs:
            print(f"{folder_path} skipped as corresponding MongoDB exists!")
            continue
        
        # write the optimade-launch-config.yml
        olaunch_config_path = os.path.join(folder_path, "optimade-launch-config.yaml")
        with open(olaunch_config_path, 'w') as fhandle:
            fhandle.write(olaunch_config_template.format(
                DOI_ID=doi_id,
                JSONL_PATH=os.path.join(folder_path, "optimade.jsonl"),
                SOCKET_PATH=os.path.join(SOCKET_DIR, doi_id+".sock"),
                BASE_URL=BASE_URL_BASE + doi_id
            ))
            print(f"Wrote {olaunch_config_path}!")

        # Call the CLI commands

        print("---- optimade-launch profile create")
        profile_start_time = time()
        command = f"optimade-launch profile create --config {olaunch_config_path}"
        output = subprocess.check_output(command, shell=True).decode('utf-8')
        print(output)
        print(f"-- optimade-launch profile create finished! Time: {time() - profile_start_time:.2f}")
        print("----")

        print("---- optimade-launch server start")
        server_start_time = time()
        command = f"optimade-launch -vvv server start -p {doi_id}"
        output = subprocess.check_output(command, shell=True).decode('utf-8')
        print(output)
        print(f"-- optimade-launch server start finished! Time: {time() - server_start_time:.2f}")
        print("----")


# Should the /tmp/archive/ab-cd folder be deleted here to save space?

# -------------------------------------------------------------------------------
# 4. update landing page based on socket files

print("#### ---------------------------------------------")
print("#### 4. update landing page")
print("#### ---------------------------------------------")

from string import Template

p = Path(__file__).with_name('landing_page.html.template')
with p.open('r') as f:
    landing_page_template = Template(f.read())


db_list_html = ""
for socket_file in Path(SOCKET_DIR).glob("*"):
    doi_id = socket_file.stem
    base_url = BASE_URL_BASE + doi_id
    db_list_html += f"<li><a href='{base_url}'>{base_url}</a></li>\n"

index_html_loc = "/var/www/html/index.html"
with open(index_html_loc, 'w') as f:
    f.write(landing_page_template.substitute(HTML_DB_LIST_ENTRIES=db_list_html))





