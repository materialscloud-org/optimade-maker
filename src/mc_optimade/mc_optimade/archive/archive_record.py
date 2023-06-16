import json
from urllib.error import HTTPError, URLError
import requests
import tqdm
import os

from mc_optimade.config import Config

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

    def __init__(self, id: int, archive_url: str = DEFAULT_ARCHIVE_URL,
                 dir="/tmp/archive") -> None:
        self.id = id
        self.archive_url = archive_url
        self.dir = os.path.join(dir, str(self.id))
        self.url = self.get_record_url(id)
        self.files = self.get_files()

    def process(self):
        if not self.is_optimade_record():
            return
        self.load_optimade_config()
        self.download_files()
        # self.convert_to_optimade()

    @property
    def metadata(self):
        return self.get_record_metadata()

    def get_record_url(self, record_id: int) -> str:
        return self.archive_url + "api/records/" + str(record_id)

    def get_file_url(self, record_id: int, filename: str, checksum: str) -> str:
        filename = filename.replace(" ", "+")
        url = self.archive_url + f"/record/file_stats?record_id={record_id}&checksum={checksum}&filename={filename}"
        return url

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
        Check if the record has a file called "optimade.yaml" or "optimade.yml".
        """
        return "optimade.yaml" in self.files or "optimade.yml" in self.files

    def download_mcloud_yaml_file(self, filename):
        """
        Try to download the optimade.yaml/yml file.
        """
        url = self.get_file_url(self.id, filename, self.files[filename])
        response = requests.get(url, allow_redirects=True)
        if not response.status_code == 200:
            raise RuntimeError("Could not download optimade.yaml/yml file.")
        return response

    def load_optimade_config(self):
        """
        Parse the optimade.yaml file.
        """
        try:
            response = self.download_mcloud_yaml_file("optimade.yaml")
        except RuntimeError:
            response = self.download_mcloud_yaml_file("optimade.yml")

        self.mc_config = Config.from_string(response.content.decode("utf-8"))

    def download_files(self, extract_files: bool = False):
        """
        Download all files from the optimade file list.
        """
        import tempfile
        from .utils import download_file, extract
        import shutil
        import os
        # remove the directory if it exists
        if os.path.exists(self.dir) and os.path.isdir(self.dir):
            shutil.rmtree(self.dir)
        os.makedirs(self.dir)
        # Extract and process files in record
        for file in tqdm.tqdm(self.mc_config.data_paths, desc="Downloading data files"):
            file_url = self.get_file_url(self.id, file, self.files[file])
            path = download_file(file_url, self.dir)
            if extract_files:
                try:
                    print("\nExtracting file ", path)
                    extract(path, self.dir)
                    print("Extracted!")
                except ValueError as e:
                    print(e)
                    print("Try to open the file and count the structures...")
