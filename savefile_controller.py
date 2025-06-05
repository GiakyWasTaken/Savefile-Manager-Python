"""
Controller module for managing savefiles
Provides functionality to interact with savefile resources via API
"""

import os
from pathlib import Path
from typing import Any, Dict, Union, override

import requests

from controller_base import ControllerBase
from models import Savefile


class SavefileController(ControllerBase[Savefile]):
    """
    Controller for Savefile entities. Handles API interactions for savefile resources
    """

    def __init__(
        self, api_url: str, api_token: str, ssl_cert: Union[str, bool]
    ) -> None:
        super().__init__(api_url, api_token, ssl_cert, model_class=Savefile)

    @override
    def field_mapping(self) -> Dict[str, Any]:
        return {
            "id": "id",
            "file_name": "name",
            "file_path": "rel_path",
            "created_at": "created_at",
            "updated_at": "modified_at",
            "fk_id_console": "id_console",
        }

    @override
    def get_headers(
        self,
        accept: str = "application/json",
        content_type: str = "application/json",
    ) -> Dict[str, str]:
        headers = super().get_headers(accept, content_type)
        headers.pop("Content-Type", None)
        return headers

    @override
    def get(
        self, resource_id: int, download_file: bool = False
    ) -> Union[Savefile, None]:
        if not download_file:
            return super().get(resource_id)

        # Make a request to download the file
        url = f"{self.api_url}/{self.resource}/{resource_id}"
        headers = self.get_headers(accept="application/octet-stream")

        response = requests.get(
            url, headers=headers, verify=self.ssl_cert, stream=True, timeout=10
        )

        self.logger.log_debug(f"GET {url} - Response: {response.status_code}")

        if response.status_code != 200:
            self.logger.log_error(
                f"Failed to download {self.resource}: {response.status_code}"
            )
            return None

        # Get the savefile details to determine the path and filename
        savefile_model = super().get(resource_id)
        if not savefile_model:
            self.logger.log_error(
                f"Failed to get {self.resource} metadata for {resource_id}"
            )
            return None

        # Use model properties for filename and path
        filename = savefile_model.name or f"savefile_{resource_id}"
        relative_path = savefile_model.rel_path if savefile_model.rel_path else ""

        # Handle cases where path is just "/" or starts with "/"
        relative_path = relative_path.lstrip("/")

        # Create the Downloads directory structure
        base_dir = (
            Path(os.path.dirname(os.path.abspath(__file__)))
            / "Downloads"
            / relative_path
        )
        os.makedirs(base_dir, exist_ok=True)

        # Save the file
        file_path = base_dir / filename
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        self.logger.log_info(f"Downloaded {self.resource} {resource_id} to {file_path}")
        return savefile_model

    @override
    def save(self, model: Savefile) -> Union[Savefile, None]:
        url = f"{self.api_url}/{self.resource}"
        headers = self.get_headers()

        data = super().convert_to_json(model)

        response = requests.post(
            url,
            data=data,
            files={"savefile": model.savefile} if model.savefile else None,
            headers=headers,
            verify=self.ssl_cert,
            timeout=10,
        )
        result = None

        self.logger.log_debug(
            f"POST {url} - Response: {response.status_code} - {response.text}"
        )

        if response.status_code == 201:
            self.logger.log_info(f"Created new {self.resource}")
            result = super().convert_to_model(response.json())
            result = result[0] if isinstance(result, list) else result
        elif response.status_code == 409:
            self.logger.log_warning(
                f"Another {self.resource} with the same data already exists"
            )
        else:
            self.logger.log_error(
                f"Error creating {self.resource}: {response.status_code} - {response.text}"
            )

        return result

    @override
    def update(self, model: Savefile) -> Union[Savefile, None]:
        url = f"{self.api_url}/{self.resource}/{model.id}"
        headers = self.get_headers()

        data = super().convert_to_json(model)

        # PHP compatibility for PUT requests with multipart/form-data
        data["_method"] = "PUT"

        response = requests.post(
            url,
            data=data,
            files={"savefile": model.savefile} if model.savefile else None,
            headers=headers,
            verify=self.ssl_cert,
            timeout=10,
        )
        result = None

        self.logger.log_debug(
            f"PUT {url} - Response: {response.status_code} - {response.text}"
        )

        if response.status_code == 200:
            self.logger.log_info(f"Updated {self.resource} {model.id}")
            result = super().convert_to_model(response.json())
            result = result[0] if isinstance(result, list) else result
        elif response.status_code == 404:
            self.logger.log_warning(f"{self.resource} {model.id} not found")
        else:
            self.logger.log_error(
                f"Error updating {self.resource}: {response.status_code} - {response.text}"
            )

        return result
