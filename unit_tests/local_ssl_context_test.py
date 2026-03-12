"""Unit tests for LocalSSLContext adapter"""

from local_ssl_context import LocalSSLContext


def test_session_mounts_adapter_for_given_api_url():
    """Ensure that setting an API URL mounts the custom adapter for that prefix"""

    api_prefix = "https://api.example/"
    LocalSSLContext.set_api_url(api_prefix)

    session = LocalSSLContext.get_session()

    adapter = session.get_adapter("https://api.example/resource")

    assert isinstance(adapter, LocalSSLContext)


def test_session_uses_local_adapter_for_matching_url_and_default_for_others():
    """Verify the adapter is used for the configured API prefix, but not for unrelated hosts"""

    api_prefix = "https://api.example/"
    LocalSSLContext.set_api_url(api_prefix)

    session = LocalSSLContext.get_session()

    matching_adapter = session.get_adapter("https://api.example/other")
    other_adapter = session.get_adapter("https://other.example/")

    assert isinstance(matching_adapter, LocalSSLContext)
    assert not isinstance(other_adapter, LocalSSLContext)


def test_setting_api_url_without_trailing_slash_still_matches():
    """Ensure the adapter matches the API URL prefix even without a trailing slash"""

    api_prefix = "https://api.example"
    LocalSSLContext.set_api_url(api_prefix)

    session = LocalSSLContext.get_session()

    adapter = session.get_adapter("https://api.example/path")

    assert isinstance(adapter, LocalSSLContext)


def test_empty_api_url_mounts_adapter_for_all_urls():
    """Setting an empty API URL should mount the adapter as a default for all schemes"""

    LocalSSLContext.set_api_url("")

    session = LocalSSLContext.get_session()

    adapter_https = session.get_adapter("https://any.host/path")

    assert isinstance(adapter_https, LocalSSLContext)
