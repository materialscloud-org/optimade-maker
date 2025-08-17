import logging
import os

level_name = os.getenv("LOGLEVEL", "INFO").upper()
level = getattr(logging, level_name, logging.INFO)

LOGGER = logging.getLogger("optimade-maker")
LOGGER.setLevel(level)

handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
)

LOGGER.addHandler(handler)
LOGGER.propagate = False
