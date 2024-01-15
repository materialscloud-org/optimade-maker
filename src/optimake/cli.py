import argparse
from pathlib import Path
from optimake.convert import convert_archive

def main():
    parser = argparse.ArgumentParser(
        prog="optimake",
        description="Use an `optimade.yaml` config to describe archived data and create a OPTIMADE JSONL file for ingestion as an OPTIMADE API."
    )
    parser.add_argument("archive_path", help="The path to the archive to ingest.")
    parser.add_argument("--jsonl-path", help="The path to write the JSONL file to.")
    args = parser.parse_args()
    jsonl_path = args.jsonl_path
    if jsonl_path:
        jsonl_path = Path(jsonl_path)
        if jsonl_path.exists():
            raise FileExistsError(f"File already exists at {jsonl_path}.")

    convert_archive(Path(args.archive_path), jsonl_path=jsonl_path)
