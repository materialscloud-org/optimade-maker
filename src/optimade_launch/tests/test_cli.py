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
    
def test_create_with_all_parameters(tmp_path_factory):
    # Create new-profile with all valid parameters
    runner: CliRunner = CliRunner()

    tmp1 = tmp_path_factory.mktemp("tmp1.jsonl")
    tmp2 = tmp_path_factory.mktemp("tmp2.jsonl")
    # Create new-profile
    result: Result = runner.invoke(
        cli.cli, ["profile", "create", "new-profile", "--port", "8999", "--mongo-uri", "mongodb://localhost:27017", "--jsonl", str(tmp1), "--jsonl", str(tmp2), "--db-name", "optimade-test"], input="n\n"
    )
    assert result.exit_code == 0
    assert "Created profile 'new-profile'." in result.output
    
    runner: CliRunner = CliRunner()
    result: Result = runner.invoke(cli.cli, ["profile", "show", "new-profile"])
    assert Profile.loads("default", result.output) == Profile(port=8999, mongo_uri="mongodb://localhost:27017", jsonl_paths=[str(tmp1), str(tmp2)], db_name="optimade-test")
    
    # Remove new-profile
    result: Result = runner.invoke(
        cli.cli, ["profile", "remove", "new-profile"], input="y\n"
    )
    assert result.exit_code == 0
    result: Result = runner.invoke(cli.cli, ["profile", "list"])
    assert "new-profile" not in result.output
    
def test_create_with_config(static_dir):
    runner: CliRunner = CliRunner()
    
    config_file = static_dir / "config.yaml"
    result: Result = runner.invoke(
        cli.cli, ["profile", "create", "--config", str(config_file)], input="n\n"
    )
    assert result.exit_code == 0
    
    # show profile
    result: Result = runner.invoke(cli.cli, ["profile", "show", "te-st"])
    assert result.exit_code == 0
    assert "te-st" in result.output
    assert "port" not in result.output
    
    # Remove new-profile
    result: Result = runner.invoke(
        cli.cli, ["profile", "remove", "te-st"], input="y\n"
    )
    assert result.exit_code == 0
    result: Result = runner.invoke(cli.cli, ["profile", "list"])
    assert "te-st" not in result.output
    