"""The profile dataclass for the optimade container instance.
"""
from __future__ import annotations

import toml
import sys
from dataclasses import dataclass, field, asdict
from docker.models.containers import Container

from .core import LOGGER

CONTAINER_PREFIX = "optimade"

DEFAULT_PORT = 8081
DEFAULT_IMAGE = "ghcr.io/materials-consortia/optimade:0.24.0"
DEFAULT_MONGO_URI = "mongodb://127.0.0.1:27017"

DEFAULT_NAME = "default"

def _default_port() -> int:
    return DEFAULT_PORT

def _get_configured_host_port(container: Container) -> int | None:
    try:
        host_config = container.attrs["HostConfig"]
        return int(host_config["PortBindings"]["8081/tcp"][0]["HostPort"]) or None
    except (KeyError, IndexError, ValueError):
        pass
    return None

@dataclass
class Profile:
    name: str = DEFAULT_NAME
    port: int | None = field(default_factory=_default_port)
    image: str = DEFAULT_IMAGE
    jsonl_paths: list[str] = field(default_factory=lambda: [])
    mongo_uri: str = DEFAULT_MONGO_URI
    db_name: str = "optimade"
    
    def __post_init__(self):
        # TODO: Check if name is valid
        pass
    
    def container_name(self) -> str:
        return f"{CONTAINER_PREFIX}_{self.name}"
    
    def environment(self) -> dict:
        """Return the environment variables for start the container.
        """
        if "localhost" in self.mongo_uri:
            self.mongo_uri = self.mongo_uri.replace("localhost", "host.docker.internal")
        if "127.0.0.1" in self.mongo_uri:
            self.mongo_uri = self.mongo_uri.replace("127.0.0.1", "host.docker.internal")
                
        return {
            "OPTIMADE_CONFIG_FILE": None,
            "optimade_insert_test_data": False,
            "optimade_database_backend": "mongodb",
            "optimade_mongo_uri": self.mongo_uri,
            "optimade_mongo_database": self.db_name,
            "optimade_structures_collection": "structures",
            "optimade_page_limit": 25,
            "optimade_page_limit_max": 100,
            "optimade_base_url": f"http://localhost:{self.port}", # ??
            "optimade_index_base_url": f"http://localhost:{self.port}", # ??
            "optimade_provider": "{\"prefix\":\"myorg\",\"name\":\"Materials Cloud Archive\",\"description\":\"Short description for My Organization\",\"homepage\":\"https://example.org\"}",
        }
        
    def dumps(self) -> str:
        """Dump the profile to a TOML string.
        """
        return toml.dumps({k: v for k, v in asdict(self).items() if k != "name"})

    @classmethod
    def loads(cls, name: str, s: str) -> Profile:
        params = toml.loads(s)
        return cls(name=name, **params)