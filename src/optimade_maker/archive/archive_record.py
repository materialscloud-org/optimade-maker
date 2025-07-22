import json
import os
from urllib.error import HTTPError, URLError

import requests

from optimade_maker.config import Config

DEFAULT_ARCHIVE_URL = "https://archive.materialscloud.org"


class ArchiveRecord:
    """An class for Materials Cloud Archive record.
    The class have the following methods:
    1. get the url of a record by its id
    2. get the metadata of a record by request the url
    3. check if the record has a config file called "optimade.yaml"
    4. if so, parse the config file, get the file list to be download.
    5. download the files in the file list
    6. convert the structure to OPTIMADE format (in another script)

    Parameters:

    id: int
        id of the record. In MC archive, on the right panel,
        "Export" --> "JSON", then find the "id" value.
    archive_url: str
        url of the archive.
    dir: str
        directory to save the downloaded files.
    """

    def __init__(self, id: int, archive_url: str = DEFAULT_ARCHIVE_URL) -> None:
        self.id = id
        self.archive_url = archive_url
        self.url = self.get_record_url(id)

        self.metadata = self.get_record_metadata()
        self.doi_id = self.get_doi_id()
        self.files_w_checksums = self.get_files_w_checksums()

        self.default_path = os.path.join("/tmp/archive", self.doi_id)

        self.optimade_config_name = self.check_optimade_config_name()

    def check_optimade_config_name(self):
        """
        Check if optimade config file exists. If it doesn't, return None
        """
        optimade_yml_name = None
        for name_candidate in ["optimade.yaml", "optimade.yml"]:
            if name_candidate in self.files_w_checksums:
                optimade_yml_name = name_candidate
                break
        return optimade_yml_name

    def process(self):
        if not self.is_optimade_record():
            return
        self.load_optimade_config()
        self.download_files()
        # self.convert_to_optimade()

    def download_optimade_files(self, path=None):
        if not self.is_optimade_record():
            return
        self.load_optimade_config()
        self.download_files(path)

    def get_record_url(self, record_id: int) -> str:
        return self.archive_url + "api/records/" + str(record_id)

    def get_file_url(self, filename: str) -> str:
        # checksum = self.files_w_checksums[filename]
        filename = filename.replace(" ", "+")
        # original version, failing for
        # https://staging-archive.materialscloud.org//record/file_stats?record_id=1412&checksum=md5:81b5fefab6bfa8e516d313b9cea39c66&filename=structures.zip
        # url = (
        #     self.archive_url
        #     + f"/record/file_stats?record_id={record_id}&checksum={checksum}&filename={filename}"
        # )
        url = self.archive_url + f"/record/file?record_id={self.id}&filename={filename}"
        return url

    def get_record_metadata(self):
        """
        Get the metadata of a record by request the url.
        """
        try:
            r = requests.get(self.url, timeout=30, allow_redirects=True, verify=False)
            s = json.loads(r.content.decode("utf-8"))
            return s["metadata"]
        except HTTPError as e:
            print("The server couldn't fulfill the request.")
            print("Error code: ", e.code)
        except URLError as e:
            print("We failed to reach a server.")
            print("Reason: ", e.reason)

    def get_doi_id(self):
        """
        Get the DOI identifier of the record, e.g.
        "10.24435/materialscloud:jq-0s" -> "jq-0s"
        "10.24435/materialscloud:2020.0040/v1" -> "2020.0040/v1"

        NOTE: the slash in the old format currently unsupported (e.g. can't make a folder,
        or docker container), but these entries any way don't contain optimade.yml, so it
        should be safe to ignore this for now.
        """
        return self.metadata["doi"].split(":")[-1]

    def get_files_w_checksums(self):
        """
        Get the file list with checksums of a record.
        """
        files = {f["key"]: f["checksum"] for f in self.metadata["_files"]}
        return files

    def is_optimade_record(self):
        """
        return if the record has the optimade config file.
        """
        return self.optimade_config_name is not None

    def download_optimade_config_file(self):
        """
        Try to download the optimade.yaml/yml file.
        """
        filename = self.optimade_config_name
        url = self.get_file_url(filename)
        response = requests.get(url, timeout=30, allow_redirects=True)
        if not response.status_code == 200:
            raise RuntimeError(f"Could not download {filename} file.")
        return response

    def load_optimade_config(self):
        """
        Download and parse the optimade.yaml/yml file.
        """
        response = self.download_optimade_config_file()
        self.mc_config = Config.from_string(response.content.decode("utf-8"))

    def download_files(self, path=None):
        """
        Download all files from the optimade file list.
        """
        import os
        import shutil

        from .utils import download_file

        if not path:
            path = self.default_path

        # remove the directory if it exists
        if os.path.exists(path) and os.path.isdir(path):
            shutil.rmtree(path)
        os.makedirs(path)

        # download optimade.yml/yaml and rename to "yml->yaml"
        file_url = self.get_file_url(self.optimade_config_name)
        download_file(file_url, path, rename="optimade.yaml")

        # download files in record
        if getattr(self.mc_config.entries, "jsonl_path", None):
            # case 1: jsonl file specified (either via `file: jsonl.gz` or `jsonl_path:`)
            if getattr(self.mc_config.entries, "file", None):
                # download `file:`, if specified
                file_url = self.get_file_url(self.mc_config.entries.file)
                download_file(file_url, path)
            else:
                # otherwise download the `jsonl_path:`
                file_url = self.get_file_url(self.mc_config.entries.jsonl_path)
                download_file(file_url, path)
        else:
            # case 2: files specified as entry_paths/property_paths
            for entry in self.mc_config.entries:
                list_of_files = [path.file for path in entry.entry_paths]
                if getattr(entry, "property_paths", None):
                    list_of_files += [path.file for path in entry.property_paths]
                for fname in list_of_files:
                    file_url = self.get_file_url(fname)
                    download_file(file_url, path)
