"""
Main module for the Savefile Manager application
Handles initialization and execution of the application
"""

from enum import Enum
import os
import re
import sys
from typing import Optional, Union

import dotenv
from auth_manager import AuthManager
from console_controller import ConsoleController
from logger import Logger, LogLevel
from models import Console, Savefile
from savefile_controller import SavefileController

logger = Logger(file_log_level=LogLevel.NONE, print_log_level=LogLevel.DEBUG)


def extract_bash_array(env_file_path: str, array_name: str) -> list[str]:
    """Extract a bash array from the .env file"""
    if not os.path.exists(env_file_path):
        return []

    with open(env_file_path, "r", encoding="utf-8") as f:
        env_content = f.read()

    # Pattern to match the array declaration and its values
    pattern = f"export {array_name}=\\(([^)]+)\\)"
    match = re.search(pattern, env_content, re.DOTALL)

    if not match:
        return []

    # Extract values and clean them
    raw_values = match.group(1).strip().split("\n")
    values: list[str] = []

    for line in raw_values:
        # Remove comments and empty lines
        cleaned = line.strip().strip("'\"")

        if cleaned and not cleaned.startswith("#"):
            values.append(cleaned)

    return values


def setup_env():
    """Set up environment variables and validate required ones"""
    dotenv_path = dotenv.find_dotenv()
    dotenv.load_dotenv(dotenv_path)

    api_url = os.getenv("API_URL", "").rstrip("/")
    email = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")
    ssl_cert = os.path.join(os.path.dirname(__file__), os.getenv("SSL_CERT_NAME", ""))

    if not ssl_cert:
        logger.log_warning("SSL certificate not provided, skipping SSL verification")
        ssl_cert = False

    if not email or not password:
        raise ValueError("EMAIL and PASSWORD must be set in the .env file")

    return dotenv_path, api_url, email, password, ssl_cert


def get_controllers(api_url: str, token: str, ssl_cert: Union[str, bool]):
    """Initialize and return controllers"""
    console_controller = ConsoleController(
        api_url=api_url, api_token=token, ssl_cert=ssl_cert
    )

    savefile_controller = SavefileController(
        api_url=api_url, api_token=token, ssl_cert=ssl_cert
    )

    return console_controller, savefile_controller


def get_crawling_mode():
    """Get the crawling mode from command line arguments"""
    match sys.argv[1:] if len(sys.argv) > 1 else [""]:
        case ["-u", *_]:
            crawling_mode = CrawlingMode.UPDATE
        case ["-f", *_]:
            crawling_mode = CrawlingMode.FORCE
        case ["-n", *_]:
            crawling_mode = CrawlingMode.NEW
        case ["-a", *_]:
            crawling_mode = CrawlingMode.ALL
        case _:
            crawling_mode = CrawlingMode.AUTO

    return crawling_mode


def retrieve_console(
    console_name: str, console_controller: ConsoleController, crawling_mode: Enum
) -> Optional[Console]:
    """Find or create console"""
    console = Console(name=console_name)
    result = console_controller.search(console)

    if not result and crawling_mode in (
        CrawlingMode.NEW,
        CrawlingMode.AUTO,
        CrawlingMode.ALL,
    ):
        result = console_controller.save(console)

    if isinstance(result, list):
        return result[0] if result else None
    return result


def _handle_new_savefile(
    savefile: Savefile, savefile_controller: SavefileController, crawling_mode: Enum
) -> str:
    """Handle a savefile that doesn't exist in the database yet"""
    if crawling_mode in (CrawlingMode.UPDATE, CrawlingMode.FORCE):
        return "Skipped"

    logger.log_info(
        f"Creating savefile '{savefile.name}' in console "
        f"{savefile.console.name if savefile.console else 'Unknown'}'"
    )
    result = savefile_controller.save(savefile)
    return "Created" if result else "Failed"


def _handle_existing_savefile(
    savefile: Savefile,
    savefile_id: int,
    savefile_controller: SavefileController,
    crawling_mode: Enum,
) -> str:
    """Handle a savefile that already exists in the database"""
    console_name = savefile.console.name if savefile.console else "Unknown"

    # Skip if we only want new files
    if crawling_mode == CrawlingMode.NEW:
        logger.log_info(
            f"Skipping savefile '{savefile.name}', "
            f"savefile already exists in console '{console_name}'"
        )
        return "Skipped"

    # For automatic update, check if update is needed
    if crawling_mode in (CrawlingMode.AUTO, CrawlingMode.UPDATE):
        existing_savefile = savefile_controller.get(savefile_id)

        if not existing_savefile:
            logger.log_info(
                f"Savefile '{savefile.name}' not found in console '{console_name}'"
            )
            return "Failed"

        if savefile.modified_at <= existing_savefile.modified_at:
            logger.log_info(
                f"Skipping savefile '{savefile.name}', "
                f"savefile is already up to date in console '{console_name}'"
            )
            return "Skipped"

    # Update the savefile
    logger.log_info(f"Updating savefile '{savefile.name}' in console '{console_name}'")
    result = savefile_controller.update(savefile_id, savefile)
    return "Updated" if result else "Failed"


def handle_savefile_updating(
    savefile: Savefile, savefile_controller: SavefileController, crawling_mode: Enum
) -> str:
    """Process a single savefile"""
    # Find if savefile exists
    search_result = savefile_controller.search(savefile)
    if isinstance(search_result, list):
        search_result = search_result[0] if search_result else None

    savefile_id = search_result.id if search_result else None

    # Handle based on whether the savefile exists
    if not savefile_id:
        return _handle_new_savefile(savefile, savefile_controller, crawling_mode)

    return _handle_existing_savefile(
        savefile, savefile_id, savefile_controller, crawling_mode
    )


def handle_save_downloading(
    remote_savefile: Savefile,
    local_path: str,
    savefile_controller: SavefileController,
    downloading_mode: Enum,
) -> str:
    """Download a savefile from the server"""
    local_savefile_path = os.path.join(
        local_path, remote_savefile.rel_path, remote_savefile.name
    )

    if os.path.exists(local_savefile_path):
        if downloading_mode == DownloadMode.NEW:
            logger.log_info(
                f"Skipping savefile '{remote_savefile.name}', "
                f"savefile already exists in local path '{local_savefile_path}'"
            )

            return "Skipped"

        if downloading_mode in (DownloadMode.AUTO, DownloadMode.UPDATE):
            existing_savefile = os.stat(local_savefile_path)

            if (
                existing_savefile.st_mtime >= float(remote_savefile.modified_at)
                if remote_savefile.modified_at
                else 0
            ):
                logger.log_info(
                    f"Skipping savefile '{remote_savefile.name}', "
                    f"savefile is already up to date in local path '{local_savefile_path}'"
                )
                return "Skipped"

    logger.log_info(
        f"Downloading savefile '{remote_savefile.name}' to local path '{local_savefile_path}'"
    )

    savefile = (
        savefile_controller.get(remote_savefile.id)
        if remote_savefile.id is not None
        else None
    )

    return "Downloaded" if savefile else "Failed"


def crawl_savefiles(
    console_names: list[str],
    saves_paths: list[str],
    console_controller: ConsoleController,
    savefile_controller: SavefileController,
    crawling_mode: Enum,
):
    """Process save paths and crawl savefiles"""

    def process_savefile(file: str, root: str, save_path: str, console: Console):
        rel_dir = os.path.relpath(root, save_path)
        savefile = Savefile(
            name=file, rel_path="/" if rel_dir == "." else f"{rel_dir}/"
        )
        savefile.console = console
        handle_savefile_updating(savefile, savefile_controller, crawling_mode)

    for i, save_path in enumerate(saves_paths):
        console_name = console_names[i]

        if not os.path.exists(save_path):
            logger.log_warning(f"Savefiles not found at {save_path}")
            return

        logger.log_info(f"Crawling '{console_name}' saves inside '{save_path}'")

        console = retrieve_console(console_name, console_controller, crawling_mode)

        if not console:
            return

        console.saves_path = save_path

        for root, dirs, files in os.walk(save_path):
            for dir_path in dirs:
                logger.log_info(f"Now entering dir: {os.path.join(root, dir_path)}")

            for file in files:
                process_savefile(file, root, save_path, console)


def _ensure_directory_exists(path: str):
    """Ensure directory exists, create if not"""
    if not os.path.exists(path):
        logger.log_info(f"Creating directory '{path}'")
        os.makedirs(path, exist_ok=True)


def _download_console_savefiles(
    console: Console,
    console_local_path: str,
    savefile_controller: SavefileController,
    downloading_mode: Enum,
):
    """Download savefiles for a specific console"""
    logger.log_info(f"Downloading savefiles for console '{console.name}'")

    remote_savefiles = savefile_controller.search(
        Savefile(id_console=console.id), multiple_search=True
    )
    if not remote_savefiles:
        return

    # Ensure result is a list
    savefiles_list = (
        remote_savefiles if isinstance(remote_savefiles, list) else [remote_savefiles]
    )

    for remote_savefile in savefiles_list:
        handle_save_downloading(
            remote_savefile,
            console_local_path,
            savefile_controller,
            downloading_mode,
        )


def download_savefiles(
    console_names: list[str],
    saves_paths: list[str],
    console_controller: ConsoleController,
    savefile_controller: SavefileController,
    downloading_mode: Enum,
):
    """Download savefiles from the server"""
    remote_consoles = console_controller.get_all()
    if not remote_consoles:
        return

    # Ensure result is a list
    consoles_list = (
        remote_consoles if isinstance(remote_consoles, list) else [remote_consoles]
    )

    for console in consoles_list:
        if console.name not in console_names:
            logger.log_info(
                f"Skipping console '{console.name}', console not present in local env"
            )
            continue

        console_local_path = saves_paths[console_names.index(console.name)]
        _ensure_directory_exists(console_local_path)
        _download_console_savefiles(
            console, console_local_path, savefile_controller, downloading_mode
        )


class CrawlingMode(Enum):
    """Enum for crawling modes"""

    # Uploads only already existing savefiles by last modified date
    UPDATE = 1

    # Uploads every already existing savefile
    FORCE = 2

    # Uploads only new savefiles and ignores existing ones
    NEW = 3

    # Uploads new savefiles and updates existing ones by last modified date
    AUTO = 4

    # Uploads every savefile present in the directory
    ALL = 5


class DownloadMode(Enum):
    """Enum for download modes"""

    # Downloads only already existing savefiles by last modified date
    UPDATE = 1

    # Downloads every already existing savefile
    FORCE = 2

    # Downloads only new savefiles and ignores existing ones
    NEW = 3

    # Downloads new savefiles and updates existing ones by last modified date
    AUTO = 4

    # Downloads every savefile present in the directory
    ALL = 5


def main():
    """
    Main entry point of the application. Initializes the logger, loads environment
    variables, authenticates the user, and performs operations using controllers
    """
    dotenv_path, api_url, email, password, ssl_cert = setup_env()

    token = AuthManager.login(api_url, email, password, ssl_cert)

    if not token:
        token = AuthManager.register(api_url, "giaky", email, password, ssl_cert)
        if not token:
            logger.log_error("Failed to authenticate or register")
            return

    logger.log_info("Login successful")

    console_controller, savefile_controller = get_controllers(api_url, token, ssl_cert)

    console_names, saves_paths = [
        extract_bash_array(dotenv_path, name)
        for name in ["CONSOLE_NAMES", "SAVES_PATHS"]
    ]

    if len(console_names) != len(saves_paths):
        logger.log_error(
            "CONSOLE_NAMES and SAVES_PATHS arrays must have the same length"
        )

        return

    crawling_mode = get_crawling_mode()

    crawl_savefiles(
        console_names,
        saves_paths,
        console_controller,
        savefile_controller,
        crawling_mode,
    )

    AuthManager.logout(api_url, token, ssl_cert)
    print("end")


if __name__ == "__main__":
    main()
