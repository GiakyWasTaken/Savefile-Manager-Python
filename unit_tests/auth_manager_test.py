"""Unit tests for AuthManager module"""

import os
import pytest
import responses
from responses import RequestsMock

from auth_manager import AuthManager

API_URL = "https://api.example.com"
EMAIL = "admin@example.com"


@pytest.fixture(scope="module")
def mock_responses():
    """Setup and teardown for mocked responses"""
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            API_URL + "/login",
            json={"token": "mocked_token"},
            status=200,
        )
        rsps.add(
            responses.GET,
            API_URL + "/logout",
            body="Successfully logged out",
            status=200,
        )
        rsps.add(
            responses.POST,
            API_URL + "/register",
            json={"token": "mocked_token"},
            status=201,
        )
        yield rsps

    # Clean up log folder after tests
    log_folder = "log"
    if os.path.exists(log_folder):
        for filename in os.listdir(log_folder):
            file_path = os.path.join(log_folder, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
        os.rmdir(log_folder)


def test_login(mock_responses: RequestsMock):  # pylint: disable=redefined-outer-name
    """
    Test the login functionality of AuthManager
    """
    result = AuthManager.login(API_URL, EMAIL, "password123")
    assert result == "mocked_token"

    # Test with incorrect credentials
    mock_responses.replace(
        responses.POST,
        API_URL + "/login",
        json={"error": "Invalid credentials"},
        status=401,
    )
    result = AuthManager.login(API_URL, EMAIL, "password123")
    assert result is None


def test_logout():  # pylint: disable=redefined-outer-name
    """
    Test the logout functionality of AuthManager
    """
    result = AuthManager.logout(API_URL, "dummy_token")
    assert result is True

    # Test logout with no token
    result = AuthManager.logout(API_URL, "")
    assert result is False


def test_register_user(
    mock_responses: RequestsMock,
):  # pylint: disable=redefined-outer-name
    """
    Test the user registration functionality of AuthManager
    """
    result = AuthManager.register(API_URL, "Admin User", EMAIL, "password123")
    assert result == "mocked_token"

    # Test registration failure
    mock_responses.replace(
        responses.POST,
        API_URL + "/register",
        json={"error": "Email already exists"},
        status=400,
    )
    result = AuthManager.register(API_URL, "Admin User", EMAIL, "password123")
    assert result is None
