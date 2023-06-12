#!/usr/bin/env python3
import sys
from pathlib import Path
import tqdm
import sys

import bson.json_util
from pymongo import MongoClient

# client = MongoClient("mongodb://mongo:27017") # when run from docker-compose
client = MongoClient("mongodb://localhost:27017")

total_lines = 10136
progress_bar = tqdm.tqdm(total=total_lines, desc="Loading data")
batch_size = 2000

def main():
    
    db_name = sys.argv[1]
    jsonl_file = sys.argv[2]
    
    collection = client[db_name]["structures"]
        
    with open(Path(__file__).parent.joinpath(jsonl_file)) as handle:
        batch = []
        for json_str in handle:  
            try:
                id = bson.json_util.loads(json_str)['id']
                inp_data = bson.json_util.loads(json_str)['attributes']
                inp_data['id'] = id
                progress_bar.update(1)
                # Append the data to the batch
                batch.append(inp_data)
            except:
                print("Error in json_str: ", json_str)
                continue

            if len(batch) >= batch_size:
                collection.insert_many(batch)
                batch = []
                
            # res = collection.insert_one(inp_data)
            # progress_bar.update(batch_size)

    progress_bar.close()

if __name__ == "__main__":
    main()
