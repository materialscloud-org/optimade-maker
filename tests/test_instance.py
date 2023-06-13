import pytest

from optimade_launch.profile import Profile
from dataclasses import replace

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
