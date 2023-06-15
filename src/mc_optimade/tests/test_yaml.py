from pathlib import Path
from mc_optimade import Config
import pytest

EXAMPLE_YAMLS = (Path(__file__).parent.parent / "examples").glob("*/optimade.yaml")

@pytest.mark.parametrize("path", EXAMPLE_YAMLS)
def test_example_yaml(path):
    assert Config.from_file(path)

