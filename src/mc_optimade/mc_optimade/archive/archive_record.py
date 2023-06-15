import json
from urllib.error import HTTPError, URLError

import requests
from utils import get_file_url, get_record_url, parse_optimade_config


class ArchiveRecord:
    """An class for Materials Cloud Archive record.
    The class have the following methods:
    1. get the url of a record by its id
    2. get the metadata of a record by request the url
    3. check if the record has a config file called "optimade.yaml"
    4. if so, parse the config file, get the file list to be download.
    5. download the files in the file list
    6. convert the structure to OPTIMADE format

    """

    def __init__(self, id: int) -> None:
        self.id = id
        self.url = get_record_url(id)
        self.files = self.get_files()

    def process(self):
        if not self.is_optimade_record():
            return
        self.parse_optimade_config()
        self.download_files()
        self.convert_to_optimade()

    @property
    def metadata(self):
        return self.get_record_metadata()

    def get_record_metadata(self):
        """
        Get the metadata of a record by request the url.
        """
        try:
            r = requests.get(self.url, allow_redirects=True, verify=False)
            s = json.loads(r.content.decode("utf-8"))
            return s["metadata"]
        except HTTPError as e:
            print("The server couldn't fulfill the request.")
            print("Error code: ", e.code)
        except URLError as e:
            print("We failed to reach a server.")
            print("Reason: ", e.reason)

    def get_files(self):
        """
        Get the file list of a record.
        """
        files = {f["key"]: f["checksum"] for f in self.metadata["_files"]}
        return files

    def is_optimade_record(self):
        """
        Check if the record has a file called "optimade.yaml".
        """
        return "optimade.yaml" in self.files

    def parse_optimade_config(self):
        """
        Parse the optimade.yaml file.
        """
        import yaml

        url = get_file_url(self.id, "optimade.yaml", self.files["optimade.yaml"])
        response = requests.get(url, allow_redirects=True)
        content = response.content.decode("utf-8")
        content = yaml.safe_load(content)
        # step 2 phase the optimade config file
        files_to_downlaod, files_to_convert = parse_optimade_config(content)
        files_to_downlaod.append(
            "optimade.yaml",
        )
        self.optimade_config = {
            "files_to_downlaod": files_to_downlaod,
            "files_to_convert": files_to_convert,
        }

    def download_files(self):
        """
        Download all files from the optimade file list.
        """
        import tempfile

        from .utils import download_file, extract

        # Extract and process files in record
        tmpdir = tempfile.mkdtemp(dir="/tmp/archive")
        for file in self.optimade_config["files_to_downlaod"]:
            file_url = get_file_url(self.id, file, self.files[file])
            path = download_file(file_url, tmpdir)
            try:
                print("\nExtracting file ", path)
                extract(path, tmpdir)
                print("Extracted!")
            except ValueError as e:
                print(e)
                print("Try to open the file and count the structures...")

    def convert_to_optimade(self):
        """
        Convert the structure to OPTIMADE format.
        """
        pass
