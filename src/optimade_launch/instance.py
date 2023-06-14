from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
import asyncio
from time import time

import docker 
from docker.models.containers import Container
from typing import Any, AsyncGenerator, Generator

import pymongo
from pymongo.errors import ServerSelectionTimeoutError

from .core import LOGGER
from .profile import Profile
from .database import inject_data

def _get_host_ports(container: Container) -> Generator[int, None, None]:
    try:
        ports = container.attrs["NetworkSettings"]["Ports"]
        yield from (int(i["HostPort"]) for i in ports["5000/tcp"])
    except KeyError:
        pass


class FailedToWaitForServices(RuntimeError):
    pass


class RequiresContainerInstance(RuntimeError):
    """Raised when trying to perform operation that requires a container instance."""


class NoHostPortAssigned(RuntimeError):
    """Raised when then trying to obtain the instance URL, but there is not host port."""



@dataclass
class OptimadeInstance:
    class OptimadeInstanceStatus(Enum):
        UNKNOWN = auto()
        CREATED = auto()
        DOWN = auto()
        UP = auto()
        EXITED = auto()
        STARTING = auto()
        
    client: docker.DockerClient
    profile: Profile
    _image: docker.models.images.Image = None
    _container: Container = None
    _protocol: str = "http"
    
    def _get_image(self) -> docker.models.images.Image | None:
        try:
            return self.client.images.get(self.profile.image)
        except docker.errors.ImageNotFound:
            return None

    def _get_container(self) -> Container | None:
        try:
            return self.client.containers.get(self.profile.container_name())
        except docker.errors.NotFound:
            return None

    def __post_init__(self) -> None:
        self._image = self._get_image()
        self._container = self._get_container()
        
    @property
    def image(self) -> docker.models.images.Image | None:
        return self._image

    @property
    def container(self) -> Container | None:
        if self._container is None:
            self._container = self._get_container()
        return self._container

    def _requires_container(self) -> Container:
        container = self.container
        if container is None:
            raise RequiresContainerInstance
        return container
    
    def pull(self) -> docker.models.images.Image | None:
        try:
            image = self.client.images.pull(self.profile.image)
            LOGGER.info(f"Pulled image: {image}")
            self._image = image
            return image
        except docker.errors.NotFound:
            LOGGER.warning(f"Unable to pull image: {self.profile.image}")
            return None
        
    def _mongo_check(self) -> pymongo.MongoClient:
        # check mongodb can be connected to
        # mongo_client = pymongo.MongoClient(self.profile.mongo_uri, serverSelectionTimeoutMS=500)
        mongo_uri = f"{self.profile.mongo_uri}/?serverSelectionTimeoutMS=500"
        client = pymongo.MongoClient(mongo_uri)
        try:
            # Wait for the connection to be established within a timeout of 5 seconds
            client.server_info()
            LOGGER.info("Connected to MongoDB is ready.")
        except ServerSelectionTimeoutError:
            LOGGER.info("Connection timeout occurred. Connection is not ready.")
            raise
        else:
            return client
        
    def _inject_data(self) -> None:
        """Inject data to mongodb."""
        # check mongodb can be connected to
        client = self._mongo_check()
        
        # Inject data to mongodb
        for jsonl_path in self.profile.jsonl_paths:
            inject_data(client, jsonl_path, self.profile.db_name)
            LOGGER.info(f"Injected data from {jsonl_path} to MongoDB.")
                
    def _remove_data(self) -> None:
        """remove the database."""
        client = self._mongo_check()
        
        client.drop_database(self.profile.db_name)
            
    def create(self) -> Container:
        """Create a container instance from profile.
        """
        # Inject data to mongodb
        self._inject_data()
        
        # Create container
        assert self._container is None
        self._container = self.client.containers.create(
            image=(self.image or self.pull()),
            name=self.profile.container_name(),
            environment=self.profile.environment(),
            ports={"5000/tcp": self.profile.port},
        )
        return self._container
    
    def recreate(self) -> None:
        self._requires_container()
        assert self.container is not None
        self.remove()
        self.create()
        
    def start(self) -> None:
        # TODO: check mongodb can be connected to
        LOGGER.info(f"Starting container '{self.profile.container_name()}'...")
        (self.container or self.create()).start()
        assert self.container is not None
        LOGGER.info(f"Started container: {self.container.name} ({self.container.id}).")
        self._run_post_start()
        
    def stop(self, timeout: float | None = None) -> None:
        self._requires_container()
        assert self.container is not None
        
        try:
            self.container.stop(timeout=timeout)
        except AttributeError:
            raise RuntimeError("no container.")

    def restart(self) -> None:
        self._requires_container()
        assert self.container is not None
        self.container.restart()
        self._run_post_start()
        
    def _run_post_start(self) -> None:
        assert self.container is not None

        # Do someting?
        
    def remove(self, data: bool = False) -> None:
        # Remove contanier
        if self.container:
            self.container.remove()
            self._container = None
            
        if data:
            # Remove data from mongodb
            self._remove_data()
        
    def logs(
        self, stream: bool = False, follow: bool = False
    ) -> docker.types.daemon.CancellableStream | str:
        if self.container is None:
            raise RuntimeError("Instance was not created.")
        return self.container.logs(stream=stream, follow=follow)
        
    def host_ports(self) -> list[int]:
        self._requires_container()
        assert self.container is not None
        self.container.reload()
        return list(_get_host_ports(self.container))
    
    @staticmethod
    async def _host_port_assigned(container: Container) -> None:
        LOGGER.debug("Waiting for host port to be assigned...")
        while True:
            container.reload()
            if any(_get_host_ports(container)):
                LOGGER.debug("Host port assigned.")
                break
            await asyncio.sleep(1)
    
    async def status(self, timeout: float | None = 5.0) -> OptimadeInstanceStatus:
        if self.container:
            self.container.reload()
            await asyncio.sleep(0)
            if self.container.status == "running":
                try:
                    await asyncio.wait_for(self.wait_for_services(), timeout=timeout)
                except asyncio.TimeoutError:
                    return self.OptimadeInstanceStatus.STARTING
                except RuntimeError:
                    return self.OptimadeInstanceStatus.UNKNOWN
                else:
                    return self.OptimadeInstanceStatus.UP
            elif self.container.status == "created":
                return self.OptimadeInstanceStatus.CREATED
            elif self.container and self.container.status == "exited":
                return self.OptimadeInstanceStatus.EXITED
        return self.OptimadeInstanceStatus.DOWN
    
    async def wait_for_services(self) -> None:
        container = self._requires_container()
        LOGGER.info(f"Waiting for services to come up ({container.id})...")
        start = time()
        _ = await asyncio.gather(
            self._host_port_assigned(container),
        )
        LOGGER.info(
            f"Services came up after {time() - start:.1f} seconds ({container.id})."
        )

    def url(self) -> str:
        self._requires_container()
        assert self.container is not None
        self.container.reload()
        host_ports = list(_get_host_ports(self.container))
        if len(host_ports) > 0:
            return (
                f"{self._protocol}://localhost:{host_ports[0]}/"
            )
        else:
            raise NoHostPortAssigned(self.container.id)
        
    
        
    