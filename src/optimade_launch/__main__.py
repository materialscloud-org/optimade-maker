from __future__ import annotations

import click
import docker
import logging
import sys
import asyncio

from .core import LOGGER
from .util import spinner
from .instance import OptimadeInstance
from .application_state import ApplicationState

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
        
async def _async_start(
    app_state, profile, restart: bool = False, force: bool = False, timeout: None | int = None, **kwargs,
):
    # get the instance
    instance = OptimadeInstance(client=app_state.docker_client, profile=profile)
    
    msg = f"Downloading image '{instance.profile.image}, this may take a while..."
    
    with spinner(msg):
        instance.pull()
    
    if instance.image is None:
        raise click.ClickException(
            f"Unable to pull image '{instance.profile.image}'"
        )
        
    try:
        InstanceStatus = instance.InstanceStatus
        status = await instance.get_status()
        
        if status in (
            InstanceStatus.DOWN,
            InstanceStatus.CREATED,
            InstanceStatus.EXITED,
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
                    await asyncio.wait_for(instance.wait_for_ready(), timeout=timeout)
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
            url = instance.get_url()
            host_port = instance.get_host_port()
            
            click.secho(f"OPTIMADE instance is ready at {url}:{host_port}", fg="green")
            
            assert len(host_port) > 0, "No host port found"
            
        else:
            click.secho(
                "Use `optimade-launch status` to check the OPTIMADE instance "
                "status and `optimade-launch logs` to see the container logs.",
                fg="green",
            )
            
@cli.command()
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
    asyncio.run(_async_start(*args, **kwargs))