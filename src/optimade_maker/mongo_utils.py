import json
from collections import defaultdict
from pathlib import Path

import bson

from optimade_maker.logger import LOGGER


def populate_mongodb_from_jsonl(
    jsonl_path: Path, mongo_db, replace_prefix: str | None = None
) -> None:
    """Insert OPTIMADE JSON lines data into the database.

    Arguments:
        jsonl_path: Path to the JSON lines file.
        mongo_db: MongoDB database
        replace_prefix: replace custom provider prefixes with this.
    """

    from .serve import replace_provider_prefix

    batch = defaultdict(list)
    batch_size: int = 1000

    bad_rows: int = 0
    good_rows: int = 0
    with open(jsonl_path) as handle:
        header = handle.readline()
        header_jsonl = json.loads(header)
        assert header_jsonl.get("x-optimade"), (
            "No x-optimade header, not sure if this is a JSONL file"
        )

        for line_no, json_str in enumerate(handle):
            try:
                if json_str.strip():
                    entry = bson.json_util.loads(json_str)
                else:
                    LOGGER.warning("Could not read any data from L%s", line_no)
                    bad_rows += 1
                    continue
            except json.JSONDecodeError:
                LOGGER.warning("Could not read entry L%s JSON: '%s'", line_no, json_str)
                bad_rows += 1
                continue
            try:
                id = entry.get("id", None)
                _type = entry.get("type", None)
                if id is None or _type == "info":
                    # assume this is an info endpoint for pre-1.2
                    continue

                inp_data = {}
                if replace_prefix:
                    for key, val in entry["attributes"].items():
                        if key.startswith("_"):
                            inp_data[replace_provider_prefix(key, replace_prefix)] = val
                        else:
                            inp_data[key] = val
                else:
                    inp_data = entry["attributes"]
                inp_data["id"] = id
                if "relationships" in entry:
                    inp_data["relationships"] = entry["relationships"]
                if "links" in entry:
                    inp_data["links"] = entry["links"]

                # Append the data to the batch
                batch[_type].append(inp_data)
            except Exception as exc:
                LOGGER.warning(f"Error with entry at L{line_no} -- {entry} -- {exc}")
                bad_rows += 1
                continue

            if len(batch[_type]) >= batch_size:
                mongo_db[_type].insert_many(batch[_type])
                batch[_type] = []

            good_rows += 1

        # Insert any remaining data
        for entry_type in batch:
            mongo_db[entry_type].insert_many(batch[entry_type])
            batch[entry_type] = []

        if bad_rows:
            LOGGER.info(f"Could not read {bad_rows} rows from the JSONL file")
        LOGGER.info(f"Inserted {good_rows} rows from the JSONL file")
