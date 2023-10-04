#!/usr/bin/env python3

"""
Script that periodically runs on the MC optimade server and automatically spins up
optimade APIs; consists of multiple fairly-independent steps
"""

from pymongo import MongoClient

import docker

from tqdm import tqdm

import os
import socket
import json
import subprocess

from pathlib import Path

from time import time

import traceback
import click
from datetime import datetime
from urllib.parse import urljoin

import generate_apache_file

SERVER_NAME = "dev-optimade.materialscloud.org"
BASE_URL = f"https://{SERVER_NAME}"
BASE_URL_INDEX = urljoin(BASE_URL, "/index")

ARCHIVE_URL = "https://staging-archive.materialscloud.org/"

DOWNLOAD_DIR = "/tmp/archive"
JSONL_NAME = "optimade.jsonl"
SOCKET_DIR = "/home/ubuntu/optimade-sockets/"

METADB_NAME = "metadata"

mongo_client = MongoClient("localhost", 27017)


def _get_random_empty_port():
    with socket.socket() as sock:
        sock.bind(("", 0))
        return sock.getsockname()[1]


def _mongodb_name(doi_id):
    return f"optimade_{doi_id}"


def _get_optimade_mongodbs(mongo_client):
    return [
        db for db in mongo_client.list_database_names() if db.startswith("optimade_")
    ]


def _get_optimade_containers():
    return [
        c.name
        for c in docker.DockerClient().containers.list()
        if c.name.startswith("optimade_")
    ]


def _add_record_metadata_to_mongodb(doi_id, data):
    collection = mongo_client[METADB_NAME]["entries"]
    filter_criteria = {"doi_id": doi_id}
    data["doi_id"] = doi_id
    # Insert if not exists or update if exists
    collection.update_one(filter_criteria, {"$set": data}, upsert=True)


def _get_record_metadata_processed(doi_id):
    collection = mongo_client[METADB_NAME]["entries"]
    filter_criteria = {"doi_id": doi_id}

    result = collection.find_one(filter_criteria)

    if result:
        mcid = result["metadata"]["mcid"]
        date_format = "%b %d, %Y, %H:%M:%S"
        return {
            "title": result["metadata"]["title"],
            "version": result["metadata"]["version"],
            "mcid": mcid,
            "url": f"{ARCHIVE_URL}record/{mcid}",
            "publication_date": datetime.strptime(
                result["metadata"]["publication_date"], date_format
            ),
        }

    return {}


def _download_entries_from_archive():
    """
    1.
    Go through each archive entry and if they're optimade-related, download them
    to <path>/ab-cd, where "ab-cd" is the doi identifier.
    skipped if
    * the subfolder already exists
    * the mongodb has a database with name "ab-cd"
    """
    print()
    print("#### ---------------------------------------------")
    print("#### Checking MC archive")
    print("#### ---------------------------------------------")
    from mc_optimade.archive.archive_record import ArchiveRecord
    from mc_optimade.archive.utils import get_all_records

    existing_dbs = _get_optimade_mongodbs(mongo_client)
    print("Existing MongoDBs: ", existing_dbs)

    records = get_all_records(ARCHIVE_URL, limit=9999)

    for record in tqdm(records, desc="Processing records"):
        record_id = record["id"]
        doi = record["metadata"]["doi"]
        doi_id = doi.split(":")[-1]
        entry_folder = os.path.join(DOWNLOAD_DIR, doi_id)

        try:
            recordArc = ArchiveRecord(record_id, archive_url=ARCHIVE_URL)
            if recordArc.is_optimade_record():
                print("------------------------------------------------")
                print(f"Record {record_id}/{doi_id} is an OPTIMADE record.")

                _add_record_metadata_to_mongodb(doi_id, record)

                if _mongodb_name(doi_id) in existing_dbs:
                    print(
                        f"{record_id}/{doi_id} skipped as corresponding"
                        + "MongoDB exists!"
                    )
                    continue
                if os.path.isdir(entry_folder) and len(os.listdir(entry_folder)) > 0:
                    print(
                        f"Folder {entry_folder} exists and is not empty,"
                        + "skipping the download."
                    )
                else:
                    time_start = time()
                    recordArc.download_optimade_files(path=entry_folder)
                    print(f"-- Download finished! Time: {time()-time_start:.2f}")
        except Exception:
            print(f"Skipping {record_id}/{doi_id}, error:")
            print(traceback.format_exc())


def _convert_entries_to_jsonl():
    """
    check each subfolder in <path> and convert them to jsonl
    skipped if:
    * jsonl exists
    * mongodb exists
    """

    print()
    print("#### ---------------------------------------------")
    print("#### Converting downloaded entries to jsonl")
    print("#### ---------------------------------------------")

    from mc_optimade.convert import convert_archive
    from pathlib import Path

    existing_dbs = _get_optimade_mongodbs(mongo_client)
    print("Existing MongoDBs: ", existing_dbs)

    working_dir_contents = os.listdir(DOWNLOAD_DIR)

    for folder_name in working_dir_contents:
        doi_id = folder_name
        folder_path = os.path.join(DOWNLOAD_DIR, folder_name)

        print("------------------------------------------------")
        print(doi_id)

        if _mongodb_name(doi_id) in existing_dbs:
            print(f"{doi_id} skipped as corresponding MongoDB exists!")
            continue

        if os.path.isdir(folder_path):
            if "optimade.yaml" not in os.listdir(folder_path):
                print(f"Skipping {folder_path}! optimade.yaml is missing.")
                continue

            # skip if the jsonl file already exists
            if JSONL_NAME in os.listdir(folder_path):
                print(f"Skipping {folder_path}! {JSONL_NAME} already exists.")
                continue

            time_start = time()
            try:
                jsonl_path = convert_archive(Path(folder_path))
                print(f"-- Conversion finished! Time: {time()-time_start:.2f}")
                if jsonl_path.exists():
                    print(f"Generated {os.path.join(folder_path, jsonl_path)}!")
            except Exception:
                print(f"Skipping {folder_path}, error:")
                print(traceback.format_exc())


def _populate_mongodbs():
    """
    check each jsonl file in subfolders of <path> and populate Mongo databases
    skipped if:
    * mongodb exists
    """

    print()
    print("#### ---------------------------------------------")
    print("#### Injecting the jsonl data to mongoDB")
    print("#### ---------------------------------------------")

    from optimade_launch.database import inject_data

    existing_dbs = _get_optimade_mongodbs(mongo_client)
    print("Existing MongoDBs: ", existing_dbs)

    working_dir_contents = os.listdir(DOWNLOAD_DIR)

    for folder_name in working_dir_contents:
        doi_id = folder_name
        folder_path = os.path.join(DOWNLOAD_DIR, folder_name)

        print("------------------------------------------------")
        print(doi_id)

        if _mongodb_name(doi_id) in existing_dbs:
            print(f"{doi_id} skipped as corresponding MongoDB exists!")
            continue

        if os.path.isdir(folder_path):
            if JSONL_NAME not in os.listdir(folder_path):
                print(f"{doi_id} skipped as {JSONL_NAME} is missing!")
                continue

            time_start = time()
            try:
                inject_data(
                    mongo_client,
                    os.path.join(folder_path, JSONL_NAME),
                    _mongodb_name(doi_id),
                )
                print(
                    f"-- MongoDB added: {_mongodb_name(doi_id)}!"
                    + f"Time: {time()-time_start:.2f}"
                )
            except Exception:
                print(f"Skipping {folder_path}, error:")
                print(traceback.format_exc())


def _start_containers():
    """
    Start containers for all optimade mongoDB databases (that don't already have a
    container running)
    """

    print()
    print("#### ---------------------------------------------")
    print("#### Starting containers")
    print("#### ---------------------------------------------")

    # Get list of running docker containers starting with "optimade_"
    optimade_container_names = _get_optimade_containers()
    print("Running OPTIMADE containers: ", optimade_container_names)

    existing_dbs = _get_optimade_mongodbs(mongo_client)
    print("Existing MongoDBs: ", existing_dbs)

    OLAUNCH_CONFIG_DIR = "/home/ubuntu/optimade-launch-configs"

    # Note: don't add the JSONL files here, as data was already injected separately
    # Note: specifying :latest tag for the image doesn't always give the latest version
    olaunch_config_template = """
---
image: ghcr.io/materials-consortia/optimade:0.25.3
name: {DOI_ID}
mongo_uri: mongodb://localhost:27017
db_name: {DB_NAME}
port: {PORT}
optimade_base_url: {BASE_URL}
optimade_index_base_url: {BASE_URL_INDEX}
optimade_provider:
    prefix: "mcloudarchive"
    name: "Materials Cloud Archive"
    description: "OPTIMADE provider for Materials Cloud Archive"
    homepage: {ARCHIVE_URL}
"""

    for db in existing_dbs:
        if db not in optimade_container_names:
            print(f"MongoDB {db} doesn't have a container! Starting...")

            doi_id = db.split("optimade_")[1]

            # write the optimade-launch-config.yml
            olaunch_config_path = os.path.join(OLAUNCH_CONFIG_DIR, f"{doi_id}.yaml")

            with open(olaunch_config_path, "w") as fhandle:
                fhandle.write(
                    olaunch_config_template.format(
                        DOI_ID=doi_id,
                        DB_NAME=_mongodb_name(doi_id),
                        PORT=_get_random_empty_port(),
                        BASE_URL=urljoin(BASE_URL, f"archive/{doi_id}"),
                        BASE_URL_INDEX=BASE_URL_INDEX,
                        ARCHIVE_URL=ARCHIVE_URL,
                    )
                )
                print(f"Wrote {olaunch_config_path}!")

            # Call the CLI commands
            try:
                print("---- optimade-launch profile create")
                start_time = time()
                command = (
                    f"optimade-launch profile create --config {olaunch_config_path}"
                )
                output = subprocess.check_output(command, shell=True).decode("utf-8")
                print(output)
                print(f"-- finished! Time: {time() - start_time:.2f}")

                print("---- optimade-launch server start")
                start_time = time()
                command = f"optimade-launch -vvv server start -p {doi_id}"
                output = subprocess.check_output(command, shell=True).decode("utf-8")
                print(output)
                print(f"---- finished! Time: {time() - start_time:.2f}")
            except subprocess.CalledProcessError:
                print(f"Skipping {db}, error:")
                print(traceback.format_exc())


def _update_apache_config():
    print()
    print("#### ---------------------------------------------")
    print("#### Updating apache config")
    print("#### ---------------------------------------------")
    vhosts_loc = "/etc/apache2/sites-enabled/optimade-vhosts.conf"
    with open(vhosts_loc, "w") as f:
        f.write(
            generate_apache_file.generate_vhosts(
                server_name=SERVER_NAME, index_port=3214
            )
        )
    print(f"Updated {vhosts_loc}!")
    try:
        # Use Docker Compose to start or restart the service
        subprocess.run(["sudo", "systemctl", "reload", "apache2"])
        print("Apache reloaded.")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")


def _update_index():
    print()
    print("#### ---------------------------------------------")
    print("#### Updating the index metadb")
    print("#### ---------------------------------------------")

    index = [
        {
            "id": "mc-archive-index",
            "type": "links",
            "name": "MC Archive index meta-db",
            "description": "Materials Cloud Archive index meta-database",
            "base_url": BASE_URL_INDEX,
            "homepage": ARCHIVE_URL,
            "link_type": "root",
        },
    ]

    for container_name in _get_optimade_containers():
        doi_id = container_name.split("optimade_")[1]
        entry = {
            "id": doi_id,
            "type": "links",
            "name": f"MC Archive {doi_id}",
            "description": f"OPTIMADE API serving the Materials Cloud Archive entry {doi_id}",  # noqa
            "base_url": urljoin(BASE_URL, f"/archive/{doi_id}"),
            "homepage": _get_record_metadata_processed(doi_id).get("url"),
            "link_type": "child",
            "aggregate": "ok",
        }

        index.append(entry)

    INDEX_METADB_PATH = "/home/ubuntu/index-metadb"

    with open(os.path.join(INDEX_METADB_PATH, "index_links.json"), "w") as f:
        json.dump(index, f)

    # start or restart the index metadb from the docker-compose file.
    try:
        # Use Docker Compose to start or restart the service
        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                os.path.join(INDEX_METADB_PATH, "docker-compose.yml"),
                "up",
                "-d",
                "--force-recreate",
            ]
        )
        print("Index metadb started/restarted.")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")


def _update_landing_page():
    """
    Update the landing page served at the root of the website
    """

    print()
    print("#### ---------------------------------------------")
    print("#### update landing page")
    print("#### ---------------------------------------------")

    from string import Template

    p = Path(__file__).with_name("landing_page.html.template")
    with p.open("r") as f:
        landing_page_template = Template(f.read())

    rows = []
    for container_name in _get_optimade_containers():
        doi_id = container_name.split("optimade_")[1]
        metadata = _get_record_metadata_processed(doi_id)
        rows.append([metadata.get("publication_date"), doi_id, metadata])

    # sort in ascending order by publication date
    # (entries without a date go to the end)
    rows.sort(key=lambda x: (x[0] is not None, x), reverse=True)

    db_list_html = ""
    for row in rows:
        date, doi_id, metadata = row
        base_url = urljoin(BASE_URL, f"archive/{doi_id}")
        metadata_html = ""
        if date:
            metadata_html = f"<a href='{metadata.get('url')}'>"
            metadata_html += date.strftime("%Y.%m.%d") + " "
            metadata_html += (
                f"{metadata.get('title')} (version v{metadata.get('version')})"
            )
            metadata_html += "</a>; "

        db_list_html += (
            f"<li>{metadata_html}OPTIMADE endpoint:"
            + f"<a href='{base_url}'>{base_url}</a></li>\n"
        )

    index_html_loc = "/var/www/html/index.html"
    with open(index_html_loc, "w") as f:
        f.write(
            landing_page_template.substitute(
                HTML_DB_LIST_ENTRIES=db_list_html,
                INDEX_BASE_URL=BASE_URL_INDEX,
            )
        )


@click.command()
@click.option("--skip_download", is_flag=True)
@click.option("--skip_convert", is_flag=True)
@click.option("--skip_mongo_inject", is_flag=True)
@click.option("--skip_containers", is_flag=True)
@click.option("--skip_apache", is_flag=True)
@click.option("--skip_index", is_flag=True)
@click.option("--skip_landing", is_flag=True)
def cli(
    skip_download,
    skip_convert,
    skip_mongo_inject,
    skip_containers,
    skip_apache,
    skip_index,
    skip_landing,
):
    """
    Set up the Materials Cloud Archive OPTIMADE APIs.
    """

    if not skip_download:
        _download_entries_from_archive()
    if not skip_convert:
        _convert_entries_to_jsonl()
    if not skip_mongo_inject:
        _populate_mongodbs()
    if not skip_containers:
        _start_containers()
    if not skip_apache:
        _update_apache_config()
    if not skip_index:
        _update_index()
    if not skip_landing:
        _update_landing_page()


if __name__ == "__main__":
    cli()
