"""
Controller module for managing consoles
Provides functionality to interact with console resources via API
"""

from typing import Any, Dict, Union, override
from controller_base import ControllerBase
from models import Console


class ConsoleController(ControllerBase[Console]):
    """
    Controller for Console entities. Handles API interactions for console resources
    """

    def __init__(
        self, api_url: str, api_token: str, ssl_cert: Union[str, bool]
    ) -> None:
        super().__init__(api_url, api_token, ssl_cert, model_class=Console)

    @override
    def field_mapping(self) -> Dict[str, Any]:
        return {
            "id": "id",
            "console_name": "name",
            "created_at": "created_at",
            "updated_at": "modified_at",
        }
