"""Unit tests for the Models module"""

import os

from models import Console, Savefile

CONSOLE_NAME = "Test Console"
SAVEFILE_NAME = "Test Savefile"
CREATED_AT = "2024-01-01T12:00:00.000000Z"
MODIFIED_AT = "2024-01-02T12:00:00.000000Z"
CONSOLE_PATH = "/path/to/console/"
SAVEFILE_PATH = "/savefiles"


def test_model_from_json():
    """
    Test the from_json method of the Model class
    """

    json_data = {
        "id": 1,
        "name": CONSOLE_NAME,
        "created_at": CREATED_AT,
        "modified_at": MODIFIED_AT,
        "saves_path": CONSOLE_PATH,
    }

    console_fj = Console()
    console_fj.from_json(json_data)

    assert console_fj.id == 1
    assert console_fj.name == CONSOLE_NAME
    assert console_fj.created_at == CREATED_AT
    assert console_fj.modified_at == MODIFIED_AT
    assert console_fj.saves_path == CONSOLE_PATH


def test_model_from_json_fails():
    """
    Test the from_json method of the Model class with invalid data
    """

    json_data = {
        "id": "invalid_id",
        "name": CONSOLE_NAME,
        "created_at": "invalid_date",
        "modified_at": "2024-01-02T12:00:00.000000Z",
        "saves_path": CONSOLE_PATH,
    }

    console_fjf = Console()

    try:
        console_fjf.from_json(json_data)
        assert False, "from_json should have raised an exception for invalid data"
    except (ValueError, TypeError):
        pass

    json_data["id"] = "2"
    json_data["created_at"] = CREATED_AT
    json_data["non_existent_field"] = "value"

    try:
        console_fjf.from_json(json_data)
        assert False, "from_json should have raised an exception for non-existent field"
    except ValueError:
        pass


def test_console_to_json():
    """
    Test the to_json method of the Console class
    """

    console_tj = Console(
        id=1,
        name=CONSOLE_NAME,
        saves_path=CONSOLE_PATH,
    )
    console_tj.created_at = CREATED_AT
    console_tj.modified_at = MODIFIED_AT

    json_data = console_tj.to_json()

    assert json_data["id"] == 1
    assert json_data["name"] == CONSOLE_NAME
    assert json_data["created_at"] == CREATED_AT
    assert json_data["modified_at"] == MODIFIED_AT
    assert json_data["saves_path"] == CONSOLE_PATH


def test_console_equality_and_hash():
    """
    Test the equality and hashing of Console instances
    """

    console1 = Console(id=1, name="Console A")
    console2 = Console(id=1, name="Console B")
    console3 = Console(id=2, name="Console A")
    console4 = Console(id=2, name="Console C")

    assert console1 == console2  # Same id
    assert console1 == console3  # Same name
    assert console1 != console4  # Different id and name

    console_set = {console1, console4}
    assert console2 not in console_set  # console2 has same id as console1 but different name
    assert console3 in console_set  # console3 has same name as console1


def test_savefile_from_json():
    """
    Test the from_json method of the Savefile class
    """
    json_data = {
        "id": "1",
        "name": SAVEFILE_NAME,
        "created_at": CREATED_AT,
        "modified_at": MODIFIED_AT,
        "rel_path": SAVEFILE_PATH,
        "console": {
            "id": "1",
            "name": CONSOLE_NAME,
            "created_at": CREATED_AT,
            "modified_at": MODIFIED_AT,
            "saves_path": CONSOLE_PATH,
        }
    }

    savefile_fj = Savefile()
    savefile_fj.from_json(json_data)

    assert savefile_fj.id == "1"
    assert savefile_fj.name == SAVEFILE_NAME
    assert savefile_fj.created_at == CREATED_AT
    assert savefile_fj.modified_at == MODIFIED_AT
    assert savefile_fj.rel_path == SAVEFILE_PATH
    assert savefile_fj.abs_path == os.path.join(
        CONSOLE_PATH, SAVEFILE_PATH.lstrip("/"), SAVEFILE_NAME
    )
    assert savefile_fj.id_console == "1"


def test_savefile_to_json():
    """
    Test the to_json method of the Savefile class
    """

    console = Console(
        id=1,
        name=CONSOLE_NAME,
        saves_path=CONSOLE_PATH,
    )
    console.created_at = CREATED_AT
    console.modified_at = MODIFIED_AT

    savefile_tj = Savefile(
        id=1,
        name=SAVEFILE_NAME,
        rel_path=SAVEFILE_PATH,
    )
    savefile_tj.console = console
    savefile_tj.created_at = CREATED_AT
    savefile_tj.modified_at = MODIFIED_AT

    json_data = savefile_tj.to_json()

    assert json_data["id"] == 1
    assert json_data["name"] == SAVEFILE_NAME
    assert json_data["created_at"] == CREATED_AT
    assert json_data["modified_at"] == MODIFIED_AT
    assert json_data["rel_path"] == SAVEFILE_PATH
    assert json_data["console"] == console.to_json()
