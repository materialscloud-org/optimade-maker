import pytest 
import pytest_asyncio

import asyncio

import docker
import sys
from functools import partial
from typing import Iterator

from optimade_launch.profile import Profile
from optimade_launch.config import Config
from optimade_launch.instance import OptimadeInstance, RequiresContainerInstance

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

@pytest.fixture(scope="class")
def profile(config):
    return Profile()

@pytest.fixture(scope="class")
def config():
    return Config()

@pytest.fixture(scope="class")
def instance(docker_client, profile):
    instance = OptimadeInstance(docker_client, profile=profile)
    yield instance
    
    # TODO create a volume for the database and remove it when tearing down
    def remove_db_volume():
        pass
    
    for op in (
        instance.stop,
        partial(instance.remove, data=True),
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
            

@pytest_asyncio.fixture(scope="class")
async def started_instance(instance):
    instance.create()
    assert instance.container is not None
    assert await instance.status() is instance.OptimadeInstanceStatus.CREATED
    instance.start()
    await asyncio.wait_for(instance.wait_for_services(), timeout=30)
    assert (
        await asyncio.wait_for(instance.status(), timeout=10)
        is instance.OptimadeInstanceStatus.UP
    )
    yield instance
