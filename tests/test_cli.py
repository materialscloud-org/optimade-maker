import logging
from dataclasses import replace

import docker
import pytest
from click.testing import CliRunner, Result

import optimade_launch.__main__ as cli
from optimade_launch import __version__
from optimade_launch.profile import Profile

def test_version_displays_library_version():
    """Test that the CLI displays the library version.
    """
    runner: CliRunner = CliRunner()
    result: Result = runner.invoke(cli.cli, ["version"])
    assert __version__ in result.output.strip(), "Version number should match library version."
    assert "Optimade Launch" in result.output.strip()
    
def test_list_profiles():
    runner: CliRunner = CliRunner()
    result: Result = runner.invoke(cli.cli, ["profile", "list"])
    assert "default" in result.output.strip()

def test_show_profile():
    runner: CliRunner = CliRunner()
    result: Result = runner.invoke(cli.cli, ["profile", "show", "default"])
    assert Profile.loads("default", result.output) == Profile()

def test_change_default_profile():
    runner: CliRunner = CliRunner()
    result: Result = runner.invoke(cli.cli, ["profile", "set-default", "default"])
    assert result.exit_code == 0
    result: Result = runner.invoke(
        cli.cli, ["profile", "set-default", "does-not-exist"]
    )
    assert result.exit_code == 1
    assert "does not exist" in result.output
    
def test_create_remove_profile():
    runner: CliRunner = CliRunner()

    # Create new-profile
    result: Result = runner.invoke(
        cli.cli, ["profile", "create", "new-profile"], input="n\n"
    )
    assert result.exit_code == 0
    assert "Created profile 'new-profile'." in result.output

    # Check that new-profile exists
    result: Result = runner.invoke(cli.cli, ["profile", "list"])
    assert "new-profile" in result.output
    result: Result = runner.invoke(cli.cli, ["profile", "show", "new-profile"])
    assert result.exit_code == 0

    # Try add another profile with the same name (should fail)
    result: Result = runner.invoke(
        cli.cli, ["profile", "create", "new-profile"], input="n\n"
    )
    assert result.exit_code == 1
    assert "Profile with name 'new-profile' already exists." in result.output

    # Try make new profile default
    result: Result = runner.invoke(cli.cli, ["profile", "set-default", "new-profile"])
    assert result.exit_code == 0
    assert "Set default profile to 'new-profile'." in result.output
    # Reset default profile
    result: Result = runner.invoke(cli.cli, ["profile", "set-default", "default"])
    assert result.exit_code == 0
    assert "Set default profile to 'default'." in result.output

    # Remove new-profile
    result: Result = runner.invoke(
        cli.cli, ["profile", "remove", "new-profile"], input="y\n"
    )
    assert result.exit_code == 0
    result: Result = runner.invoke(cli.cli, ["profile", "list"])
    assert "new-profile" not in result.output

    # Remove new-profile (again – should fail)
    result: Result = runner.invoke(
        cli.cli, ["profile", "remove", "new-profile"], input="y\n"
    )
    assert result.exit_code == 1
    assert "Profile with name 'new-profile' does not exist." in result.output