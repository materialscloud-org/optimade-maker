#!/usr/bin/env python3
import sys
from pathlib import Path
import random
import string
import collections
import tqdm
import sys

import bson.json_util
from pymongo import MongoClient

# client = MongoClient("mongodb://mongo:27017") # when run from docker-compose
client = MongoClient("mongodb://localhost:27017", connect=True)

total_lines = 5
# progress_bar = tqdm.tqdm(total=total_lines, desc="Loading data")
batch_size = 2000

def main():
    
    db_name = sys.argv[1]
    jsonl_file = sys.argv[2]

    load_jsonl(jsonl_file, db_name, "".join(random.choices(string.ascii_lowercase, k=4)))

def load_jsonl(filename, database, prefix):

    db = client[database]
   
    entry_collections = {entry_type: db[f"{prefix}-{entry_type}"] for entry_type in ("structures", "references")}
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

            if len(batch[type]) >= batch_size:
                entry_collections[type].insert_many(batch[type])
                batch[type] = []

        # Insert any remaining data
        for entry_type in batch:
            entry_collections[entry_type].insert_many(batch[entry_type])
            batch[entry_type] = []

    # progress_bar.close()

if __name__ == "__main__":
    main()
