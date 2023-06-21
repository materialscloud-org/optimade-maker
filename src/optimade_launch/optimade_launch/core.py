# __future__ import needed for classmethod factory functions; should be dropped
# with py 3.10.
import logging

APPLICATION_ID = "org.optimade.optimade_launch"

LOGGER = logging.getLogger(APPLICATION_ID.split(".")[-1])
