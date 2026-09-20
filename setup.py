import re
from pathlib import Path

from setuptools import setup, find_packages

HERE = Path(__file__).parent

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()


def read_version():
    """Read __version__ from the package, the one place it's defined.

    Parsed rather than imported so building doesn't need the dependencies
    installed, and so there's no second copy of the number to drift.
    """
    source = (HERE / "flight_tracer" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__ = ["\']([^"\']+)["\']', source, re.MULTILINE)
    if not match:
        raise RuntimeError("Could not find __version__ in flight_tracer/__init__.py")
    return match.group(1)


setup(
    name="flight-tracer",
    version=read_version(),
    author="Matt Stiles",
    author_email="mattstiles@gmail.com",
    description="Turn an N-number, ICAO hex or ADS-B Exchange URL into a mapped, summarized flight trace in one command",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/stiles/flight-tracer",
    packages=find_packages(include=["flight_tracer", "flight_tracer.*"]),
    install_requires=[
        "requests",
        "pandas",
        "geopandas",
        "boto3",
        "matplotlib",
        "contextily",
        "xyzservices",
        "shapely",
        "click",
        "pytz"
    ],
    extras_require={
        "faa": ["hangarbay"],
        "tz": ["timezonefinder"],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "License :: Public Domain",
        "Operating System :: OS Independent",
    ],
    license="CC0-1.0",
    # geopandas and contextily's current releases don't support anything
    # older; >=3.7 hadn't been true for a while.
    python_requires=">=3.9",
    entry_points={
    "console_scripts": [
        "flight-tracer=flight_tracer.cli:cli",
    ],
},
)
