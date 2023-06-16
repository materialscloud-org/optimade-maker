import pytest
from dataclasses import replace

from optimade_launch.profile import Profile

def test_profile_equality(profile):
    assert profile == profile
    assert profile != replace(profile, name="other")
    
def test_profile_init(profile):
    pass

def test_profile_dumps_loads(profile):
    assert Profile.loads(profile.name, profile.dumps()) == profile
    