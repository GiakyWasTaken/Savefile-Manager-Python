"""
Authentication manager module for the Savefile Manager application
Handles user authentication, registration, and logout operations
"""

from typing import Dict, Optional

from local_ssl_context import LocalSSLContext
from logger import Logger


class AuthManager:
    """
    Manages authentication operations such as login, logout, and registration
    """

    @staticmethod
    def __get_headers() -> Dict[str, str]:
        return {"Accept": "application/json", "Content-Type": "application/json"}

    @staticmethod
    def login(api_url: str, email: str, password: str) -> Optional[str]:
        """
        Authenticate the user and retrieve an access token

        Args:
            api_url (str): API base URL
            email (str): User's email address
            password (str): User's password

        Returns:
            str: Access token if login is successful, empty string otherwise
        """
        logger = Logger("Auth")
        login_url = f"{api_url}/login"
        payload: Dict[str, str] = {"email": email, "password": password}
        headers = AuthManager.__get_headers()

        response = LocalSSLContext.get_session().post(
            login_url, json=payload, headers=headers, timeout=10
        )
        token = None

        logger.log_debug(f"Login response: {response.status_code} - {response.text}")

        if response.status_code == 200:
            token = response.json().get("token")
            logger.log_info("Login successful")
        else:
            logger.log_error("Login failed")

        return token

    @staticmethod
    def logout(api_url: str, token: str) -> bool:
        """
        Log out the user by invalidating the access token

        Args:
            api_url (str): API base URL
            token (str): Access token to be invalidated

        Returns:
            bool: True if logout is successful, False otherwise
        """
        logger = Logger("Auth")
        if not token:
            logger.log_warning("No token provided for logout")
            return False

        logout_url = f"{api_url}/logout"
        headers = AuthManager.__get_headers()
        headers["Authorization"] = f"Bearer {token}"

        response = LocalSSLContext.get_session().get(
            logout_url, headers=headers, timeout=10
        )
        result = False

        logger.log_debug(f"Logout response: {response.status_code} - {response.text}")

        if response.status_code == 200 and "logged out" in response.text.lower():
            logger.log_info("Logout successful")
            result = True
        else:
            logger.log_error("Logout failed")

        return result

    @staticmethod
    def register(api_url: str, name: str, email: str, password: str) -> Optional[str]:
        """
        Register a new user and retrieve an access token

        Args:
            api_url (str): API base URL
            name (str): User's name
            email (str): User's email address
            password (str): User's password

        Returns:
            str: Access token if registration is successful, empty string otherwise
        """
        logger = Logger("Auth")
        register_url = f"{api_url}/register"
        payload: Dict[str, str] = {
            "name": name,
            "email": email,
            "password": password,
            "password_confirmation": password,
        }
        headers = AuthManager.__get_headers()

        response = LocalSSLContext.get_session().post(
            register_url,
            json=payload,
            headers=headers,
            timeout=10,
        )
        token = None

        logger.log_debug(f"Register response: {response.status_code} - {response.text}")

        if response.status_code == 201:
            token = response.json().get("token")
            logger.log_info("Registration successful")
        else:
            logger.log_error("Registration failed")

        return token
