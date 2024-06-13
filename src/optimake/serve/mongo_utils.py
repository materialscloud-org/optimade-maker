#!/usr/bin/env python3

"""
MongoDB utilities.
"""

import collections
import traceback
from datetime import datetime
from pathlib import Path

import bson.json_util
from pymongo import MongoClient

MONGO_METADB_NAME = "metadata"
INJECT_BATCH_SIZE = 2000


def mongodb_name(doi_id):
    return f"optimade_{doi_id}"


class MongoHandler:
    def __init__(self):
        self.client = MongoClient("localhost", 27017)

    def get_optimade_mongodbs(self):
        return [
            db for db in self.client.list_database_names() if db.startswith("optimade_")
        ]

    def does_record_mongodb_exist(self, doi_id):
        return mongodb_name(doi_id) in self.get_optimade_mongodbs()

    def add_record_metadata_to_mongodb(self, doi_id, data):
        collection = self.client[MONGO_METADB_NAME]["entries"]
        filter_criteria = {"doi_id": doi_id}
        data["doi_id"] = doi_id
        # Insert if not exists or update if exists
        collection.update_one(filter_criteria, {"$set": data}, upsert=True)

        # add also the parent & version
        collection = self.client[MONGO_METADB_NAME]["versioning"]
        parent_id = data["metadata"]["conceptrecid"]
        version_nr = data["metadata"]["version"]
        filter_query = {"parent_id": parent_id}
        collection.update_one(
            filter_query, {"$set": {f"versions.{version_nr}": doi_id}}, upsert=True
        )

    def get_record_metadata_processed(self, doi_id, archive_url):
        collection = self.client[MONGO_METADB_NAME]["entries"]
        filter_criteria = {"doi_id": doi_id}

        result = collection.find_one(filter_criteria)

        if result:
            mcid = result["metadata"]["mcid"]
            date_format = "%b %d, %Y, %H:%M:%S"
            return {
                "title": result["metadata"]["title"],
                "version": result["metadata"]["version"],
                "doi": result["metadata"]["doi"],
                "authors": result["metadata"]["contributors"],
                "mcid": mcid,
                "url": f"{archive_url}record/{mcid}",
                "publication_date": datetime.strptime(
                    result["metadata"]["publication_date"], date_format
                ),
            }

        return None

    def get_record_latest_version(self, doi_id):
        # get the parent id
        collection = self.client[MONGO_METADB_NAME]["entries"]
        filter_criteria = {"doi_id": doi_id}
        result = collection.find_one(filter_criteria)

        if result:
            parent_id = result["metadata"]["conceptrecid"]

            # get all records with the same parent id
            collection = self.client[MONGO_METADB_NAME]["versioning"]
            filter_criteria = {"parent_id": parent_id}
            result = collection.find_one(filter_criteria)

            last_version_num = max(int(k) for k in result["versions"].keys())
            last_version = result["versions"][str(last_version_num)]
            return last_version

        return None

    def newer_version_exists(self, doi_id):
        latest_version = self.get_record_latest_version(doi_id)
        if latest_version is None:
            return False
        if latest_version != doi_id:
            print(f"{doi_id} skipped as a newer version exists!")
            return True
        return False

    def get_version_mapping(self):
        """
        The entry versioning and endpoint choice is the following:
        each entry has a single running container serving the latest
        version, which is served at the <doi_id> of the first version.

        Example:
        Let's say an archive entry has 3 versions that have an optimade.yaml
        and the <doi_id>'s are the following:
        - v2 -> kw-y0
        - v3 -> ea-2k
        - v4 -> df-mk

        This means that the data from entry df-mk is served at the /kw-y0 endpoint.
        Additionally, redirects are added from the other doi_id subpaths.

        This function returns a dictionary that maps each doi_id to its corresponding
        endpoint, e.g.
        mapping = {
            'kw-y0': 'kw-y0',
            'ea-2k': 'kw-y0',
            'df-mk': 'kw-y0',
        }
        """
        mapping = {}
        collection = self.client[MONGO_METADB_NAME]["versioning"]
        results = collection.find()
        for res in results:
            first_version_num = min(int(k) for k in res["versions"].keys())
            first_doi_id = res["versions"][str(first_version_num)]
            for _, doi_id in res["versions"].items():
                mapping[doi_id] = first_doi_id
        return mapping

    def get_provider_fields_from_mongodb(self, doi_id):
        """
        Go through the "info" collection of the corresponding MongoDB and get the
        provider fields (custom properties)
        """
        db = self.client[mongodb_name(doi_id)]
        provider_fields = []
        if "info" in db.list_collection_names():
            # go through all "info" entries and try to find properties
            for entry in db["info"].find():
                if "properties" in entry:
                    for prop, val in entry["properties"].items():
                        # if property name starts with underscore, it's a custom one
                        if prop.startswith("_"):
                            provider_field_entry = {
                                "name": prop,
                            }
                            # add only the keys that are not None.
                            for key in ["description", "unit", "type"]:
                                if val.get(key) is not None:
                                    provider_field_entry[key] = val.get(key)
                            provider_fields.append(provider_field_entry)
        return provider_fields

    def inject_data(self, filename: str, doi_id: str):
        db = self.client[mongodb_name(doi_id)]

        supported_entry_types = ["structures", "references"]

        entry_collections = {
            entry_type: db[f"{entry_type}"] for entry_type in supported_entry_types
        }
        entry_collections["info"] = db["info"]  # all other lines from the jsonl file
        batch = collections.defaultdict(list)

        with open(Path(__file__).parent.joinpath(filename)) as handle:
            try:
                for json_str in handle:
                    entry = bson.json_util.loads(json_str)

                    if "x-optimade" in entry:
                        # skip the first line
                        continue

                    if "type" not in entry:
                        entry_collections["info"].insert_one(entry)
                        continue

                    entry_type = entry["type"]

                    if entry_type not in supported_entry_types:
                        entry_collections["info"].insert_one(entry)
                        continue

                    inp_data = entry["attributes"]
                    inp_data["id"] = entry["id"]

                    batch[entry_type].append(inp_data)

                    if len(batch[entry_type]) >= INJECT_BATCH_SIZE:
                        entry_collections[entry_type].insert_many(batch[entry_type])
                        batch[entry_type] = []

                # Insert any remaining data
                for entry_type in batch:
                    if len(batch[entry_type]) > 0:
                        entry_collections[entry_type].insert_many(batch[entry_type])
                        batch[entry_type] = []
            except Exception as exc:
                traceback.print_exc()
                print(f"Error {exc}")
