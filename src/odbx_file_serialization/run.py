import json
from pathlib import Path

from optimade.client import OptimadeClient

JSONLINES_FILENAME = Path("optimade_odbx.jsonl")
if JSONLINES_FILENAME.exists():
    JSONLINES_FILENAME.unlink()


def write_jsonl_file(_, results):
    with open("optimade_odbx.jsonl", "a") as f:
        if isinstance(results["data"], list):
            for data in results["data"]:
                json.dump(data, f)
                f.write("\n")
        else:
            json.dump(results["data"], f)
            f.write("\n")

# first write the header

with open(JSONLINES_FILENAME, "w") as f:
    special_header = {"x-optimade": {"meta": {"api_version": "1.1.0"}}}
    json.dump(special_header, f)
    f.write("\n")

client = OptimadeClient(base_urls="https://dcgat.odbx.science", callbacks=[write_jsonl_file], silent=False)
client.get(endpoint="info")
client.get(endpoint="info/structures")
client.get(endpoint="info/references")
client.get(endpoint="structures")
client.get(endpoint="references")
