import pytest

from optimade_launch.profile import Profile
from dataclasses import replace
from optimade_launch.instance import RequiresContainerInstance
import re

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

@pytest.mark.asyncio
async def test_instance_profile_detection(instance):
    assert await instance.status() is instance.OptimadeInstanceStatus.DOWN
    instance.create()
    assert await instance.status() is instance.OptimadeInstanceStatus.CREATED
    # TODO create a profile from container
    # assert instance.profile == Profile.from_container(instance.container)

def test_instance_url_before_start(instance):
    with pytest.raises(RequiresContainerInstance):
        instance.url()
        
# start a instance and test real actions
@pytest.mark.asyncio
@pytest.mark.usefixtures("started_instance")
class TestsAgainstStartedInstance:
    
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
        