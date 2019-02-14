#!/usr/bin/env python
# -*- coding: utf-8 -*-


from setuptools import find_packages, setup

# Package meta-data.
NAME = "flow_toolz"
DESCRIPTION = "Shared airflow libs."
URL = "https://github.com/"
EMAIL = "your@email.com"
AUTHOR = "your name"
REQUIRES_PYTHON = ">=3.6.0"
VERSION = "alpha"

REQUIRED = [
    "requests",
    "boto3",
    "invoke",
    "dataclasses",
    "importlib_resources",
]

airflow_requirements = [
    "apache-airflow[gcp_api,password,google_auth,s3,postgres,celery]"
]
test_requirements = ["pytest"]
data_science_requirements = [
    "jupyterlab",
    "fastparquet",
    "pandas",
    "pandas-gbq",
]
development_requirements = ["jinja2", "klaxon"]

EXTRAS = {
    "airflow": airflow_requirements,
    "test": test_requirements,
    "data-science": data_science_requirements,
    "dev": development_requirements,
    "all": airflow_requirements
    + test_requirements
    + data_science_requirements
    + development_requirements,
}


setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    author=AUTHOR,
    author_email=EMAIL,
    python_requires=REQUIRES_PYTHON,
    url=URL,
    packages=find_packages(exclude=("tests",)),
    install_requires=REQUIRED,
    extras_require=EXTRAS,
    include_package_data=True,
    classifiers=[
        # Trove classifiers
        # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
)
