import codecs
import os
import re
from setuptools import setup, find_packages


def read(*parts):
    here = os.path.abspath(os.path.dirname(__file__))
    return codecs.open(os.path.join(here, *parts), 'r').read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)

    raise RuntimeError("Unable to find version string.")


setup(
    name='aiowebsocket',
    version=find_version('aiowebsocket', '__init__.py'),
    packages=find_packages(),
    url='https://github.com/asyncins/aiowebsocket',
    license='Apache 2.0',
    author='AsyncIns',
    author_email='asyncins@aliyun.com',
    description='Asynchronous WebSocket Client .',
    long_description='See https://github.com/asyncins/aiowebsocket',
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ]
)