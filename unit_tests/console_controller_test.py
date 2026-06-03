"""Unit tests for the ConsoleController using a mocked HTTP session"""

from typing import Dict, List, Optional, Tuple

from pytest import MonkeyPatch

from console_controller import ConsoleController
from models import Console

API_URL = "https://api.example.com"
CONSOLE_API_URL = f"{API_URL}/console"
CREATED_AT = "2024-01-01T12:00:00.000000Z"
UPDATED_AT = "2024-01-02T12:00:00.000000Z"
NOT_FOUND_TEXT = "not found"


class MockResponse:
    """A simple mock response object to simulate HTTP responses in tests"""

    def __init__(
        self, status_code: int, json_data: Optional[List[Dict[str, object]]] = None, text: str = ""
    ):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self) -> Optional[List[Dict[str, object]]]:
        """Simulate the .json() method of a real HTTP response object"""
        return self._json


class MockSession:
    """A mock session to simulate HTTP requests and responses for testing the ConsoleController"""

    def __init__(self, responses_map: Dict[Tuple[str, str], MockResponse]):
        # key: (method, url) -> MockResponse
        self._map = responses_map

    def _respond(self, method: str, url: str) -> MockResponse:
        """Helper method to return the appropriate MockResponse based on the method and URL"""
        return self._map.get((method, url), MockResponse(500, json_data=None, text="error"))

    def get(
        self, url: str, headers: Optional[Dict[str, str]] = None, timeout: Optional[int] = None
    ) -> MockResponse:
        """Simulate a GET request and return the corresponding MockResponse"""
        _ = headers
        _ = timeout
        return self._respond("GET", url)

    def post(
        self, url: str, json: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None, timeout: Optional[int] = None
    ) -> MockResponse:
        """Simulate a POST request and return the corresponding MockResponse"""
        _ = json
        _ = headers
        _ = timeout
        return self._respond("POST", url)

    def put(
        self, url: str, json: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None, timeout: Optional[int] = None
    ) -> MockResponse:
        """Simulate a PUT request and return the corresponding MockResponse"""
        _ = json
        _ = headers
        _ = timeout
        return self._respond("PUT", url)

    def delete(
        self, url: str,
        headers: Optional[Dict[str, str]] = None, timeout: Optional[int] = None
    ) -> MockResponse:
        """Simulate a DELETE request and return the corresponding MockResponse"""
        _ = headers
        _ = timeout
        return self._respond("DELETE", url)


def create_controller_with_session(
    monkeypatch: MonkeyPatch, responses_map: Dict[Tuple[str, str], MockResponse]
) -> ConsoleController:
    """
    Create a ConsoleController using a mocked LocalSSLContext session

    The `responses_map` maps (method, url) to `MockResponse` instances used
    by the mocked session to simulate API responses.
    """

    mock_session = MockSession(responses_map)
    # Patch the LocalSSLContext.get_session to return our mock session
    monkeypatch.setattr("local_ssl_context.LocalSSLContext.get_session", lambda: mock_session)
    return ConsoleController(API_URL, "dummy_token")


def test_get_returns_console_on_200(monkeypatch: MonkeyPatch):
    """Ensure controller.get returns a `Console` when API returns HTTP 200"""
    api_obj: List[Dict[str, object]] = [
        {
            "id": 1,
            "console_name": "Test Console",
            "created_at": CREATED_AT,
            "updated_at": UPDATED_AT,
        }
    ]

    responses = {
        ("GET", CONSOLE_API_URL + "/1"): MockResponse(200, json_data=api_obj, text=str(api_obj))
    }

    controller = create_controller_with_session(monkeypatch, responses)

    result = controller.get(1)

    assert isinstance(result, Console)
    assert result.id == 1
    assert result.name == "Test Console"
    assert result.created_at == CREATED_AT


def test_get_returns_none_on_404(monkeypatch: MonkeyPatch):
    """Ensure controller.get returns None for a 404 response"""
    responses = {
        ("GET", CONSOLE_API_URL + "/2"): MockResponse(404, json_data=None, text=NOT_FOUND_TEXT)
    }

    controller = create_controller_with_session(monkeypatch, responses)

    result = controller.get(2)

    assert result is None


def test_get_all_returns_list_and_empty_when_no_items(monkeypatch: MonkeyPatch):
    """Verify get_all returns list of consoles and handles empty lists"""
    api_list: List[Dict[str, object]] = [
        {
            "id": 1,
            "console_name": "A",
            "created_at": CREATED_AT,
            "updated_at": UPDATED_AT
        },
        {
            "id": 2, "console_name": "B", "created_at": CREATED_AT,
            "updated_at": UPDATED_AT
        },
    ]

    responses = {
        ("GET", CONSOLE_API_URL): MockResponse(200, json_data=api_list, text=str(api_list))
    }

    controller = create_controller_with_session(monkeypatch, responses)

    result = controller.get_all()

    assert isinstance(result, List)
    assert len(result) == 2

    # Now simulate empty list response
    responses_empty = {("GET", CONSOLE_API_URL): MockResponse(200, json_data=[], text="[]")}
    controller = create_controller_with_session(monkeypatch, responses_empty)
    result_empty = controller.get_all()
    assert result_empty == []


def test_save_and_conflict_handling(monkeypatch: MonkeyPatch):
    """Test saving a console and handling HTTP 409 conflict responses"""
    api_obj: List[Dict[str, object]] = [
        {
            "id": 3,
            "console_name": "Saved Console",
            "created_at": CREATED_AT,
            "updated_at": UPDATED_AT
        }
    ]

    responses = {
        ("POST", CONSOLE_API_URL): MockResponse(201, json_data=api_obj, text=str(api_obj))
    }

    controller = create_controller_with_session(monkeypatch, responses)

    model = Console(name="Saved Console")
    created = controller.save(model)

    assert isinstance(created, Console)
    assert created.id == 3

    # Conflict
    responses_conflict = {
        ("POST", CONSOLE_API_URL): MockResponse(409, json_data=None, text="conflict")
    }
    controller = create_controller_with_session(monkeypatch, responses_conflict)
    created_conflict = controller.save(model)
    assert created_conflict is None


def test_update_and_not_found(monkeypatch: MonkeyPatch):
    """Test update returns the updated model on 200 and None on 404"""
    api_obj: List[Dict[str, object]] = [
        {
            "id": 4,
            "console_name": "Updated Console",
            "created_at": CREATED_AT,
            "updated_at": "2024-01-03T12:00:00.000000Z"
        }
    ]

    responses = {
        ("PUT", API_URL + "/console/4"): MockResponse(200, json_data=api_obj, text=str(api_obj))
    }

    controller = create_controller_with_session(monkeypatch, responses)

    model = Console(id=4, name="Updated Console")
    updated = controller.update(model)

    assert isinstance(updated, Console)
    assert updated.id == 4

    # Not found
    responses_nf = {
        ("PUT", API_URL + "/console/5"): MockResponse(404, json_data=None, text=NOT_FOUND_TEXT)
    }
    controller = create_controller_with_session(monkeypatch, responses_nf)
    model_nf = Console(id=5, name="DoesNotExist")
    updated_nf = controller.update(model_nf)
    assert updated_nf is None


def test_delete_success_and_not_found(monkeypatch: MonkeyPatch):
    """Test delete returns True for successful delete and False for 404"""
    responses = {
        ("DELETE", API_URL + "/console/6"): MockResponse(204, json_data=None, text=""),
        ("DELETE", API_URL + "/console/7"): MockResponse(404, json_data=None, text=NOT_FOUND_TEXT),
    }

    controller = create_controller_with_session(monkeypatch, responses)

    assert controller.delete(6) is True
    assert controller.delete(7) is False


def test_search_single_and_multiple_results(monkeypatch: MonkeyPatch):
    """Test the search behavior for single, multiple, and no matches"""
    # Two consoles with same name to create multiple matches
    api_list: List[Dict[str, object]] = [
        {
            "id": 8, "console_name": "SearchMe", "created_at": CREATED_AT,
            "updated_at": UPDATED_AT
        },
        {
            "id": 9, "console_name": "SearchMe", "created_at": CREATED_AT,
            "updated_at": UPDATED_AT
        },
        {
            "id": 10, "console_name": "Other", "created_at": CREATED_AT,
            "updated_at": UPDATED_AT
        },
    ]

    responses = {
        ("GET", CONSOLE_API_URL): MockResponse(200, json_data=api_list, text=str(api_list))
    }

    controller = create_controller_with_session(monkeypatch, responses)

    search_model = Console(name="SearchMe")
    # By default multiple results should return None
    res_default = controller.search(search_model)
    assert res_default is None

    # Allow multiple results
    res_multiple = controller.search(search_model, allow_multiple_results=True)
    assert isinstance(res_multiple, List)
    assert len(res_multiple) == 2

    # Single unique match
    search_unique = Console(name="Other")
    res_unique = controller.search(search_unique)
    assert isinstance(res_unique, List) or res_unique is None
    # Should find exactly one item and return it
    assert res_unique is not None
    assert res_unique[0].name == "Other"
