"""
General utilities.
"""
from contextlib import contextmanager

import requests


@contextmanager
def get_session(headers: dict = None, auth: tuple = None) -> requests.Session:
    """
    Yield a requests.Session context with the given headers and auth.

    Args:
        headers (dict): request headers
        auth (tuple): (username, password) http basic auth

    Yields: requests.Session

    """
    with requests.Session() as session:
        session.auth = auth
        session.headers = headers
        yield session
