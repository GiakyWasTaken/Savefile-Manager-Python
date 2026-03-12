"""Unit tests for SavefileController using a mocked HTTP session."""

import datetime
import io
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from _pytest.monkeypatch import MonkeyPatch

from models import Savefile, DATE_FORMAT
from savefile_controller import SavefileController

API_URL = "https://api.example.com"
SAVEFILE_API_URL = f"{API_URL}/savefile"
CREATED_AT = "2024-01-01T12:00:00.000000Z"
UPDATED_AT = "2024-01-02T12:00:00.000000Z"


class MockResponse:
    """A simple mock response object to simulate HTTP responses in tests"""

    def __init__(
        self, status_code: int, json_data: Optional[Dict[str, object]], text: str = "",
        content: bytes = b""
    ):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.content = content

    def json(self) -> Dict[str, object]:
        """Simulate the .json() method of a real HTTP response object"""
        return self._json or {}

    def iter_content(self, chunk_size: int = 8192) -> Iterable[bytes]:
        """
        Simulate the .iter_content() method of a real HTTP response object for streaming downloads
        """
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i: i + chunk_size]


class MockSession:
    """A mock session to simulate HTTP requests and responses for testing the ConsoleController"""

    def __init__(self, responses_map: Dict[Tuple[str, str], MockResponse]):
        # key: (method, url) -> MockResponse
        self.headers: Optional[Dict[str, str]] = None
        self.stream: Optional[bool] = None
        self.timeout: Optional[int] = None
        self._map = responses_map
        self.last_data: Optional[Dict[str, object]] = None
        self.last_files: Optional[object] = None

    def _respond(self, method: str, url: str) -> MockResponse:
        """Helper method to return the appropriate MockResponse based on the method and URL"""
        return self._map.get((method, url), MockResponse(500, json_data=None, text="error"))

    def get(
        self, url: str, headers: Optional[Dict[str, str]] = None, stream: bool = False,
        timeout: Optional[int] = None
    ) -> MockResponse:
        """Simulate a GET request and return the corresponding MockResponse"""
        self.headers = headers
        self.stream = stream
        self.timeout = timeout
        return self._respond("GET", url)

    def post(self, url: str, *args: Any, **kwargs: Any) -> MockResponse:
        """
        Simulate a POST request and return the corresponding MockResponse

        Captures typical parameters (data, files, headers, timeout, json)
        whether passed positionally or as keywords
        """
        # prefer explicit kwargs, fall back to positional args if provided
        data = kwargs.get("data", None)
        files = kwargs.get("files", None)
        if data is None and len(args) >= 1:
            data = args[0]
        if files is None and len(args) >= 2:
            files = args[1]

        json_body: Optional[Dict[str, object]] = kwargs.get("json", None)
        self.last_data = data if data is not None else json_body
        self.last_files = files
        self.headers = kwargs.get("headers", None)
        timeout = kwargs.get("timeout", None)
        if timeout is None and len(args) >= 3:
            timeout = args[2]
        self.timeout = timeout
        return self._respond("POST", url)


def create_controller_with_session(
    monkeypatch: MonkeyPatch
    , responses_map: Dict[Tuple[str, str], MockResponse]
) -> Tuple[SavefileController, MockSession]:
    """
    Create a SavefileController wired to a mocked HTTP session

    The provided `responses_map` is used by `MockSession` to return
    predetermined responses for specific (method, url) keys

    Returns:
        Tuple[SavefileController, MockSession]: controller and the mocked session
    """

    mock_session = MockSession(responses_map)
    # Patch the LocalSSLContext.get_session to return our mock session
    monkeypatch.setattr(
        "local_ssl_context.LocalSSLContext.get_session", lambda: mock_session
    )
    return SavefileController(API_URL, "dummy_token"), mock_session


def test_get_returns_savefile_model_without_downloading(monkeypatch: MonkeyPatch):
    """
    Ensure `get` returns a Savefile model when download_path is not provided

    Verifies fields are correctly mapped from the API response
    """
    api_obj: Dict[str, object] = {
        "id": 1,
        "file_name": "game.sav",
        "file_path": "saves/slot1",
        "created_at": CREATED_AT,
        "updated_at": UPDATED_AT,
        "fk_id_console": 2,
    }

    responses = {
        ("GET", SAVEFILE_API_URL + "/1"): MockResponse(
            200, json_data=api_obj, text=str(api_obj)
        )
    }

    controller, _ = create_controller_with_session(monkeypatch, responses)

    result = controller.get(1)

    assert isinstance(result, Savefile)
    assert result.id == 1
    assert result.name == "game.sav"
    assert result.rel_path == "saves/slot1"
    assert result.id_console == 2


def test_get_downloads_file_and_sets_mtime(monkeypatch: MonkeyPatch, tmp_path: Path):
    """
    Verify that `get(..., download_path=...)` downloads the file and sets mtime

    The test simulates two sequential GET responses: one for the JSON metadata
    and a second streaming response containing file bytes
    """
    api_obj: Dict[str, object] = {
        "id": 5,
        "file_name": "download.sav",
        "file_path": "slotX",
        "created_at": CREATED_AT,
        "updated_at": UPDATED_AT,
        "fk_id_console": 7,
    }

    file_bytes = b"\x00\x01\x02save-data"

    # Use a sequence responder so first GET returns JSON and second GET returns bytes
    call_count = {"n": 0}

    def responder():
        """Simulate sequential GET responses: first for metadata, then for file content"""
        call_count["n"] += 1
        if call_count["n"] == 1:
            return MockResponse(200, json_data=api_obj, text=str(api_obj))
        return MockResponse(200, json_data={}, text="file", content=file_bytes)

    class SequenceSession(MockSession):
        """
        A mock session that returns different responses for sequential GET calls to simulate
        metadata retrieval followed by file download
        """

        def __init__(self):
            super().__init__({})

        def get(
            self, url: str, headers: Optional[Dict[str, str]] = None, stream: bool = False,
            timeout: Optional[int] = None
        ):
            return responder()

    seq_session = SequenceSession()
    monkeypatch.setattr(
        "local_ssl_context.LocalSSLContext.get_session", lambda: seq_session
    )

    controller = SavefileController(API_URL, "token")

    download_path = tmp_path / "out" / "download.sav"

    result = controller.get(5, download_path=str(download_path))

    assert isinstance(result, Savefile)
    assert download_path.exists()

    with open(download_path, "rb") as f:
        data = f.read()
        assert data == file_bytes

    # Interpret the test timestamp as UTC so it matches the controller's
    # normalization (which turns trailing 'Z' into +00:00 and produces an
    # aware UTC datetime). Use an aware datetime for a consistent epoch.
    parsed_dt = datetime.datetime.strptime(UPDATED_AT, DATE_FORMAT).replace(
        tzinfo=datetime.timezone.utc
    )

    assert int(os.path.getmtime(download_path)) == int(parsed_dt.timestamp())


def test_get_headers_removes_content_type():
    """
    Assert `get_headers` for `SavefileController` does not include Content-Type
    """
    controller = SavefileController(API_URL, "token")
    headers = controller.get_headers()
    assert "Content-Type" not in headers


def test_save_uploads_file_and_handles_conflict(monkeypatch: MonkeyPatch):
    """
    Test uploading a savefile and handling HTTP 409 conflict responses

    Ensures file-like objects from the model are sent and that conflict
    responses result in None
    """
    api_obj: Dict[str, object] = {
        "id": 11,
        "file_name": "u.sav",
        "file_path": "p",
        "created_at": CREATED_AT,
        "updated_at": UPDATED_AT,
        "fk_id_console": 3,
    }

    responses_ok = {
        ("POST", SAVEFILE_API_URL): MockResponse(201, json_data=api_obj, text=str(api_obj))
    }

    controller, _ = create_controller_with_session(monkeypatch, responses_ok)

    # Make Savefile.savefile return a file-like object for upload
    monkeypatch.setattr(Savefile, "savefile", property(lambda self: io.BytesIO(b"abc")))

    model = Savefile(name="u.sav", rel_path="p", id_console=3)
    created = controller.save(model)

    assert isinstance(created, Savefile)
    assert created.id == 11

    # Now simulate conflict
    responses_conflict = {
        ("POST", SAVEFILE_API_URL): MockResponse(409, json_data=None, text="conflict")
    }
    controller, _ = create_controller_with_session(monkeypatch, responses_conflict)
    monkeypatch.setattr(Savefile, "savefile", property(lambda self: io.BytesIO(b"abc")))
    created_conflict = controller.save(model)
    assert created_conflict is None


def test_update_uses_method_override_and_handles_not_found(monkeypatch: MonkeyPatch):
    """
    Test that update uses `_method=PUT` override and handles 404

    Confirms the controller places `_method` in POST data for PHP-style
    method override and that a 404 response returns None
    """
    api_obj: Dict[str, object] = {
        "id": 21,
        "file_name": "u2.sav",
        "file_path": "p2",
        "created_at": CREATED_AT,
        "updated_at": UPDATED_AT,
        "fk_id_console": 4,
    }

    responses_ok = {
        ("POST", f"{SAVEFILE_API_URL}/21"): MockResponse(
            200, json_data=api_obj, text=str(api_obj)
        )
    }

    controller, mock_session = create_controller_with_session(monkeypatch, responses_ok)

    # Ensure savefile property returns file-like
    monkeypatch.setattr(Savefile, "savefile", property(lambda self: io.BytesIO(b"xyz")))

    model = Savefile(id=21, name="u2.sav", rel_path="p2", id_console=4)
    updated = controller.update(model)

    assert isinstance(updated, Savefile)

    # Verify that controller used POST with _method=PUT in data
    assert mock_session.last_data is not None
    assert ("_method" in mock_session.last_data) and (
        mock_session.last_data["_method"] == "PUT")

    # Not found case
    responses_nf = {
        ("POST", f"{SAVEFILE_API_URL}/22"): MockResponse(
            404, json_data=None, text="not found"
        )
    }
    controller, _ = create_controller_with_session(monkeypatch, responses_nf)
    model_nf = Savefile(id=22, name="no.sav", rel_path="/x", id_console=9)
    updated_nf = controller.update(model_nf)
    assert updated_nf is None
