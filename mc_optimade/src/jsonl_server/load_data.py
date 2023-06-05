#!/usr/bin/env python3
import sys
from pathlib import Path

import bson.json_util
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
collection = client["mc_optimade"]["structures"]

with open(Path(__file__).parent.joinpath("test_structures_mongo.json")) as handle:
    data = bson.json_util.loads(handle.read())

try:
    print(f"Inserting {len(data)} structures into {collection.full_name}")
    collection.insert_many(data, ordered=False)
except Exception as exc:  # pylint: disable=broad-except
    print("An error occurred!")
    sys.exit(exc)
else:
    print("Done!")
