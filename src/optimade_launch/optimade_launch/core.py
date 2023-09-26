# __future__ import needed for classmethod factory functions; should be dropped
# with py 3.10.
import os
import logging
import click
from pathlib import Path

APPLICATION_ID = "org.optimade.optimade_launch"
LOGGER = logging.getLogger(APPLICATION_ID.split(".")[-1])

if os.environ.get("OPTIMADE_LAUNCH_CONFIG_FOLDER"):
    CONFIG_FOLDER = Path(os.environ["OPTIMADE_LAUNCH_CONFIG_FOLDER"])
else:
    CONFIG_FOLDER = Path(click.get_app_dir(APPLICATION_ID))
