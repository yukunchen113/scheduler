from setuptools import setup, find_packages

setup(
    name='plex',
    version='1.0.0',
    description='Plan your day with ease.',
    author='Yukun Chen',
    author_email='yukunchen113@gmail.com',
    packages=find_packages(),
    install_requires=[
		"gcsa==2.2.0",
		"google_api_python_client==2.108.0",
		"google_auth_oauthlib==0.8.0",
		"protobuf==4.25.2",
		"setuptools==65.6.3",
		"typed_argument_parser==1.8.1",
    ],
)