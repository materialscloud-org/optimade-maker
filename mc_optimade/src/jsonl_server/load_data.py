#!/usr/bin/env python3
import sys
from pathlib import Path

import bson.json_util
from pymongo import MongoClient

client = MongoClient("mongodb://mongo:27017")
collection = client["mc_optimade"]["structures"]
    
with open(Path(__file__).parent.joinpath("optimade.jsonl")) as handle:
    json_list = list(handle)
    
for json_str in json_list:
    id = bson.json_util.loads(json_str)['id']
    inp_data = bson.json_util.loads(json_str)['attributes']
    inp_data['id'] = id
    res = collection.insert_one(inp_data)
