import collections
from pathlib import Path
import bson.json_util
from pymongo import MongoClient
import traceback

from .core import LOGGER

BATCH_SIZE = 2000


def inject_data(client: MongoClient, filename: str, database: str):
    db = client[database]

    supported_entry_types = ["structures", "references"]

    entry_collections = {
        entry_type: db[f"{entry_type}"] for entry_type in supported_entry_types
    }
    batch = collections.defaultdict(list)

    with open(Path(__file__).parent.joinpath(filename)) as handle:
        try:
            for json_str in handle:
                entry = bson.json_util.loads(json_str)

                if "type" not in entry:
                    LOGGER.info(f"Skipping line (no type defined): {json_str}")
                    continue

                entry_type = entry["type"]

                if entry_type not in supported_entry_types:
                    LOGGER.info(f"Skipping line (type not supported): {json_str}")
                    continue

                inp_data = entry["attributes"]
                inp_data["id"] = entry["id"]

                batch[entry_type].append(inp_data)

                if len(batch[entry_type]) >= BATCH_SIZE:
                    entry_collections[entry_type].insert_many(batch[entry_type])
                    batch[entry_type] = []

            # Insert any remaining data
            for entry_type in batch:
                if len(batch[entry_type]) > 0:
                    entry_collections[entry_type].insert_many(batch[entry_type])
                    batch[entry_type] = []
        except Exception as exc:
            traceback.print_exc()
            LOGGER.error(f"Error {exc}")
