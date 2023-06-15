"""Get file URLs from Materials Cloud records"""
from __future__ import print_function
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
import json
import requests
import tarfile
import zipfile
import os
import requests
requests.packages.urllib3.disable_warnings()

# The api to get the metadata of the entries in the Materials Cloud Archive

def get_all_records(url):
    """
    Get all the records in the Materials Cloud Archive.
    """
    r = requests.get(url, allow_redirects=True, verify=False)
    s = json.loads(r.content.decode('utf-8'))
    recrods = s["hits"]["hits"]
    print("There are {} records in the Materials Cloud Archive.".format(len(recrods)))
    return recrods

def get_parsed_records():
    import os
    old_records = []
    for _, _, files in os.walk("optimade_entries"):
        for f in files:
            f = f.rsplit(".",1)
            old_records.append(f[0])
    return old_records

def parse_optimade_config():
    """Parse OPTIMADE config file"""
    pass

def get_record_id(doi):
    return doi.replace("10.24435/materialscloud:", "")

def get_record_url(record_id):
    api_url = 'https://archive.materialscloud.org/api/records/'
    return api_url + record_id

def get_file_url(record_id, filename, checksum):
    filename = filename.replace(" ", "+") 
    print(filename)
    return "https://archive.materialscloud.org/record/file_stats?record_id={}&checksum={}&filename={}".format(record_id, checksum, filename)

def get_file_urls_from_doi(record_id, max_size):
    json_url = get_record_url(record_id)
    
    try:
        r = requests.get(json_url, allow_redirects=True, verify=False)
        s = json.loads(r.content.decode('utf-8'))
        record_json = s["metadata"]

        files = [{'filename':f['key'], 'checksum':f['checksum']} for f in record_json['_files'] if f['size']<=max_size]
        discarded_files = [f['key'] for f in record_json['_files'] if f['size']>max_size]
        file_urls = [get_file_url(record_id, f) for f in files]

        if len(discarded_files) > 0:
            return dict(zip(file_urls, files)), dict({record_id: discarded_files})
        else:
            return dict(zip(file_urls, files)), dict()
    except HTTPError as e:
        print("HTTP Error: {} {}".format(e.code, json_url))
    except URLError as e:
        print("URL Error: {} {}".format(e.reason, json_url))


def download_file(url, tmpdir):
    """
    Downloads file
    """
    try:
        # when reading from archive or staging-invenio where the certificate is valid
        response = urlopen(url)

        filename = os.path.basename(url).split("filename=")
        fpath = os.path.join(tmpdir, filename[1])

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


def extract(path, tmpdir):
    """Extract archive"""

    try:
        if tarfile.is_tarfile(path):
            with tarfile.open(path, "r:*", format=tarfile.PAX_FORMAT) as tar:
                tar.extractall(path=tmpdir)
        elif zipfile.is_zipfile(path):
            with zipfile.ZipFile(path, "r", allowZip64=True) as zip:
                zip.extractall(path=tmpdir)
    except Exception:
        #TODO: Could add check on file extension at the url level
        raise ValueError(
            "File format not recognized. Supported: .tar, .tar.gz, .zip")
