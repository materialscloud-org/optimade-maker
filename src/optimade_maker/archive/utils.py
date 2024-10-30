"""Get file URLs from Materials Cloud records"""

from __future__ import print_function

import json
import os
import tarfile
import zipfile
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import requests

requests.packages.urllib3.disable_warnings()  # type: ignore

# The api to get the metadata of the entries in the Materials Cloud Archive
DEFAULT_ARCHIVE_URL = "https://archive.materialscloud.org"


def get_all_records(base_url: str = DEFAULT_ARCHIVE_URL, limit: int = 9999) -> dict:
    """
    Get all the records in the Materials Cloud Archive.
    """
    url = base_url + f"/api/records/?sort=mostrecent&page=1&size={limit}"
    r = requests.get(url, allow_redirects=True, verify=False)
    s = json.loads(r.content.decode("utf-8"))
    records = s["hits"]["hits"]
    print("There are {} records in the Materials Cloud Archive.".format(len(records)))
    return records


def get_parsed_records() -> list:
    import os

    old_records = []
    for _, _, files in os.walk("optimade_entries"):
        for f in files:
            fs = f.rsplit(".", 1)
            old_records.append(fs[0])
    return old_records


def download_file(url: str, tmpdir: str, rename: str = "") -> str:
    """
    Downloads file
    """
    try:
        # when reading from archive or staging-invenio where the certificate is valid
        response = urlopen(url)

        filename = os.path.basename(url).split("filename=")[1]
        if len(rename) > 0:
            filename = rename

        fpath = os.path.join(tmpdir, filename)

        # Open our local file for writing
        with open(fpath, "wb") as local_file:
            r = response.read()
            local_file.write(r)

        return fpath

    except UnicodeEncodeError as e:
        print("\nUnicodeEncodeError: {} {}".format(e, url))
    except HTTPError as e:
        print("HTTP Error: {} {}".format(e.code, url))
    except URLError as e:
        print("URL Error: {} {}".format(e.reason, url))
    return ""


def extract(path: str, tmpdir: str) -> None:
    """Extract archive"""

    try:
        if tarfile.is_tarfile(path):
            with tarfile.open(path, "r:*", format=tarfile.PAX_FORMAT) as tar:
                tar.extractall(path=tmpdir)
        elif zipfile.is_zipfile(path):
            with zipfile.ZipFile(path, "r", allowZip64=True) as zip:
                zip.extractall(path=tmpdir)
    except Exception:
        # TODO: Could add check on file extension at the url level
        raise ValueError("File format not recognized. Supported: .tar, .tar.gz, .zip")
