import importlib.util
import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest
import requests

AIIDA_AVAILABLE = bool(importlib.util.find_spec("aiida"))

EXAMPLE_ARCHIVES = (Path(__file__).parent.parent / "examples").glob("*")


def wait_for_server_to_start(url, retries=20, delay=1):
    for _ in range(retries):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return True
        except requests.ConnectionError:
            time.sleep(delay)
    return False


@pytest.mark.parametrize("archive_path", EXAMPLE_ARCHIVES, ids=lambda path: path.name)
def test_serve_example_archives(archive_path, tmp_path):
    """This test will run through all examples in the examples folder and
    attempt to serve them via the CLI. Every endpoint is checked.
    """
    if "aiida" in archive_path.name and not AIIDA_AVAILABLE:
        pytest.skip(
            "Skipping test for AiiDA archive, as it requires AiiDA to be installed."
        )
    # copy example into temporary path
    tmp_path = tmp_path / archive_path.name
    shutil.copytree(archive_path, tmp_path)

    override_config_file = "override_config.json"
    override_config = None
    if (tmp_path / override_config_file).is_file():
        with open(tmp_path / override_config_file, "r") as f:
            override_config = json.load(f)
    custom_prefix = None
    if override_config is not None:
        custom_prefix = override_config.get("provider", {}).get("prefix")

    # use an uncommon port that hopefully is unused
    port = 43486
    host = "127.0.0.1"

    # use subprocess to start the api via the cli
    command = [
        "optimake",
        "serve",
        "--host",
        str(host),
        "--port",
        str(port),
        "--write_config",
        "final_config.json",
    ]
    if override_config is not None:
        command += ["--override_config_file", override_config_file]
    command += [str(tmp_path)]
    process = subprocess.Popen(command)

    url = f"http://{host}:{port}"

    try:
        if not wait_for_server_to_start(url):
            raise RuntimeError(f"Server did not start at {url}")

        # check the landing page
        response = requests.get(url)
        assert response.status_code == 200
        assert "Available endpoints:" in response.text

        # check the info endpoints
        response = requests.get(f"{url}/info")
        assert response.status_code == 200
        response = requests.get(f"{url}/info/structures")

        props = response.json()["data"]["properties"]
        custom_prop_keys = [k for k, v in props.items() if k.startswith("_")]
        if custom_prefix is not None:
            assert all(k.startswith(f"_{custom_prefix}") for k in custom_prop_keys)

        assert response.status_code == 200
        response = requests.get(f"{url}/info/references")
        assert response.status_code == 200

        # check links and references
        response = requests.get(f"{url}/links")
        assert response.status_code == 200
        response = requests.get(f"{url}/references")
        assert response.status_code == 200

        # check structures endpoint
        response = requests.get(f"{url}/structures")
        assert response.status_code == 200
        # each example has at least 1 structure, run a basic check on it
        struct_entry = response.json()["data"][0]
        assert "type" in struct_entry
        assert struct_entry["type"] == "structures"

        props = struct_entry["attributes"]
        custom_prop_keys = [k for k in props.keys() if k.startswith("_")]
        if custom_prefix is not None:
            assert all(k.startswith(f"_{custom_prefix}") for k in custom_prop_keys)

    finally:
        process.terminate()
        process.wait()

    assert (tmp_path / "final_config.json").is_file()
