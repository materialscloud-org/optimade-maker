import pytest

from optimade_launch.profile import Profile

@pytest.mark.asyncio
async def test_instance_init(instance):
    assert await instance.status() is instance.OptimadeInstanceStatus.DOWN