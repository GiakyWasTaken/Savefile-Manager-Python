"""
This module provides a custom HTTPAdapter implementation, `LocalSSLContext`,
which ensures secure SSL/TLS connections by enforcing a minimum TLS version
and loading default certificates
"""

import ssl
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager


class LocalSSLContext(HTTPAdapter):
    """
    Custom HTTPAdapter that uses a secure SSL context for requests
    This adapter sets a minimum TLS version of 1.2 and loads default certificates
    to ensure secure connections when making HTTP requests
    """

    _api_url: str = ""

    @staticmethod
    def set_api_url(api_url: str) -> None:
        """
        Sets the API URL for the instance

        Args:
            api_url (str): The URL of the API to be set
        """
        LocalSSLContext._api_url = api_url

    def init_poolmanager(
        self, connections: int, maxsize: int, block: bool = False, **pool_kwargs: Any
    ) -> PoolManager:
        """
        Initializes the connection pool manager with a custom SSL context

        Args:
            connections (int): The number of connections to cache
            maxsize (int): The maximum number of connections to pool
            block (bool): Whether to block when the pool is full
            **pool_kwargs (Any): Additional keyword arguments for the pool manager

        Returns:
            PoolManager: A configured connection pool manager
        """

        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_default_certs()
        pool_kwargs["ssl_context"] = context
        return super().init_poolmanager(  # type: ignore
            connections, maxsize, block=block, **pool_kwargs
        )

    @staticmethod
    def get_session() -> requests.Session:
        """
        Creates and returns a configured `requests.Session` object with a custom SSL context

        Returns:
            requests.Session: A session object with the custom SSL context applied
        """

        session = requests.Session()
        session.mount(LocalSSLContext._api_url, LocalSSLContext())
        return session
