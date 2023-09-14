#!/usr/bin/env python
"""Tool to launch and manage OPTIMADE instances with docker.
"""
from dataclasses import dataclass, field
from pathlib import Path

import click
import docker

from .config import Config
from optimade_launch.core import CONFIG_FOLDER
from .util import get_docker_client
from .version import __version__


def _application_config_path():
    return CONFIG_FOLDER / "config.toml"


def _load_config():
    try:
        return Config.load(_application_config_path())
    except FileNotFoundError:
        return Config()


@dataclass
class ApplicationState:
    config_path: Path = field(default_factory=_application_config_path)
    config: Config = field(default_factory=_load_config)
    docker_client: docker.DockerClient = field(default_factory=get_docker_client)

    def save_config(self):
        self.config.save(self.config_path)
