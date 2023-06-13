import pytest 

import docker
import sys

from optimade_launch.profile import Profile
from optimade_launch.config import Config
from optimade_launch.instance import OptimadeInstance, RequiresContainerInstance

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