from dataclasses import replace

import pytest

from optimade_launch.config import Config

CONFIGS = {
    "2023.1000": """
        default_profile = "default"
        version = "2023.1000"

        [profiles.default]
        port = 8081
        image = "ghcr.io/materials-consortia/optimade:0.24.0"
        """
}


def test_config_init(config):
    pass    

def test_config_equality(config):
    assert config == config
    assert config != replace(config, default_profile="other")
    
def test_config_dumps_loads(config):
    assert config == Config.loads(config.dumps())
    
@pytest.mark.parametrize("safe", [True, False])
def test_config_save(tmp_path, config, safe):
    config.save(tmp_path / "config.json", safe=safe)
    assert Config.load(tmp_path / "config.json") == config
    
@pytest.mark.parametrize("config_version", list(CONFIGS))
def test_config_loads_valid_configs(config_version):
    Config.loads(CONFIGS[config_version])
