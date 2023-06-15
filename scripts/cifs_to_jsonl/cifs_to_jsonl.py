#!/usr/bin/env python

import optimade
import optimade.adapters
import json
import pymatgen
import pymatgen.io.cif

from datetime import datetime, timezone
from pathlib import Path

CIFS_FOLDER = Path("./cifs")

JSONLINES_FILENAME = Path("optimade.jsonl")
if JSONLINES_FILENAME.exists():
    JSONLINES_FILENAME.unlink()


def cif_to_optimade_dict(cif_file_path):
    # generate attributes with pymatgen
    parser = pymatgen.io.cif.CifParser(cif_file_path)
    structure = parser.get_structures()[0]
    optimade_sra_pymg = optimade.adapters.structures.pymatgen.from_pymatgen(structure)
    attributes_dict = optimade_sra_pymg.dict()
    
    timestr = datetime.now(timezone.utc).isoformat(timespec='seconds').replace("+00:00", "Z")
    attributes_dict["last_modified"] = timestr
    
    return {
    "id": cif_file_path.name,
    "type": "structures",
    "links": None,
    "meta": None,
    "relationships": None,
    "attributes": attributes_dict
}

with open(JSONLINES_FILENAME, "w") as f:

    #### 1. write header
    special_header = {"x-optimade": {"meta": {"api_version": "1.1.0"}}}
    json.dump(special_header, f)
    f.write("\n")

    #### 2. json dump for every cif file
    for cif_path in CIFS_FOLDER.iterdir():
        if cif_path.suffix == ".cif":
            json.dump(cif_to_optimade_dict(cif_path), f)
            f.write("\n")

