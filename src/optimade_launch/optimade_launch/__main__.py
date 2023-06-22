from __future__ import annotations

import click
import docker
import logging
import sys
import asyncio

from .core import LOGGER
from .util import spinner
from .instance import OptimadeInstance, _BUILD_TAG
from .application_state import ApplicationState
from .profile import DEFAULT_PORT, Profile
from .version import __version__

LOGGING_LEVELS = {
    0: logging.ERROR,
    1: logging.WARN,
    2: logging.INFO,
    3: logging.DEBUG,
}  #: a mapping of `verbose` option counts to logging levels


def exception_handler(exception_type, exception, traceback):  # noqa: U100
    click.echo(f"Unexpected {exception_type.__name__}: {exception}", err=True)
    click.echo(
        "Use verbose mode `optimade-launch --verbose` to see full stack trace", err=True
    )

pass_app_state = click.make_pass_decorator(ApplicationState, ensure=True)

def with_profile(cmd):
    def callback(ctx, param, value):  # noqa: U100
        app_state = ctx.ensure_object(ApplicationState)
        name = value or app_state.config.default_profile
        LOGGER.info(f"Using profile: {name}")
        return app_state.config.get_profile(name)

    return click.option(
        "-p", "--profile", help="Select profile to use.", callback=callback
    )(cmd)

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-v",
    "--verbose",
    count=True,
    help=(
        "Increase the output verbosity of the launcher. "
        "Use '-vv' or '-vvv' for even more verbose output"
    ),
)
@pass_app_state
def cli(app_state: ApplicationState, verbose: int):
    # Use the verbosity count to determine the logging level...
    logging.basicConfig(
        level=LOGGING_LEVELS[verbose] if verbose in LOGGING_LEVELS else logging.DEBUG
    )
    if verbose > 0:
        click.secho(
            f"Verbose logging is enabled. "
            f"(LEVEL={logging.getLogger().getEffectiveLevel()})",
            fg="yellow",
            err=True,
        )

    # Hide stack trace by default.
    if verbose == 0:
        sys.excepthook = exception_handler
        
    LOGGER.info(f"Using config file: {app_state.config_path}")
    
    
@cli.command()
def version():
    """Show the version of optimade-launch."""
    click.echo(click.style(f"Optimade Launch {__version__}", bold=True))
        
async def _async_start(
    app_state, profile, restart: bool = False, force: bool = False, timeout: None | int = None, **kwargs,
):
    # get the instance
    instance = OptimadeInstance(client=app_state.docker_client, profile=profile)
    
    msg = f"Building image TAG='{_BUILD_TAG}', this may take a while..."
    
    with spinner(msg):
        instance.build()
    
    if instance.image is None:
        raise click.ClickException(
            f"Unable to build image '{_BUILD_TAG}'"
        )
        
    try:
        OptimadeInstanceStatus = instance.OptimadeInstanceStatus
        status = await instance.status()
        
        if status in (
            OptimadeInstanceStatus.DOWN,
            OptimadeInstanceStatus.CREATED,
            OptimadeInstanceStatus.EXITED,
        ):
            with spinner("Starting container..."):
                instance.start()
        
        # TODO handle restart and force
        
        else:
            raise RuntimeError(
                "Container already exists, but failed to determine its status."
            )
            
    except docker.errors.APIError as error:
        # TODO LOGGING
        raise click.ClickException("Startup failed due to an API error.") from error
    
    except Exception as error:
        raise click.ClickException(f"Unknown error: {error}.") from error
    
    else:
        if timeout:
            logging_level = logging.getLogger().getEffectiveLevel()
            try:
                with spinner("Waiting for OPTIMADE to be ready..."):
                    if logging_level == logging.DEBUG:
                        echo_logs = asyncio.create_task(instance.echo_logs())
                    await asyncio.wait_for(instance.wait_for_services(), timeout=timeout)
            except asyncio.TimeoutError:
                raise click.ClickException(
                    f"OPTIMADE instance failed to start within {timeout} seconds."
                )
            except RuntimeError as error:
                raise click.ClickException(
                    f"Failing to start OPTIMADE instance: {error} "
                    "the container output logs with "
                    f"   docker logs {instance.container.name}"
                )
            else:
                LOGGER.debug("OPTIMADE instance is ready.")
            finally:
                if logging_level == logging.DEBUG:
                    echo_logs.cancel()
                    
            LOGGER.debug("Preparing connection information...")
            url = instance.url()

            click.secho(f"OPTIMADE instance is ready at {url}", fg="green")
            
        else:
            click.secho(
                "Use `optimade-launch status` to check the OPTIMADE instance "
                "status and `optimade-launch logs` to see the container logs.",
                fg="green",
            )
      

@cli.group()
def server(*args, **kwargs):
    """Manage OPTIMADE servers."""
    pass

@server.command("start")
@click.option(
    "--timeout",
    default=120,
    show_default=True,
    help="Timeout in seconds to wait for the OPTIMADE instance to be ready.",
)
@click.option(
    "--restart",
    is_flag=True,
    help="Restart the OPTIMADE instance if it is already running.",
)
@pass_app_state
@with_profile
def start(*args, **kwargs):
    """Start an OPTIMADE instance on this host."""
    asyncio.run(_async_start(*args, **kwargs))
    
@server.command("stop")
@click.option(
    "-r",
    "--remove",
    is_flag=True,
    help="Do not only stop the container, but also remove it.",
)
@click.option(
    "--clean-db",
    is_flag=True,
    help="Also remove the database",
)
@click.option(
    "-t",
    "--timeout",
    type=click.INT,
    default=20,
    help="Wait this long for the instance to shut down.",
)
@pass_app_state
@with_profile
def stop(app_state, profile, remove: bool, clean_db: bool, timeout, **kwargs):
    """Stop an OPTIMADE instance on this host."""
    instance = OptimadeInstance(client=app_state.docker_client, profile=profile)
    status = asyncio.run(instance.status())
    if status not in (
        instance.OptimadeInstanceStatus.DOWN,
        instance.OptimadeInstanceStatus.CREATED,
        instance.OptimadeInstanceStatus.EXITED,
    ):
        with spinner("Stopping Optimade...", final="stopped."):
            instance.stop(timeout=timeout)
    if remove:
        with spinner("Removing container..."):
            instance.remove()
            
    if clean_db:
        # TODO clean db by calling the database command
        pass

    
@cli.group()
def database(*args, **kwargs):
    """Manage OPTIMADE databases."""
    pass

@database.command("health-check")
@with_profile
def health_check():
    """Check if the database is healthy."""
    pass

@database.command("import")
@with_profile
def import_database():
    """Import a database."""
    pass

@database.command("delete")
@with_profile
def delete_database():
    """Delete a database."""
    pass

@cli.group()
@with_profile
def container(*args, **kwargs):
    """Manage OPTIMADE containers."""
    pass

@container.command("create")
@with_profile
def create_container():
    """Create a container."""
    pass

@container.command("start")
@with_profile
def start_container():
    """Start a container."""
    pass

@container.command("stop")
@with_profile
def stop_container():
    """Stop a container."""
    pass
    
@cli.group()
def profile():
    """Manage Optimade profiles."""
    pass

@profile.command("list")
@pass_app_state
def list_profiles(app_state):
    """List all configured Optimade profiles.

    The default profile is shown in bold.
    """
    default_profile = app_state.config.default_profile
    click.echo(
        "\n".join(
            [
                click.style(
                    profile.name + (" *" if profile.name == default_profile else ""),
                    bold=profile.name == default_profile,
                )
                for profile in app_state.config.profiles
            ]
        )
    )
    
@profile.command("show")
@click.argument("profile")
@pass_app_state
def show_profile(app_state, profile):
    """Show an Optimade profile configuration."""
    click.echo(app_state.config.get_profile(profile).dumps(), nl=False)
    
@profile.command("set-default")
@click.argument("profile", type=click.STRING)
@pass_app_state
def set_default_profile(app_state, profile):
    """Set an Optimade profile as default."""
    try:
        app_state.config.get_profile(profile)
    except ValueError:
        raise click.ClickException(f"A profile with name '{profile}' does not exist.")
    else:
        app_state.config.default_profile = profile
        app_state.save_config()
        click.echo(f"Set default profile to '{profile}'.")
        
@profile.command("edit")
@click.argument("profile")
@pass_app_state
def edit_profile(app_state, profile):
    """Edit an Optimade profile configuration."""
    current_profile = app_state.config.get_profile(profile)
    profile_edit = click.edit(current_profile.dumps(), extension=".toml")
    if profile_edit:
        new_profile = Profile.loads(profile, profile_edit)
        if new_profile != current_profile:
            app_state.config.profiles.remove(current_profile)
            app_state.config.profiles.append(new_profile)
            app_state.save_config()
            return
    click.echo("No changes.")

        
@profile.command("create")
@click.argument("profile", type=click.STRING, required=False)
@click.option(
    "--port",
    type=click.IntRange(min=1, max=65535),
    help=(
        "Specify port on which this instance will be exposed. The default port "
        "is chosen such that it does not conflict with any currently configured "
        "profiles."
    ),
)
@click.option(
    "--mongo-uri", 
    type=click.STRING, 
    help="URL to the MongoDB instance to use.",
)
@click.option(
    "--jsonl", 
    type=click.Path(exists=True), 
    multiple=True,
    help="Path to a JSON Lines file as the source of database.",
)
@click.option(
    "--db-name",
    type=click.STRING,
    help="Name of the database to use.",
)
@click.option(
    "--config",
    type=click.Path(exists=True),
    required=False,
    help="Path to a YAML file containing the configuration.",
)
@pass_app_state
@click.pass_context
def create_profile(ctx, app_state, port: int | None, mongo_uri: str, jsonl: list, db_name, config, profile: str | None = None):
    """Add a new Optimade profile to the configuration."""
    if config:
        import yaml
        
        with open(config) as f:
            params = yaml.safe_load(f)
            profile = params["name"]
    else:
        params = {
            "name": profile,
            "mongo_uri": mongo_uri,
            "jsonl_paths": jsonl,
            "db_name": db_name or f"optimade-{profile}",
            "port": None,
        }
        
    print(params)
            
    try:
        app_state.config.get_profile(profile)
    except ValueError:
        pass
    else:
        raise click.ClickException(f"Profile with name '{profile}' already exists.")
            
    if port:
        params["port"] = port

    try:
        new_profile = Profile(
            **params,
        )
    except ValueError as error:  # invalid profile name
        raise click.ClickException(error)

    app_state.config.profiles.append(new_profile)
    app_state.save_config()
    click.echo(f"Created profile '{profile}'.")
    # if click.confirm("Do you want to edit it now?", default=True):
    #     ctx.invoke(edit_profile, profile=profile)
        
@profile.command("remove")
@click.argument("profile")
@click.option("--yes", is_flag=True, help="Do not ask for confirmation.")
@click.option("-f", "--force", is_flag=True, help="Proceed, ignoring any warnings.")
@pass_app_state
def remove_profile(app_state, profile, yes, force):
    """Remove an Optimade profile from the configuration."""
    try:
        profile = app_state.config.get_profile(profile)
    except ValueError:
        raise click.ClickException(f"Profile with name '{profile}' does not exist.")
    else:
        if not force:
            instance = OptimadeInstance(client=app_state.docker_client, profile=profile)
            status = asyncio.run(instance.status())
            if status not in (
                instance.OptimadeInstanceStatus.DOWN,
                instance.OptimadeInstanceStatus.CREATED,
                instance.OptimadeInstanceStatus.EXITED,
            ):
                raise click.ClickException(
                    f"The instance associated with profile '{profile.name}' "
                    "is still running. Use the -f/--force option to remove the "
                    "profile anyways."
                )

        if yes or click.confirm(
            f"Are you sure you want to remove profile '{profile.name}'?"
        ):
            app_state.config.profiles.remove(profile)
            app_state.save_config()
            click.echo(f"Removed profile with name '{profile.name}'.")