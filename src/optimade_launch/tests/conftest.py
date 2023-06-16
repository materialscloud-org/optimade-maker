import pytest 
import pytest_asyncio

import asyncio
from pathlib import Path

import docker
import sys
from functools import partial
from typing import Iterator

from optimade_launch.profile import Profile
from optimade_launch.config import Config
from optimade_launch.instance import OptimadeInstance, RequiresContainerInstance

from pytest_mock_resources import create_mongo_fixture
import pymongo

mongo = create_mongo_fixture()

@pytest.fixture(scope="function")
def static_dir():
    return Path(__file__).parent / "_static"

# Redefine event_loop fixture to be session-scoped.
# See: https://github.com/pytest-dev/pytest-asyncio#async-fixtures
@pytest.fixture(scope="session")
def event_loop(request: "pytest.FixtureRequest") -> Iterator[asyncio.AbstractEventLoop]:
    """Create an instance of the default event loop for the whole session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def docker_client():
    try:
        yield docker.from_env()
    except docker.errors.DockerException:
        pytest.skip("docker not available")

@pytest.fixture(scope="function")
def profile(config):
    return Profile(port=8981)

@pytest.fixture(scope="function")
def config():
    return Config()

@pytest.fixture(scope="function")
def instance(docker_client, profile):
    instance = OptimadeInstance(docker_client, profile=profile)
    yield instance
    
    # TODO create a volume for the database and remove it when tearing down
    def remove_db_volume():
        pass
    
    for op in (
        instance.stop,
        partial(instance.remove, data=False),
        remove_db_volume,
    ):
        try:
            op()
        except (docker.errors.NotFound, RequiresContainerInstance):
            continue
        except (RuntimeError, docker.errors.APIError) as error:
            print(
                f"WARNING: Issue while stopping/removing instance: {error}",
                file=sys.stderr,
            )
            

@pytest_asyncio.fixture(scope="function")
async def started_instance(docker_client, monkeypatch, mongo, static_dir):    
    client = pymongo.MongoClient(**mongo.pmr_credentials.as_mongo_kwargs())
    monkeypatch.setattr(pymongo, "MongoClient", lambda *args, **kwargs: client)
    
    mongo_kwargs = mongo.pmr_credentials.as_mongo_kwargs()
    username = mongo_kwargs.pop("username")
    password = mongo_kwargs.pop("password")
    host = mongo_kwargs.pop("host")
    port = mongo_kwargs.pop("port")
    authSource = mongo_kwargs.pop("authSource")
    if host in ("localhost", "127.0.0.1"):
        host = "host.docker.internal"

    mongo_uri = f"mongodb://{username}:{password}@{host}:{port}/{authSource}"
  
    profile = Profile(
        port=8981, 
        jsonl_paths=[str(static_dir / "optimade.jsonl")], 
        mongo_uri=mongo_uri,
    )
    instance = OptimadeInstance(docker_client, profile=profile)
    
    if host in ("localhost", "127.0.0.1"):
        instance._container.update({"network_mode": "host"})
    
    instance.create(data=True)
    assert instance.container is not None
    assert await instance.status() is instance.OptimadeInstanceStatus.CREATED
    instance.start()
    await asyncio.wait_for(instance.wait_for_services(), timeout=30)
    assert (
        await asyncio.wait_for(instance.status(), timeout=10)
        is instance.OptimadeInstanceStatus.UP
    )
    yield instance
    
    for op in (
        instance.stop,
        partial(instance.remove, data=True),
    ):
        try:
            op()
        except (docker.errors.NotFound, RequiresContainerInstance):
            continue
        except (RuntimeError, docker.errors.APIError) as error:
            print(
                f"WARNING: Issue while stopping/removing instance: {error}",
                file=sys.stderr,
            )
