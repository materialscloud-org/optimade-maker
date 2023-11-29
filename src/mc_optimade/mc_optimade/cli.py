import argparse
from pathlib import Path
from mc_optimade.convert import convert_archive

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive_path", help="The path to the archive to ingest.")
    args = parser.parse_args()
    convert_archive(Path(args.archive_path))
