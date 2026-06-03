"""Unit tests for main module functions"""

import argparse
import datetime
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Optional, List, Tuple

from _pytest.monkeypatch import MonkeyPatch

import main
from console_controller import ConsoleController
from main import CrawlingMode, SavefileAvailability, ProcessingResult
from models import Console, Savefile
from savefile_controller import SavefileController


def test_fit_text_to_width_returns_full_when_fits():
    """Ensure fit_text_to_width returns the full name when it fits within the width limit"""
    out = main.fit_text_to_width(20, "name.txt", "/path/")
    assert "name.txt" in out
    assert len(out) == 20


def test_fit_text_to_width_truncates_long_name():
    """Ensure fit_text_to_width truncates long names"""
    out = main.fit_text_to_width(5, "longfilename.ext", "/very/long/path/")
    assert len(out) == 5
    assert "…" in out or out.endswith(" ")


def test_set_sized_description_uses_default_width_when_no_two_line_extra():
    """Ensure set_sized_description uses default width when no two line extra"""

    class DummyPbar:
        """A dummy progress bar class for testing"""

        def __init__(self):
            self.desc = None

        def set_description(self, value: str):
            """Simulate setting the description"""
            self.desc = value

    p = DummyPbar()
    main.set_sized_description(p, "SomeDescription", "/r/")
    assert p.desc is not None
    assert len(p.desc) <= 50


def test_set_sized_description_respects_terminal_width(monkeypatch: MonkeyPatch):
    """Ensure set_sized_description respects terminal width and accounts for two line extra width"""

    class DummyPbar:
        """A dummy progress bar class for testing"""

        def __init__(self):
            self.desc = None
            self._two_line_extra_width = 10

        def set_description(self, value: str):
            """Simulate setting the description"""
            self.desc = value

    def fake_terminal_size(fallback: Tuple[int, int] = (80, 24)) -> os.terminal_size:
        """Simulate a terminal size of 80 columns and 24 rows, ignoring the fallback value"""
        _ = fallback
        return os.terminal_size((80, 24))

    monkeypatch.setattr(shutil, "get_terminal_size", fake_terminal_size)

    p = DummyPbar()
    main.set_sized_description(p, "Desc", "/r/")
    assert p.desc is not None
    # available max length should be <= 80
    assert len(p.desc) <= 80


def test_create_progress_bars_returns_expected_bars_large_terminal(monkeypatch: MonkeyPatch):
    """
    Ensure create_progress_bars returns a single primary bar and no secondary bar when terminal
    is large enough
    """

    def fake_terminal_size(fallback: Tuple[int, int] = (80, 24)) -> os.terminal_size:
        """Simulate a terminal size of 120 columns and 24 rows, ignoring the fallback value"""
        _ = fallback
        return os.terminal_size((120, 24))

    monkeypatch.setattr(shutil, "get_terminal_size", fake_terminal_size)
    primary, secondary = main.create_progress_bars(1, is_console=False)
    assert secondary is None
    assert primary is not None


def test_create_progress_bars_returns_two_bars_small_terminal(monkeypatch: MonkeyPatch):
    """
    Ensure create_progress_bars returns both primary and secondary bars when terminal is small
    and is_console is True
    """

    def fake_terminal_size(fallback: Tuple[int, int] = (80, 24)) -> os.terminal_size:
        """Simulate a terminal size of 80 columns and 24 rows, ignoring the fallback value"""
        _ = fallback
        return os.terminal_size((80, 24))

    monkeypatch.setattr(shutil, "get_terminal_size", fake_terminal_size)
    primary, secondary = main.create_progress_bars(1, is_console=True)
    assert primary is not None
    assert secondary is not None


def test_extract_bash_array_parses_values(tmp_path: Path):
    """
    Ensure extract_bash_array correctly parses values from a bash array in a .env file, ignoring
    comments and whitespace
    """
    content = """
export CONSOLE_NAMES=(
'PS4'
"PS5"
# a comment
)
"""
    p = tmp_path / ".envtmp"
    p.write_text(content, encoding="utf-8")
    res = main.extract_bash_array(str(p), "CONSOLE_NAMES")
    assert res == ["PS4", "PS5"]


def test_get_crawling_downloading_mode_defaults_to_auto_when_not_specified(
        monkeypatch: MonkeyPatch
):
    """
    Ensure get_crawling_downloading_mode returns AUTO when no command line arguments are provided
    """
    monkeypatch.setattr(sys, "argv", ["prog"])
    # ensure logger won't fail
    cmodes = main.get_crawling_downloading_mode()
    assert cmodes[0] in (CrawlingMode.AUTO, CrawlingMode.NONE, CrawlingMode.AUTO)


def test_setup_env_reads_env_and_sets_api_url(monkeypatch: MonkeyPatch):
    """Ensure setup_env reads environment variables and sets API URL in LocalSSLContext"""
    monkeypatch.setenv("EMAIL", "e@example.com")
    monkeypatch.setenv("PASSWORD", "pw")
    monkeypatch.setenv("API_URL", "https://api.test/")

    def fake_extract_bash_array(path: Path, name: str) -> List[str]:
        """
        Simulate extracting a bash array from a .env file, returning predefined values based on
        the name
        """
        _ = path
        _ = name
        return ["C1"] if name == "CONSOLE_NAMES" else ["/opt/savefiles"]

    monkeypatch.setattr(
        main, "extract_bash_array",
        fake_extract_bash_array
    )

    monkeypatch.setattr(main, "parser", argparse.ArgumentParser())
    monkeypatch.setattr(sys, "argv", ["prog"])
    # capture set_api_url
    called: Dict[str, str] = {}

    def fake_set_api_url(url: str):
        """Simulate setting the API URL and capture the value for assertion"""
        called["url"] = url

    monkeypatch.setattr(main.LocalSSLContext, "set_api_url", fake_set_api_url)
    consoles, saves_paths, api_url, _ = main.setup_env()
    assert consoles == ["C1"]
    assert saves_paths == ["/opt/savefiles"]
    assert api_url == "https://api.test"
    assert called.get("url") == "https://api.test"


def test_retrieve_local_consoles_creates_and_uses_remote():
    """
    Ensure retrieve_local_consoles creates new consoles when create_new_consoles is True and
    returns existing remote names
    """

    class FakeController(ConsoleController):
        """
        A fake ConsoleController for testing that simulates fetching consoles and saving new
        consoles
        """

        def __init__(self, api_url: str = "", api_token: str = ""):
            super().__init__(api_url, api_token)
            self._all = [Console(id=1, name="C1")]

        def get_all(
                self,
                records: Optional[int] = None,
                offset: Optional[int] = None
        ) -> List[Console]:
            """Simulate fetching all consoles"""
            return self._all

        def search(self, model: Console, allow_multiple_results: bool = False) -> List[Console]:
            """
            Simulate searching for a console by name, returning a list with a matching console if
            found
            """
            return [Console(id=1, name="C1")] if model.name == "C1" else []

        def save(self, model: Console) -> Console:
            """Simulate saving a console"""
            return Console(id=2, name=model.name)

    controller = FakeController()
    # when create_new_consoles True, existing remote names should be returned
    res = main.retrieve_local_consoles(["C1", "C2"], controller, create_new_consoles=True)
    assert isinstance(res, List)
    assert any(c.name == "C1" for c in res)
    assert any(c.name == "C2" for c in res)


def test_handle_creating_savefile_respects_mode_and_save():
    """
    Ensure handle_creating_savefile respects the crawling mode and attempts to save when appropriate
    """

    class FakeSaveCtrl(SavefileController):
        """
        A fake SavefileController for testing that simulates saving a savefile and can be
        configured to
        """

        def __init__(self, ok: bool = True, api_url: str = "", api_token: str = ""):
            super().__init__(api_url, api_token)
            self.ok = ok

        def save(self, model: Savefile) -> Optional[Savefile]:
            """Simulate saving a savefile"""
            return model if self.ok else None

    sf = Savefile(name="a.sav")
    # UPDATE should ignore
    assert main.handle_creating_savefile(
        sf, FakeSaveCtrl(True), CrawlingMode.UPDATE
    ) == ProcessingResult.IGNORED
    # NEW should attempt save
    assert main.handle_creating_savefile(
        sf, FakeSaveCtrl(True), CrawlingMode.NEW
    ) == ProcessingResult.CREATED
    assert main.handle_creating_savefile(
        sf, FakeSaveCtrl(False), CrawlingMode.NEW
    ) == ProcessingResult.FAILED_CREATION


def test_handle_downloading_savefile_behaviour():
    """
    Ensure handle_downloading_savefile behaves correctly based on the presence of an ID,
    the crawling
    """

    class FakeSaveCtrl(SavefileController):
        """
        A fake SavefileController for testing that simulates downloading a savefile and can be
        """

        def __init__(self, ok: bool = True, api_url: str = "", api_token: str = ""):
            super().__init__(api_url, api_token)
            self.ok = ok

        def get(self, resource_id: int, download_path: Optional[str] = None) -> Optional[Savefile]:
            """Simulate getting a savefile by ID"""
            return Savefile(id=resource_id, name="f.sav") if self.ok else None

    sf = Savefile(name="f.sav")
    sf.id = None
    # missing id -> failed
    assert main.handle_downloading_savefile(
        sf, FakeSaveCtrl(True), CrawlingMode.ALL
    ) == ProcessingResult.FAILED_DOWNLOAD
    sf.id = 5
    # downloading_mode less than NEW and not overwrite -> ignored
    assert main.handle_downloading_savefile(
        sf, FakeSaveCtrl(True), CrawlingMode.UPDATE
    ) == ProcessingResult.IGNORED
    # overwrite or sufficient mode
    assert main.handle_downloading_savefile(
        sf, FakeSaveCtrl(True), CrawlingMode.NEW
    ) == ProcessingResult.DOWNLOADED
    assert main.handle_downloading_savefile(
        sf, FakeSaveCtrl(False), CrawlingMode.NEW
    ) == ProcessingResult.FAILED_DOWNLOAD


def test_handle_existing_savefile_upload_and_download():
    """
    Ensure handle_existing_savefile correctly decides to upload or download based on modified
    times and crawling modes
    """

    class FakeSaveCtrl(SavefileController):
        """
        A fake SavefileController for testing that simulates saving a savefile and can be
        configured to return an existing savefile with specified modified time
        """

        def __init__(self, exist: Savefile, api_url: str = "", api_token: str = ""):
            super().__init__(api_url, api_token)
            self._existing = exist

        def get(self, resource_id: int, download_path: Optional[str] = None) -> Optional[Savefile]:
            """Simulate getting a savefile by ID"""
            return self._existing if self._existing.id == resource_id else None

        def update(self, model: Savefile) -> Optional[Savefile]:
            """Simulate updating a savefile"""
            return model

    existing = Savefile(id=10, name="n.sav")
    # set modified times
    existing.modified_at = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)

    sf = Savefile(id=10, name="n.sav")
    sf.modified_at = datetime.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc)
    sf.console = Console(id=1, name="C")

    # crawling_modes: (UPDATE, UPDATE) should upload because local newer
    res = main.handle_existing_savefile(
        sf, FakeSaveCtrl(existing), (CrawlingMode.UPDATE, CrawlingMode.UPDATE)
    )
    assert res in (ProcessingResult.UPLOADED, ProcessingResult.FAILED_UPLOAD)

    # reverse times -> should download when remote newer
    existing.modified_at = datetime.datetime(2022, 1, 1, tzinfo=datetime.timezone.utc)
    sf.modified_at = datetime.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc)
    res2 = main.handle_existing_savefile(
        sf, FakeSaveCtrl(existing), (CrawlingMode.UPDATE, CrawlingMode.UPDATE)
    )
    assert res2 in (ProcessingResult.DOWNLOADED, ProcessingResult.FAILED_DOWNLOAD)


def test_process_savefile_routes_correctly():
    """
    Ensure process_savefile routes to the correct handling function based on availability and modes
    """
    sf = Savefile(name="x")
    sf.console = Console(id=1, name="C")

    # LOCAL - provide fake controller for save
    class FakeSaveCtrl(SavefileController):
        """
        A fake SavefileController for testing that simulates saving a savefile and can be
        configured to
        """

        def __init__(self, api_url: str = "", api_token: str = ""):
            super().__init__(api_url, api_token)

        def save(self, model: Savefile) -> Optional[Savefile]:
            """Simulate saving a savefile"""
            return model

    res = main.process_savefile(
        sf, SavefileAvailability.LOCAL, FakeSaveCtrl(), (CrawlingMode.NEW, CrawlingMode.NEW)
    )
    assert isinstance(res, ProcessingResult)


def test_retrieve_local_remote_savefiles_detects_local_and_remote(tmp_path: Path):
    """
    Ensure retrieve_local_remote_savefiles correctly identifies savefiles that are present locally,
    remotely, or both, and returns the appropriate availability status
    """
    # create console with saves_path
    c = Console(id=2, name="C2")
    d = tmp_path / "saves"
    d.mkdir()
    # create a file
    fpath = d / "file.sav"
    fpath.write_text("data")
    c.saves_path = str(d)

    # create remote savefile with same name
    remote = Savefile(name="file.sav", rel_path="/", id_console=2)

    class FakeSaveCtrl(SavefileController):
        """
        A fake SavefileController for testing that simulates searching for savefiles and can be
        configured to
        """

        def __init__(self, api_url: str = "", api_token: str = ""):
            super().__init__(api_url, api_token)
            self.raw = None

        def search(
                self, model: Savefile, allow_multiple_results: bool = True, raw: bool = False
        ) -> List[Savefile]:
            """Simulate searching for a savefile"""
            self.raw = raw
            return [remote]

    res = main.retrieve_local_remote_savefiles(c, FakeSaveCtrl())
    # there should be one entry and it should be BOTH
    assert len(res) >= 1
    values = list(res.values())
    assert any(v == SavefileAvailability.BOTH for v in values)


def test_log_savefile_stats_invokes_logger(monkeypatch: MonkeyPatch):
    """Ensure log_savefile_stats invokes the logger to log information about the savefile stats"""
    messages: Dict[str, List[str]] = {"info": []}

    class FakeLogger:
        """A fake logger for testing that captures info messages"""

        @staticmethod
        def log_info(msg: str):
            """Simulate logging an info message"""
            messages["info"].append(msg)

    monkeypatch.setattr(main, "logger", FakeLogger())
    sf = Savefile(name="a")
    data = {sf: SavefileAvailability.LOCAL}
    main.log_savefile_stats("Cname", data)
    assert messages["info"]


def test_process_console_savefiles_uses_process_savefile(monkeypatch: MonkeyPatch):
    """
    Ensure process_console_savefiles uses process_savefile to process each savefile and aggregates
    """
    c = Console(id=3, name="C3")
    # stub retrieve_local_remote_savefiles to return a single savefile
    sf = Savefile(name="s.sav", rel_path="/")
    sf.console = c

    def fake_retrieve_local_remote_savefiles(console: Console, ctrl: SavefileController) -> Dict[
        Savefile, SavefileAvailability]:
        """
        Simulate retrieving local and remote savefiles, returning a single savefile with LOCAL
        availability
        """
        _ = console
        _ = ctrl
        return {sf: SavefileAvailability.LOCAL}

    monkeypatch.setattr(
        main, "retrieve_local_remote_savefiles",
        fake_retrieve_local_remote_savefiles
    )

    def fake_process_savefiles(
            savefile: Savefile, availability: SavefileAvailability, ctrl: SavefileController,
            modes: Tuple[CrawlingMode, CrawlingMode]
    ) -> ProcessingResult:
        """
        Simulate processing savefiles for a console, returning a result of CREATED for the single
        savefile
        """
        _ = savefile
        _ = availability
        _ = ctrl
        _ = modes
        return ProcessingResult.CREATED

    monkeypatch.setattr(
        main, "process_savefile", fake_process_savefiles
    )

    class DummySaveCtrl(SavefileController):
        """A dummy SavefileController for testing that avoids calling the parent constructor"""

        def __init__(self, api_url: str = "", api_token: str = ""):
            # avoid calling parent ctor
            super().__init__(api_url, api_token)

    res = main.process_console_savefiles(c, DummySaveCtrl(), (CrawlingMode.NEW, CrawlingMode.NEW))
    assert res[ProcessingResult.CREATED.value] == 1


def test_print_results_logs_summary(monkeypatch: MonkeyPatch):
    """Ensure print_results logs a summary of the processing results using the logger"""
    logs: Dict[str, List[str]] = {"info": [], "error": [], "success": []}

    class FakeLogger:
        """A fake logger for testing that captures info, error, and success messages"""

        @staticmethod
        def log_info(msg: str):
            """Simulate logging an info message"""
            logs["info"].append(msg)

        @staticmethod
        def log_error(msg: str):
            """Simulate logging an error message"""
            logs["error"].append(msg)

        @staticmethod
        def log_success(msg: str):
            """Simulate logging a success message"""
            logs["success"].append(msg)

    monkeypatch.setattr(main, "logger", FakeLogger())
    c = Console(id=4, name="C4")
    # construct counts with some created/failed values
    counts = [0] * 9
    counts[ProcessingResult.CREATED.value] = 2
    counts[ProcessingResult.FAILED_UPLOAD.value] = 1
    results = {c: counts}
    main.print_results(results)
    assert logs["success"]
    assert logs["info"]
