import pytest

from optimade_launch.profile import Profile
import docker
from pathlib import PurePosixPath
from dataclasses import replace
from optimade_launch.instance import RequiresContainerInstance, OptimadeInstance
import re

from pymongo import MongoClient

@pytest.mark.asyncio
async def test_instance_init(instance):
    assert await instance.status() is instance.OptimadeInstanceStatus.DOWN
    
@pytest.mark.asyncio
async def test_instance_create_remove(instance):
    assert await instance.status() is instance.OptimadeInstanceStatus.DOWN
    instance.create()
    
    assert instance.container is not None
    assert await instance.status() is instance.OptimadeInstanceStatus.CREATED
    # The instance is automatically stopped and removed by the fixture
    # function.
    
@pytest.mark.asyncio
async def test_instance_recreate(instance):
    assert await instance.status() is instance.OptimadeInstanceStatus.DOWN
    instance.create()
    assert await instance.status() is instance.OptimadeInstanceStatus.CREATED
    instance.recreate()
    assert instance.container is not None
    assert await instance.status() is instance.OptimadeInstanceStatus.CREATED

def test_instance_url_before_start(instance):
    with pytest.raises(RequiresContainerInstance):
        instance.url()
  
def test_instance_build_container(instance):
    instance.build("optimade:test")
    assert instance.client.images.get("optimade:test") is not None

    # remove the image
    instance.client.images.remove("optimade:test")
    
def get_docker_mount(
    container: docker.models.containers.Container, destination: PurePosixPath
) -> docker.types.Mount:
    try:
        mount = [
            mount
            for mount in container.attrs["Mounts"]
            if mount["Destination"] == str(destination)
        ][0]
    except IndexError:
        raise ValueError(f"No mount point for {destination}.")
    return mount
    
@pytest.mark.asyncio
async def test_instance_create_and_check_sock(instance):
    assert await instance.status() is instance.OptimadeInstanceStatus.DOWN
    instance.create()
    
    assert "UNIX_SOCK=/tmp/test.sock" in instance._container.attrs["Config"]["Env"]
    
    mount = get_docker_mount(instance.container, PurePosixPath("/tmp"))
    assert mount["Type"] == "bind"
    assert mount["Source"] == "/tmp/optimade-sock"
        
# start a instance and test real actions
@pytest.mark.usefixtures("started_instance")
class TestsAgainstStartedInstance:
    
    @pytest.mark.asyncio
    async def test_instance_status(self, started_instance):
        assert (
            await started_instance.status()
            is started_instance.OptimadeInstanceStatus.UP
        )
        
    def test_instance_url(self, started_instance):
        assert re.match(
            r"http:\/\/localhost:\d+\/", started_instance.url()
        )
    
    def test_instance_host_ports(self, started_instance):
        assert len(started_instance.host_ports()) > 0
        
    @pytest.mark.asyncio
    async def test_instance_query(self, started_instance):
        """make a query to the instance"""
        import requests
        assert (
            await started_instance.status()
            is started_instance.OptimadeInstanceStatus.UP
        )
        
        response = requests.get(started_instance.url() + "v1/structures")
        assert response.status_code == 200
        assert response.json()["meta"]["data_available"] == 3
