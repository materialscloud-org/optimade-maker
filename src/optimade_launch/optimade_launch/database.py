import collections
from pathlib import Path
import sys
import bson.json_util
from pymongo import MongoClient

BATCH_SIZE = 2000

def inject_data(client: MongoClient, filename: str, database: str):

    db = client[database]
   
    entry_collections = {entry_type: db[f"{entry_type}"] for entry_type in ("structures", "references")}
    batch = collections.defaultdict(list)
        
    with open(Path(__file__).parent.joinpath(filename)) as handle:
        header = handle.readline()

        for json_str in handle:  

            try:
                entry = bson.json_util.loads(json_str)
                id = entry['id']
                type = entry['type']
                inp_data = entry['attributes']
                inp_data['id'] = id
                # Append the data to the batch
                if type == "info":
                    continue
                batch[type].append(inp_data)
                # progress_bar.update(1)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                print(f"Error {exc} {id=}")
                continue

            if len(batch[type]) >= BATCH_SIZE:
                entry_collections[type].insert_many(batch[type])
                batch[type] = []

        # Insert any remaining data
        for entry_type in batch:
            entry_collections[entry_type].insert_many(batch[entry_type])
            batch[entry_type] = []

    # progress_bar.close()