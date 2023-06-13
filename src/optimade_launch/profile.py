"""The profile dataclass for the optimade container instance.
"""
from __future__ import annotations

import toml
from dataclasses import dataclass, field, asdict
from docker.models.containers import Container

from .core import LOGGER

CONTAINER_PREFIX = "optimade"

DEFAULT_PORT = 8081
DEFAULT_IMAGE = "ghcr.io/materials-consortia/optimade:0.24.0"
DEFAULT_MONOGO_URL = "mongodb://localhost:27017"

DEFAULT_NAME = "default"

def _default_port() -> int:
    return DEFAULT_PORT

def _get_configured_host_port(container: Container) -> int | None:
    try:
        host_config = container.attrs["HostConfig"]
        return int(host_config["PortBindings"]["8888/tcp"][0]["HostPort"]) or None
    except (KeyError, IndexError, ValueError):
        pass
    return None

@dataclass
class Profile:
    name: str = DEFAULT_NAME
    port: int | None = field(default_factory=_default_port)
    image: str = DEFAULT_IMAGE
    mongo_url: str = DEFAULT_MONOGO_URL
    db_name: str = "optimade"
    
    def __post_init__(self):
        # TODO: Check if name is valid
        pass
    
    def container_name(self) -> str:
        return f"{CONTAINER_PREFIX}_{self.name}"
    
    def environment(self) -> dict:
        """Return the environment variables for start the container.
        """
        return {
        }
        
    def dumps(self) -> str:
        """Dump the profile to a TOML string.
        """
        return toml.dumps({k: v for k, v in asdict(self).items() if k != "name"})

    @classmethod
    def loads(cls, name: str, s: str) -> Profile:
        params = toml.loads(s)
        return cls(name=name, **params)