"""
Base controller module for API interactions
Provides generic methods for CRUD operations on resources
"""

from abc import ABC
from typing import Any, Dict, List, Optional, Generic, TypeVar, Type, Union
import requests
from logger import Logger
from models import Entity

T = TypeVar("T", bound=Entity)


class ControllerBase(ABC, Generic[T]):
    """
    Abstract base class for controllers. Implements generic CRUD operations
    and provides utility methods for API interactions
    """

    def __init__(
        self,
        api_url: str,
        api_token: str,
        ssl_cert: Union[str, bool],
        model_class: Type[T],
    ) -> None:
        self.api_url = api_url
        self.api_token = api_token
        self.ssl_cert = ssl_cert
        self.model_class = model_class
        self.resource = (
            model_class.__name__.lower()
            if model_class
            else self.__class__.__name__.lower()
        )
        self.logger = Logger(
            model_class.__name__ if model_class else self.__class__.__name__
        )

    def get_headers(self, pop_content_type: bool = False) -> Dict[str, str]:
        """
        Generate headers for API requests

        Returns:
            Dict[str, str]: Dictionary containing headers for API requests
        """
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if pop_content_type:
            headers.pop("Content-Type", None)

        return headers

    def field_mapping(self) -> Dict[str, Any]:
        """
        Define the mapping between API fields and model fields

        Returns:
            Dict[str, Any]: Dictionary mapping API fields to model fields
        """
        return {}

    def mapper(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map API response data to model fields

        Args:
            data (Dict[str, Any]): API response data

        Returns:
            Dict[str, Any]: Mapped data with model field names
        """
        mapped_data: Dict[str, Any] = {}

        for key, value in data.items():
            if key in self.field_mapping():
                mapped_key = self.field_mapping()[key]
                mapped_data[mapped_key] = value

        return mapped_data

    def convert_to_model(
        self, data: Union[List[Dict[str, Any]], Dict[str, Any]]
    ) -> Union[List[T], T]:
        """
        Convert API response data to a model instance

        Args:
            data (Any): API response data

        Returns:
            Union[List[T], T]: Model instance or list of model instances
        """
        model = None

        if self.model_class:
            if isinstance(data, dict):
                instance = self.model_class()
                instance.from_json(self.mapper(data))

                model = instance
            else:
                result: List[T] = []

                for item in data:
                    instance = self.model_class()
                    instance.from_json(self.mapper(item))
                    result.append(instance)

                model = result
        else:
            raise ValueError("Model class not defined")

        return model

    def convert_to_json(self, model: T) -> Dict[str, Any]:
        """
        Convert a model instance to JSON format for API requests

        Args:
            model (T): Model instance

        Returns:
            Dict[str, Any]: JSON representation of the model
        """
        if self.model_class:
            json_model = model.to_json()
            mapped_json: Dict[str, Any] = {}

            reverse_mapping = {v: k for k, v in self.field_mapping().items()}

            # Define serializable types
            serializable_types = (type(None), bool, int, float, str, list, Dict)

            for key, value in json_model.items():
                if value is None:
                    continue

                # Only include serializable values
                if isinstance(value, serializable_types) and key in reverse_mapping:
                    mapped_key = reverse_mapping[key]
                    mapped_json[mapped_key] = value
        else:
            raise ValueError("Model class not defined")

        return mapped_json

    def get(self, resource_id: int) -> Optional[T]:
        """
        Retrieve a single resource by its ID

        Args:
            resource_id (int): ID of the resource to retrieve

        Returns:
            Optional[T]: Retrieved resource as a model instance, or None if not found
        """
        url = f"{self.api_url}/{self.resource}/{resource_id}"
        headers = self.get_headers()

        response = requests.get(url, headers=headers, verify=self.ssl_cert, timeout=10)
        result = None

        self.logger.log_debug(
            f"GET {url} - Response: {response.status_code} - {response.text}"
        )

        if response.status_code == 200:
            self.logger.log_info(f"Fetched {self.resource} with ID {resource_id}")
            result = self.convert_to_model(response.json())
            result = result[0] if isinstance(result, list) else result
        elif response.status_code == 404:
            self.logger.log_warning(
                f"{self.resource.capitalize()} with ID {resource_id} not found"
            )
        else:
            self.logger.log_error(
                f"Error fetching {self.resource} with ID {resource_id}: "
                f"{response.status_code} - {response.text}"
            )

        return result

    def get_all(self) -> Union[List[T], T, None]:
        """
        Retrieve all resources of the specified type

        Returns:
            Union[List[T], T, None]: List of all resources as model instances, or None if not found
        """
        url = f"{self.api_url}/{self.resource}"
        headers = self.get_headers()

        response = requests.get(url, headers=headers, verify=self.ssl_cert, timeout=10)
        result = None

        self.logger.log_debug(
            f"GET {url} - Response: {response.status_code} - {response.text}"
        )

        if response.status_code == 200:
            self.logger.log_info(f"Fetched all {self.resource}s")
            result = self.convert_to_model(response.json()) if response.json() else []
        else:
            self.logger.log_error(
                f"Error fetching all {self.resource}s: {response.status_code} - {response.text}"
            )

        return result

    def search(
        self, model: T, multiple_search: bool = False
    ) -> Union[list[T], T, None]:
        """
        Search for a resource matching the given model

        Args:
            model (T): Model instance with search criteria
            multiple_search (bool): Whether to search for multiple resources

        Returns:
            Optional[T]: Matching resource as a model instance, or None if not found
        """
        model_json = self.convert_to_json(model)

        self.logger.log_debug(f"Searching for {model_json} in {self.resource}")

        all_items = self.get_all()

        if not all_items:
            return None

        result: List[T] = []

        for item in all_items if isinstance(all_items, list) else [all_items]:
            if self._have_same_values(model_json, self.convert_to_json(item)):
                result.append(item)

        if len(result) == 1:
            self.logger.log_info(
                f"Found matching {self.resource} with Id {result[0].id}"
            )

            return result[0]

        if len(result) > 1:
            self.logger.log_warning(
                f"Multiple {self.resource}s found with values {model_json}"
            )

            return result if multiple_search else None

        self.logger.log_warning(
            f"{self.resource.capitalize()} with values {model_json} not found"
        )

        return None

    def save(self, model: T) -> Optional[T]:
        """
        Save a new resource to the API

        Args:
            model (T): Model instance to save

        Returns:
            Optional[T]: Saved resource as a model instance, or None if an error occurs
        """
        url = f"{self.api_url}/{self.resource}"
        headers = self.get_headers()

        data = self.convert_to_json(model)

        response = requests.post(
            url, json=data, headers=headers, verify=self.ssl_cert, timeout=10
        )
        result = None

        self.logger.log_debug(
            f"POST {url} - Response: {response.status_code} - {response.text}"
        )

        if response.status_code == 201:
            self.logger.log_info(f"Created new {self.resource}")
            result = self.convert_to_model(response.json())
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

    def update(self, resource_id: int, model: T) -> Optional[T]:
        """
        Update an existing resource by its ID

        Args:
            resource_id (int): ID of the resource to update
            model (T): Model instance with updated data

        Returns:
            Optional[T]: Updated resource as a model instance, or None if an error occurs
        """
        url = f"{self.api_url}/{self.resource}/{resource_id}"
        headers = self.get_headers()

        data = self.convert_to_json(model)

        response = requests.put(
            url, json=data, headers=headers, verify=self.ssl_cert, timeout=10
        )
        result = None

        self.logger.log_debug(
            f"PUT {url} - Response: {response.status_code} - {response.text}"
        )

        if response.status_code in (200, 204):
            self.logger.log_info(f"Updated {self.resource} with ID {resource_id}")
            result = self.convert_to_model(response.json())
            result = result[0] if isinstance(result, list) else result
        elif response.status_code == 404:
            self.logger.log_warning(
                f"{self.resource.capitalize()} with ID {resource_id} not found"
            )
        elif response.status_code == 409:
            self.logger.log_warning(
                f"Another {self.resource} with the same data already exists"
            )
        else:
            self.logger.log_error(
                f"Error updating {self.resource} with ID {resource_id}: "
                f"{response.status_code} - {response.text}"
            )

        return result

    def delete(self, resource_id: int) -> bool:
        """
        Delete a resource by its ID

        Args:
            resource_id (int): ID of the resource to delete

        Returns:
            bool: True if the resource was successfully deleted, False otherwise
        """
        url = f"{self.api_url}/{self.resource}/{resource_id}"
        headers = self.get_headers()

        response = requests.delete(
            url, headers=headers, verify=self.ssl_cert, timeout=10
        )
        result = False

        self.logger.log_debug(
            f"DELETE {url} - Response: {response.status_code} - {response.text}"
        )

        if response.status_code in (200, 204):
            self.logger.log_info(f"Deleted {self.resource} with ID {resource_id}")
            result = True
        elif response.status_code == 404:
            self.logger.log_warning(
                f"{self.resource.capitalize()} with ID {resource_id} not found"
            )
        else:
            self.logger.log_error(
                f"Error deleting {self.resource} with ID {resource_id}: "
                f"{response.status_code} - {response.text}"
            )

        return result

    def _have_same_values(
        self, model_json: Dict[str, Any], item_json: Dict[str, Any]
    ) -> bool:
        """
        Check if an item matches the search criteria

        Args:
            model_json (Dict[str, Any]): JSON representation of the model to search for
            item_json (Dict[str, Any]): JSON representation of the item to compare

        Returns:
            bool: True if the item matches the search criteria, False otherwise
        """
        for attr, value in model_json.items():
            if value is None or "_at" in attr:
                continue
            if attr not in item_json or item_json[attr] != value:
                return False

        return True
