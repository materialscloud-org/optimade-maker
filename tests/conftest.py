import pytest 

from optimade_launch.profile import Profile
from optimade_launch.config import Config

@pytest.fixture(scope="class")
def profile(config):
    return Profile()

@pytest.fixture(scope="class")
def config():
    return Config()
