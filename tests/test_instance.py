import pytest

from optimade_launch.profile import Profile
from dataclasses import replace
from optimade_launch.instance import RequiresContainerInstance, OptimadeInstance
import re

from pymongo import MongoClient

from pytest_mock_resources import create_mongo_fixture

mongo = create_mongo_fixture()

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
        
# def test_create_custom_connection(mongo):
#     print(mongo.pmr_credentials.as_mongo_kwargs())
#     client = MongoClient(**mongo.pmr_credentials.as_mongo_kwargs())
        
# @pytest.mark.asyncio
# async def test_instance_with_inject_data():
#     profile = Profile(port=8981, jsonl_paths=["_static/optimade.jsonl"])
#     instance = OptimadeInstance(profile=profile)
    
#     assert await instance.status() is instance.OptimadeInstanceStatus.DOWN
#     instance.create()
    
#     # Check the data is in the database
#     mongo_client = pymongo.MongoClient(profile.mongo_uri, connect=True)
#     db = mongo_client[profile.mongo_database]
#     collection = db["structures"]
#     count = collection.count_documents({})
#     assert count > 3
    
    ## make sure the teardown the database.
        
# start a instance and test real actions
# @pytest.mark.usefixtures("started_instance")
# class TestsAgainstStartedInstance:
    
#     @pytest.mark.asyncio
#     async def test_instance_status(self, started_instance):
#         assert (
#             await started_instance.status()
#             is started_instance.OptimadeInstanceStatus.UP
#         )
        
#     def test_instance_url(self, started_instance):
#         assert re.match(
#             r"http:\/\/localhost:\d+\/", started_instance.url()
#         )
    
#     def test_instance_host_ports(self, started_instance):
#         assert len(started_instance.host_ports()) > 0
        