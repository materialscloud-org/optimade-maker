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

    def __init__(self, id: int, archive_url: str = DEFAULT_ARCHIVE_URL) -> None:
        self.id = id
        self.archive_url = archive_url
        self.url = self.get_record_url(id)

        self.metadata = self.get_record_metadata()
        self.doi_id = self.get_doi_id()
        self.files = self.get_files()

        self.default_path = os.path.join("/tmp/archive", self.doi_id)

        self.optimade_config_name = self.check_optimade_config_name()
        
    def check_optimade_config_name(self):
        """
        Check if optimade config file exists. If it doesn't, return None
        """
        optimade_yml_name = None
        for name_candidate in ["optimade.yaml", "optimade.yml"]:
            if name_candidate in self.files:
                optimade_yml_name = name_candidate
                break
        return optimade_yml_name


    def process(self):
        if not self.is_optimade_record():
            return
        self.load_optimade_config()
        self.download_files()
        # self.convert_to_optimade()

    def download_optimade_files(self, path=None, extract_files=False):
        if not self.is_optimade_record():
            return
        self.load_optimade_config()
        self.download_files(path, extract_files=extract_files)

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

    def get_files(self):
        """
        Get the file list of a record.
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
        url = self.get_file_url(self.id, filename, self.files[filename])
        response = requests.get(url, allow_redirects=True)
        if not response.status_code == 200:
            raise RuntimeError(f"Could not download {filename} file.")
        return response

    def load_optimade_config(self):
        """
        Download and parse the optimade.yaml/yml file.
        """
        response = self.download_optimade_config_file()
        self.mc_config = Config.from_string(response.content.decode("utf-8"))

    def download_files(self, path=None, extract_files: bool = False):
        """
        Download all files from the optimade file list.
        """
        import tempfile
        from .utils import download_file, extract
        import shutil
        import os

        if not path:
            path = self.default_path

        # remove the directory if it exists
        if os.path.exists(path) and os.path.isdir(path):
            shutil.rmtree(path)
        os.makedirs(path)

        # download optimade.yml/yaml and rename to "yml->yaml"
        file_url = self.get_file_url(self.id, self.optimade_config_name, self.files[self.optimade_config_name])
        download_file(file_url, path, rename="optimade.yaml")

        # download files in record
        for entry in self.mc_config.entries:
            for entry_path in entry.entry_paths:
                fname = entry_path.file
                file_url = self.get_file_url(self.id, fname, self.files[fname])
                file_path = download_file(file_url, path)
                if extract_files:
                    try:
                        print("\nExtracting file ", file_path)
                        extract(file_path, path)
                        print("Extracted!")
                    except ValueError as e:
                        print(e)
                        print("Try to open the file and count the structures...")
