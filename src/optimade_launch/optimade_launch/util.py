import asyncio
import logging
from contextlib import contextmanager
import docker
from threading import Event, Thread, Timer
from typing import Any, AsyncGenerator, Generator, Iterable, Optional, Union

import click
import click_spinner

@contextmanager
def spinner(
    msg: Optional[str] = None, final: Optional[str] = "done.", delay: float = 0
) -> Generator[None, None, None]:
    """Display spinner only after an optional initial delay."""

    def spin() -> None:
        # Don't show spinner if verbose output is enabled
        level = logging.getLogger().getEffectiveLevel()
        show_spinner = (
            True if level == logging.NOTSET or level >= logging.ERROR else False
        )
        if msg:
            newline = not show_spinner
            click.echo(f"{msg.rstrip()} ", nl=newline, err=True)

        if show_spinner:
            with click_spinner.spinner():  # type: ignore
                stop.wait()
            click.echo(final if (completed.is_set() and msg) else " ", err=True)
        else:
            stop.wait()

    stop = Event()
    completed = Event()
    timed_spinner = Timer(delay, spin)
    timed_spinner.start()
    try:
        yield
        # Try to cancel the timer if still possible.
        timed_spinner.cancel()
        # Set the completed event since there was no exception, indicating that
        # the waited on operation completed successfully.
        completed.set()
    finally:
        stop.set()
        timed_spinner.join()
        
def get_docker_client(*args, **kwargs) -> docker.client.DockerClient:
    try:
        with spinner("Connecting to docker host...", delay=0.2):
            return docker.from_env(*args, **kwargs)
    except docker.errors.DockerException as error:
        click.secho(
            "\n".join(wrap(MSG_UNABLE_TO_COMMUNICATE_WITH_CLIENT)),
            fg="yellow",
            err=True,
        )
        raise click.ClickException(f"Failed to communicate with Docker client: {error}")
