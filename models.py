"""
Data models for the Savefile Manager application
Defines entities and their properties for API interactions
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BufferedReader
import os
from typing import Dict, Optional, Union


DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.000000Z"


@dataclass
class Entity:
    """
    Base class for all entities. Provides common attributes and methods for serialization
    """

    id: Optional[int] = None
    name: str = ""
    _created_at: Optional[datetime] = None
    _modified_at: Optional[datetime] = None

    @property
    def created_at(self) -> str:
        """
        Get the creation timestamp of the entity

        Returns:
            str: Creation timestamp
        """
        return self._created_at.strftime(DATE_FORMAT) if self._created_at else ""

    @created_at.setter
    def created_at(self, value: datetime) -> None:
        """
        Set the creation timestamp of the entity

        Args:
            value (datetime): Creation timestamp
        """
        if isinstance(value, str):
            self._created_at = datetime.strptime(value, DATE_FORMAT)
        elif isinstance(value, (float, int)):
            self._created_at = datetime.fromtimestamp(value)
        else:
            self._created_at = value

    @property
    def modified_at(self) -> str:
        """
        Get the modification timestamp of the entity

        Returns:
            str: Modification timestamp
        """
        return self._modified_at.strftime(DATE_FORMAT) if self._modified_at else ""

    @modified_at.setter
    def modified_at(self, value: Union[datetime, str, float, int, None]) -> None:
        """
        Set the modification timestamp of the entity

        Args:
            value (Union[datetime, str, float, int, None]): Modification timestamp
        """
        if isinstance(value, str):
            self._modified_at = datetime.strptime(value, DATE_FORMAT)
        elif isinstance(value, (float, int)):
            self._modified_at = datetime.fromtimestamp(value)
        else:
            self._modified_at = value

    def to_json(self) -> Dict[str, object]:
        """
        Convert the entity to a JSON-serializable dictionary, including properties.

        Returns:
            Dict: JSON representation of the entity
        """
        result: Dict[str, object] = {}
        result.update(self._get_instance_vars())
        result.update(self._get_properties(result))
        return result

    def _get_instance_vars(self) -> Dict[str, object]:
        """
        Helper to get instance variables (excluding private ones) for JSON serialization.
        """
        instance_vars: Dict[str, object] = {}
        for key, value in self.__dict__.items():
            if not key.startswith("_") and value is not None:
                instance_vars[key] = (
                    value.isoformat() if isinstance(value, datetime) else value
                )
        return instance_vars

    def _get_properties(self, existing: Dict[str, object]) -> Dict[str, object]:
        """
        Helper to get property values for JSON serialization, skipping those already in existing.
        """
        props: Dict[str, object] = {}
        for attr in dir(self.__class__):
            prop = getattr(self.__class__, attr)
            if isinstance(prop, property) and attr not in existing:
                value = getattr(self, attr)
                if value is not None:
                    props[attr] = (
                        value.isoformat() if isinstance(value, datetime) else value
                    )
        return props

    def from_json(self, data: Dict[str, object]) -> None:
        """
        Populate the entity's attributes from a JSON dictionary

        Args:
            data (Dict[str, object]): JSON dictionary containing entity data
        """
        for key, value in data.items():
            if hasattr(self.__class__, key) and isinstance(
                getattr(self.__class__, key), property
            ):
                setattr(self, key, value)
            elif hasattr(self, key):
                attr = getattr(self, key)
                if isinstance(attr, datetime):
                    if isinstance(value, str):
                        setattr(self, key, datetime.strptime(value, DATE_FORMAT))
                    else:
                        setattr(self, key, value)
                else:
                    setattr(self, key, value)
            else:
                raise ValueError(
                    f"Invalid attribute {key} for {self.__class__.__name__}"
                )


@dataclass
class Console(Entity):
    """
    Represents a Console entity with attributes inherited from Entity
    """

    saves_path: Optional[str] = None

    def __hash__(self) -> int:
        """
        Create a hash for the console based on its id.

        Returns:
            int: Hash value for the console
        """
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        """
        Check if two consoles are equal based on their id or name.

        Args:
            other: The other object to compare the console with

        Returns:
            bool: True if the consoles are equal, False otherwise
        """
        if not isinstance(other, Console):
            return False
        return self.id == other.id or self.name == other.name


@dataclass
class Savefile(Entity):
    """
    Represents a Savefile entity with additional attributes for path and console ID
    """

    rel_path: str = ""
    id_console: Optional[int] = None
    _console: Optional[Console] = None

    @property
    def abs_path(self) -> Optional[str]:
        """
        Get the absolute path of the savefile

        Returns:
            str: Absolute path of the savefile
        """
        if self.console and self.console.saves_path and self.rel_path and self.name:
            rel_path = self.rel_path.lstrip("/") if self.rel_path else ""
            return os.path.join(self.console.saves_path, rel_path, self.name)
        return None

    @property
    def modified_at(self) -> str:
        """
        Get the modification timestamp of the savefile

        Returns:
            str: Modification timestamp
        """
        if super().modified_at:
            return super().modified_at

        if self.abs_path and os.path.exists(self.abs_path):
            return datetime.fromtimestamp(
                os.path.getmtime(self.abs_path), timezone.utc
            ).strftime(DATE_FORMAT)

        return ""

    @modified_at.setter
    def modified_at(self, value: Union[datetime, str, float, int, None]) -> None:
        """
        Set the modification timestamp of the entity

        Args:
            value (Union[datetime, str, float, int, None]): Modification timestamp
        """
        if isinstance(value, str):
            self._modified_at = datetime.strptime(value, DATE_FORMAT)
        elif isinstance(value, (float, int)):
            self._modified_at = datetime.fromtimestamp(value)
        else:
            self._modified_at = value

    @property
    def console(self) -> Optional[Console]:
        """
        Get the console attribute of the savefile

        Returns:
            Console: Console object associated with the savefile
        """
        return self._console if self._console else None

    @console.setter
    def console(self, value: Console) -> None:
        """
        Set the console attribute of the savefile

        Args:
            value (Console): Console object to associate with the savefile
        """
        self._console = value
        self.id_console = value.id

    @property
    def savefile(self) -> Optional[BufferedReader]:
        """
        Get the savefile content as a file-like object.

        Returns:
            BufferedReader: File-like object containing the savefile content
        """
        if self.abs_path and os.path.exists(self.abs_path):
            return open(self.abs_path, "rb")

        return None

    @savefile.setter
    def savefile(self, content: bytes) -> bool:
        """
        Write content to the savefile in the file system.

        Args:
            content (bytes): The content to write to the savefile.

        Returns:
            bool: True if the savefile was successfully written, False otherwise.
        """
        if not self.abs_path or not os.path.exists(self.abs_path):
            return False

        with open(self.abs_path, "wb") as file:
            file.write(content)
        return True

    def __hash__(self) -> int:
        """
        Create a hash for the savefile based on name, rel_path and id_console.

        Returns:
            int: Hash value for the savefile
        """
        return hash((self.name, self.rel_path, self.id_console))

    def __eq__(self, other: object) -> bool:
        """
        Check if two savefiles are equal based on their id, name, rel_path, and id_console.

        Args:
            other: The other object to compare with

        Returns:
            bool: True if the savefiles are equal, False otherwise
        """
        if not isinstance(other, Savefile):
            return False
        return self.id == other.id or (
            self.name == other.name
            and self.rel_path == other.rel_path
            and self.id_console == other.id_console
        )
