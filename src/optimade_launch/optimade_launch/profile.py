"""The profile dataclass for the optimade container instance.
"""
from __future__ import annotations

import toml
from dataclasses import dataclass, field, asdict
from docker.models.containers import Container


CONTAINER_PREFIX = "optimade"

DEFAULT_PORT = 8081
DEFAULT_IMAGE = "ghcr.io/materials-consortia/optimade:latest"
DEFAULT_MONGO_URI = "mongodb://127.0.0.1:27017"
DEFAULT_BASE_URL = "http://localhost"
DEFAULT_INDEX_BASE_URL = "http://localhost"
DEFAULT_PROVIDER = '{"prefix":"default","name":"Materials Cloud Archive","description":"Short description for My Organization","homepage":"https://example.org"}'  # noqa


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
    image: str = DEFAULT_IMAGE
    jsonl_paths: list[str] = field(default_factory=lambda: [])
    mongo_uri: str = DEFAULT_MONGO_URI
    db_name: str = "optimade"
    port: int | None = None
    unix_sock: str | None = None
    optimade_config_file: str | None = None
    optimade_base_url: str | None = None
    optimade_index_base_url: str | None = None
    optimade_provider: str | None = None
    optimade_validate_api_response: bool = False

    def __post_init__(self):
        # default port is dependent on unix_sock
        if self.port is None and self.unix_sock is None:
            self.port = _default_port()

    def container_name(self) -> str:
        return f"{CONTAINER_PREFIX}_{self.name}"

    def environment(self) -> dict:
        """Return the environment variables for start the container."""
        if "localhost" in self.mongo_uri:
            self.mongo_uri = self.mongo_uri.replace("localhost", "host.docker.internal")
        if "127.0.0.1" in self.mongo_uri:
            self.mongo_uri = self.mongo_uri.replace("127.0.0.1", "host.docker.internal")

        return {
            "optimade_config_file": self.optimade_config_file,
            "optimade_insert_test_data": False,
            "optimade_database_backend": "mongodb",
            "optimade_mongo_uri": self.mongo_uri,
            "optimade_mongo_database": self.db_name,
            "optimade_structures_collection": "structures",
            "optimade_page_limit": 25,
            "optimade_page_limit_max": 100,
            "optimade_base_url": self.optimade_base_url,
            "optimade_index_base_url": self.optimade_index_base_url,
            "optimade_provider": self.optimade_provider,
            "optimade_validate_api_response": self.optimade_validate_api_response,
        }

    def dumps(self) -> str:
        """Dump the profile to a TOML string."""
        return toml.dumps({k: v for k, v in asdict(self).items() if k != "name" and v is not None})

    @classmethod
    def loads(cls, name: str, s: str) -> Profile:
        params = toml.loads(s)
        return cls(name=name, **params)
