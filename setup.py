from setuptools import find_packages, setup

setup(
    name="plex",
    version="1.0.0",
    description="Plan your day with ease.",
    author="Plex Contributor",
    packages=find_packages(),
    install_requires=[
        "gcsa>=2.2.0",
        "google_api_python_client>=2.108.0",
        "google_auth_oauthlib>=0.8.0",
        "notion-client>=2.0.0",
        "protobuf>=4.25.2",
        "setuptools>=65.6.3",
        "typed_argument_parser>=1.8.1",
    ],
    entry_points={
        "console_scripts": [
            "plex = plex.__main__:cli",
            "plex-setup = plex.setup:main",
        ],
    },
)
