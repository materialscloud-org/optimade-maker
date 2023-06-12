#!/usr/bin/env python

import aiida
from aiida.orm import QueryBuilder
from aiida.orm import Group
from aiida.orm import Node

import optimade
import optimade.adapters
import json
import pymatgen
import pymatgen.io.cif

from datetime import datetime, timezone
from pathlib import Path


from tqdm import tqdm


aiida.load_profile("li-ion-conductors")


timestr = datetime.now(timezone.utc).isoformat(timespec='seconds').replace("+00:00", "Z")


entities=["data.core.cif.CifData.", "data.core.structure.StructureData."]

filters = {"node_type": {"or": [{"==": node_type} for node_type in entities]}}

query = QueryBuilder()
query.append(Node, filters=filters)

count = query.count()

def structuredata_to_optimade_dict(sd):
    # generate attributes with pymatgen
    structure = sd.get_pymatgen()
    optimade_sra_pymg = optimade.adapters.structures.pymatgen.from_pymatgen(structure)
    attributes_dict = optimade_sra_pymg.dict()
    
    attributes_dict["immutable_id"] = sd.uuid
    attributes_dict["last_modified"] = timestr
    
    return {
    "id": sd.uuid,
    "type": "structures",
    "links": None,
    "meta": None,
    "relationships": None,
    "attributes": attributes_dict
}


JSONLINES_FILENAME = Path("optimade.jsonl")
if JSONLINES_FILENAME.exists():
    JSONLINES_FILENAME.unlink()

with open(JSONLINES_FILENAME, "w") as f:

    #### 1. write header
    special_header = {"x-optimade": {"meta": {"api_version": "1.1.0"}}}
    json.dump(special_header, f)
    f.write("\n")

    #### 2. json dump for every structuredata
    for i, (node,) in tqdm(enumerate(query.iterall()), total=count):
        json.dump(structuredata_to_optimade_dict(node), f)
        f.write("\n")