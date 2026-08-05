"""Find My Timeline - Track historical location data from Apple Find My devices."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("find-my-timeline")
except PackageNotFoundError:
    __version__ = "development"
