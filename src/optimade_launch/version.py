"""
This module contains project version information.
"""

try:
    from dunamai import Version, get_version

    __version__ = Version.from_git().serialize()
except RuntimeError:
    __version__ = get_version("optimade-launch").serialize()
except ImportError:
    __version__ = "v2023.1000"
