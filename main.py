"""
Main module for the Savefile Manager application
Handles initialization and execution of the application
"""

import argparse
from enum import Enum
import os
import re
import shutil
from typing import Optional, Any, Tuple

import dotenv
from tqdm import tqdm
from auth_manager import AuthManager
from console_controller import ConsoleController
from local_ssl_context import LocalSSLContext
from logger import Logger, LogLevel
from models import Console, Savefile
from savefile_controller import SavefileController


# Load dotenv once at module level
ENV_FILE_PATH = dotenv.find_dotenv()
dotenv.load_dotenv(ENV_FILE_PATH)


class CrawlingMode(Enum):
    """
    Enum representing different modes for crawling and downloading savefiles

    Attributes:
        NONE: No crawling, just skip
        UPDATE: Uploads or Downloads only already existing savefiles by last modified date
        FORCE: Uploads or Downloads every already existing savefile
        NEW: Uploads or Downloads only new savefiles and ignores existing ones
        AUTO: Uploads or Downloads new savefiles and updates existing ones by last modified date
        ALL: Uploads or Downloads every savefile present in the directory

    """

    NONE = 0
    UPDATE = 1
    FORCE = 2
    NEW = 3
    AUTO = 4
    ALL = 5


class SavefileAvailability(Enum):
    """
    Enum representing the availability of a savefile

    Attributes:
        LOCAL: Savefile exists only locally
        REMOTE: Savefile exists only remotely
        BOTH: Savefile exists both locally and remotely
    """

    LOCAL = 0
    REMOTE = 1
    BOTH = 2


class ProcessingResult(Enum):
    """
    Enum representing the result of processing a savefile

    Attributes:
        CONSOLE_FAILED: Failed to process the console
        IGNORED: Savefile was ignored (not processed due to mode settings)
        SKIPPED: Savefile was skipped (not uploaded or downloaded)
        CREATED: Savefile was created successfully
        UPLOADED: Remote savefile was updated successfully
        DOWNLOADED: Savefile was downloaded successfully
        FAILED_CREATION: Failed to create the savefile
        FAILED_UPLOAD: Failed to update the remote savefile
        FAILED_DOWNLOAD: Failed to download the savefile
    """

    CONSOLE_FAILED = 0
    IGNORED = 1
    SKIPPED = 2
    CREATED = 3
    UPLOADED = 4
    DOWNLOADED = 5
    FAILED_CREATION = 6
    FAILED_UPLOAD = 7
    FAILED_DOWNLOAD = 8


parser = argparse.ArgumentParser(description="Savefile Manager Scripts")


def get_logger_level() -> Logger:
    """
    Get the logger level based on command line arguments.

    Returns:
        Logger: Logger instance with the specified log level.
    """

    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity level (-v for INFO, -vv for DEBUG)",
    )
    args, _ = parser.parse_known_args()

    verbosity_map = {
        0: LogLevel.WARNING,
        1: LogLevel.INFO,
        2: LogLevel.DEBUG,
    }

    log_level = verbosity_map.get(args.verbose, LogLevel.INFO)
    logs_path = os.getenv("LOGS_PATH") or "logs"

    return Logger(logs_path=logs_path, print_log_level=log_level)


logger = get_logger_level()


def fit_text_to_width(width: int, name: str, path: str = "") -> str:
    """Fit the given text to the specified width, truncating or padding as necessary

    Args:
        width (int): The width to fit the text within
        name (str): The name to fit
        path (str): The relative path to include in the fitting

    Returns:
        str: The fitted text
    """

    # If full path + name fits exactly or with padding, return it
    full = f"{path}{name}"
    if len(full) <= width:
        pad = width - len(full)
        return full + " " * pad

    # Collapse path first: "/" stays "/", anything else becomes "…/"
    collapsed = "/" if path == "/" else "…/"

    # Try collapsed path + full name
    if collapsed and len(collapsed) + len(name) <= width:
        out = collapsed + name
        needed = max(0, width - len(out))
        res = path[:needed] + out
        if len(res) < width:
            res += " " * (width - len(res))
        return res

    # Need to truncate the name as well
    avail_for_name = max(0, width - len(collapsed))

    if avail_for_name <= 1:
        return "…"[:avail_for_name] + "/…"[-width:] if width > 0 else ""

    # Truncate filename on the right
    if len(name) > avail_for_name:
        truncated = name[: avail_for_name - 1] + "…"
    else:
        truncated = name

    out = collapsed + truncated
    if len(out) < width:
        out += " " * (width - len(out))
    return out


def set_sized_description(pbar: Any, text: str, rel_path: str = "") -> None:
    """Set the description of a progress bar to a truncated version of the text

    Args:
        pbar (Any): The progress bar to update
        text (str): The text to set as the description
        rel_path (str, optional): The relative path to prepend to the text
    """

    extra = getattr(pbar, "_two_line_extra_width", None)

    if extra is None:
        pbar.set_description(fit_text_to_width(50, text, rel_path))
        return

    try:
        term_cols = shutil.get_terminal_size(fallback=(80, 24)).columns
    except AttributeError:
        term_cols = 80

    max_len = max(0, term_cols - int(extra))

    pbar.set_description(fit_text_to_width(max_len, text, rel_path))


def create_progress_bars(total: int, is_console: bool) -> Tuple[Any, Optional[Any]]:
    """Create progress bars for console or savefile processing

    Args:
        total (int): The total number of items to process
        is_console (bool): Whether the progress bars are for console or savefile processing

    Returns:
        Tuple[Any, Optional[Any]]: The primary and secondary progress bars
    """

    stats = "{n_fmt:>3}/{total_fmt:>3}[{elapsed:>5}<{remaining:>5},{rate_fmt:>15}]"

    common_kwargs: dict[str, Any] = {
        "total": total,
        "leave": is_console,
        "dynamic_ncols": True,
        "file": None,
        "miniters": 1,
        "mininterval": 0.1,
        "smoothing": 0.1,
    }

    if shutil.get_terminal_size(fallback=(80, 24)).columns > 99:
        unit = "console" if is_console else "savefile"
        desc = fit_text_to_width(
            50, "Processing: " + ("consoles" if is_console else "savefiles")
        )

        bar_format = "{l_bar}{bar}| " + stats

        progress_bar = tqdm(
            bar_format=bar_format, desc=desc, unit=unit, **common_kwargs
        )
        pbar_2nd = None
    else:
        unit = "con" if is_console else "sav"

        stats = stats.replace("{rate_fmt:>15}", "{rate_fmt:>10}")

        primary_format = "{desc}|" + stats

        # Precompute the real width used by the stats segment to reserve space for desc
        stats_example = stats.format(
            n_fmt="000",
            total_fmt="000",
            elapsed="00:00",
            remaining="00:00",
            rate_fmt="".ljust(10),
        )

        # Reserve total extra width (separator + stats) so desc can take remaining columns
        extra_width = len(": |") + len(stats_example)

        progress_bar = tqdm(bar_format=primary_format, unit=unit, **common_kwargs)

        # Mark this bar as the two-line top bar and store reserved width
        setattr(progress_bar, "_two_line_extra_width", extra_width)

        # Ensure initial desc uses maximum available width
        set_sized_description(progress_bar, "")

        percentage_format = "{percentage:3.0f}% |{bar}"

        pbar_2nd = tqdm(bar_format=percentage_format, unit=unit, **common_kwargs)

    return progress_bar, pbar_2nd


def extract_bash_array(env_file_path: str, array_name: str) -> list[str]:
    """
    Extracts a bash array from a .env file

    Args:
        env_file_path (str): Path to the .env file
        array_name (str): Name of the array to extract

    Returns:
        list[str]: List of values in the array, cleaned of comments and empty lines
    """

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


def setup_env() -> tuple[list[str], list[str], str, tuple[CrawlingMode, CrawlingMode]]:
    """
    Load environment variables from the .env file and return necessary configurations

    Returns:
        tuple: Tuple containing console names, saves paths, API URL and crawling modes
    """

    api_url = os.getenv("API_URL", "").rstrip("/")

    if not os.getenv("EMAIL") or not os.getenv("PASSWORD"):
        raise ValueError("EMAIL and PASSWORD must be set in the .env file")

    console_names, saves_paths = [
        extract_bash_array(ENV_FILE_PATH, name)
        for name in ["CONSOLE_NAMES", "SAVES_PATHS"]
    ]

    LocalSSLContext.set_api_url(api_url)

    crawling_modes = get_crawling_downloading_mode()

    return console_names, saves_paths, api_url, crawling_modes


def get_controllers(
    api_url: str, token: str
) -> tuple[ConsoleController, SavefileController]:
    """
    Initialize and return ConsoleController and SavefileController instances

    Args:
        api_url (str): API URL for the controllers
        token (str): Authentication token for the API

    Returns:
        tuple: Tuple containing ConsoleController and SavefileController instances
    """

    console_controller = ConsoleController(api_url=api_url, api_token=token)

    savefile_controller = SavefileController(api_url=api_url, api_token=token)

    return console_controller, savefile_controller


def get_crawling_downloading_mode() -> tuple[CrawlingMode, CrawlingMode]:
    """
    Parse command line arguments to get crawling and downloading modes

    Returns:
        tuple[CrawlingMode, CrawlingMode]: Tuple containing crawling mode and downloading mode
    """

    parser.add_argument(
        "-c",
        "--crawl",
        choices=["u", "f", "n", "a", "l"],
        default="none",
        help="Crawling mode (u=update, f=force, n=new, a=auto, l=all)",
    )

    parser.add_argument(
        "-d",
        "--download",
        choices=["u", "f", "n", "a", "l"],
        default="none",
        help="Downloading mode (u=update, f=force, n=new, a=auto, l=all)",
    )
    args = parser.parse_args()

    # Mapping shortcut to Enum
    shortcut_map = {
        "u": CrawlingMode.UPDATE,
        "f": CrawlingMode.FORCE,
        "n": CrawlingMode.NEW,
        "a": CrawlingMode.AUTO,
        "l": CrawlingMode.ALL,
        "none": CrawlingMode.NONE,
    }

    crawl_mode = shortcut_map[args.crawl]
    downloading_mode = shortcut_map[args.download]

    if crawl_mode == CrawlingMode.NONE and downloading_mode == CrawlingMode.NONE:
        logger.log_info(
            "Both crawling and downloading modes aren't set. "
            "Defaulting to AUTO for crawling mode and downloading mode."
        )
        crawl_mode = CrawlingMode.AUTO
        downloading_mode = CrawlingMode.AUTO

    logger.log_info(f"Crawling mode selected: {crawl_mode.name}")
    logger.log_info(f"Downloading mode selected: {downloading_mode.name}")

    return crawl_mode, downloading_mode


def retrieve_local_consoles(
    console_names: list[str],
    console_controller: ConsoleController,
    create_new_consoles: bool,
) -> list[Console]:
    """
    Retrieve models of local consoles based on the provided console names

    Args:
        console_names (list[str]): List of local console names
        console_controller (ConsoleController): Controller for console operations
        create_new_consoles (bool): Whether to create new consoles if they don't exist remotely

    Returns:
        list[Console]: List of Console objects representing local consoles
    """

    remote_consoles = console_controller.get_all() or []

    remote_console_names = [console.name for console in remote_consoles]

    local_consoles: list[Console] = []

    for console_name in console_names:
        console = Console(name=console_name)

        # Check if the console already exists in the remote consoles
        if (console_name in remote_console_names and create_new_consoles) and (
            search_result := console_controller.search(console)
        ):
            local_consoles.append(search_result[0])
        # If the console does not exist remotely create a new one
        elif console_name not in remote_console_names and (
            save_result := console_controller.save(console)
        ):
            local_consoles.append(save_result)
        # If the console is not found or not created then add the console with only name
        else:
            local_consoles.append(console)

    return local_consoles


def handle_creating_savefile(
    savefile: Savefile, savefile_controller: SavefileController, crawling_mode: Enum
) -> ProcessingResult:
    """
    Handle a new savefile that does not exist in the database

    Args:
        savefile (Savefile): Savefile object to handle
        savefile_controller (SavefileController): Controller for savefile operations
        crawling_mode (Enum): Mode for crawling the savefile

    Returns:
        str: Result of the savefile handling
    """

    if crawling_mode in (CrawlingMode.UPDATE, CrawlingMode.FORCE):
        return ProcessingResult.IGNORED

    logger.log_info(
        f"Creating savefile '{savefile.name}' in console "
        f"'{savefile.console.name if savefile.console else 'Unknown'}'"
    )

    result = savefile_controller.save(savefile)

    return ProcessingResult.CREATED if result else ProcessingResult.FAILED_CREATION


def handle_downloading_savefile(
    savefile: Savefile,
    savefile_controller: SavefileController,
    downloading_mode: CrawlingMode,
    overwrite_existing: bool = False,
) -> ProcessingResult:
    """
    Handle a savefile that needs to be downloaded from the remote server

    Args:
        savefile (Savefile): Savefile object to handle
        savefile_controller (SavefileController): Controller for savefile operations
        downloading_mode (CrawlingMode): Mode for downloading the savefile
        overwrite_existing (bool, optional): Whether to overwrite existing local savefiles

    Returns:
        str: Result of the savefile handling
    """

    if not overwrite_existing and downloading_mode.value < CrawlingMode.NEW.value:
        return ProcessingResult.IGNORED

    if savefile.id is None:
        return ProcessingResult.FAILED_DOWNLOAD

    result = savefile_controller.get(savefile.id, download_path=savefile.abs_path)

    return ProcessingResult.DOWNLOADED if result else ProcessingResult.FAILED_DOWNLOAD


def handle_existing_savefile(
    savefile: Savefile,
    savefile_controller: SavefileController,
    crawling_modes: tuple[CrawlingMode, CrawlingMode],
) -> ProcessingResult:
    """
    Handle a savefile that already exists in the database

    Args:
        savefile (Savefile): Savefile object to handle
        savefile_controller (SavefileController): Controller for savefile operations
        crawling_modes (tuple[CrawlingMode, CrawlingMode]): Modes for crawling the savefile

    Returns:
        str: Result of the savefile handling
    """

    console_name = savefile.console.name if savefile.console else "Unknown"

    # Skip if we only want new files
    if crawling_modes[0] == CrawlingMode.NEW:
        logger.log_info(
            f"Skipping savefile '{savefile.name}', "
            f"savefile already exists in console '{console_name}'"
        )
        return ProcessingResult.IGNORED

    # For automatic update, check if update is needed
    if (
        CrawlingMode.UPDATE not in crawling_modes
        and CrawlingMode.AUTO not in crawling_modes
    ):
        return ProcessingResult.SKIPPED

    existing_savefile = (
        savefile_controller.get(savefile.id) if savefile.id is not None else None
    )

    if not existing_savefile:
        logger.log_info(
            f"Savefile '{savefile.name}' not found in console '{console_name}'"
        )

        return ProcessingResult.FAILED_DOWNLOAD

    # If the local savefile is newer than the existing one, update it
    if savefile.modified_at > existing_savefile.modified_at and crawling_modes[0] in (
        CrawlingMode.UPDATE,
        CrawlingMode.AUTO,
    ):
        logger.log_info(
            f"Updating savefile '{savefile.name}' in console '{console_name}'"
        )
        result = savefile_controller.update(savefile)
        return ProcessingResult.UPLOADED if result else ProcessingResult.FAILED_UPLOAD

    # If the existing savefile is newer than the local one, download it
    if savefile.modified_at < existing_savefile.modified_at and crawling_modes[1] in (
        CrawlingMode.UPDATE,
        CrawlingMode.AUTO,
    ):
        return handle_downloading_savefile(
            savefile,
            savefile_controller,
            crawling_modes[1],
            overwrite_existing=True,
        )

    logger.log_info(
        f"Skipping savefile '{savefile.name}', "
        f"savefile is already up to date in console '{console_name}'"
    )

    return ProcessingResult.SKIPPED


def process_savefile(
    savefile: Savefile,
    availability: SavefileAvailability,
    savefile_controller: SavefileController,
    crawling_modes: tuple[CrawlingMode, CrawlingMode],
) -> ProcessingResult:
    """
    Process a savefile by checking if it exists, and handling it based on the crawling mode

    Args:
        savefile (Savefile): Savefile object to process
        availability (SavefileAvailability): Availability of the savefile
        savefile_controller (SavefileController): Controller for savefile operations
        crawling_modes (tuple[CrawlingMode, CrawlingMode]): Modes for crawling the savefile

    Returns:
        str: Result of the savefile processing
    """

    if availability == SavefileAvailability.LOCAL:
        return handle_creating_savefile(
            savefile, savefile_controller, crawling_modes[0]
        )
    if availability == SavefileAvailability.REMOTE:
        # Create a new Savefile object with the remote data
        return handle_downloading_savefile(
            savefile, savefile_controller, crawling_modes[1]
        )

    return handle_existing_savefile(savefile, savefile_controller, crawling_modes)


def retrieve_local_remote_savefiles(
    console: Console,
    savefile_controller: SavefileController,
) -> dict[Savefile, SavefileAvailability]:
    """
    Retrieve local and remote savefiles for a given console

    Args:
        console (Console): Console object for which to retrieve savefiles
        savefile_controller (SavefileController): Controller for savefile operations

    Returns:
        dict[Savefile, SavefileAvailability]: Dict mapping Savefile models to their availability
    """

    # Get remote savefiles for this console
    remote_savefiles = (
        savefile_controller.search(
            Savefile(id_console=console.id), allow_multiple_results=True
        )
        or []
    )

    # Set the console for each remote savefile
    for remote_savefile in remote_savefiles:
        remote_savefile.console = console
        remote_savefile.modified_at = None

    # Create a dictionary to track which remote files exist locally
    available_savefiles: dict[Savefile, SavefileAvailability] = {
        savefile: SavefileAvailability.REMOTE for savefile in remote_savefiles
    }

    # Walk through the local files
    for root, dirs, files in os.walk(console.saves_path or ""):
        for dir_path in dirs:
            logger.log_info(f"Now entering dir: {os.path.join(root, dir_path)}")

        for file in files:
            rel_dir = os.path.relpath(root, console.saves_path)

            savefile = Savefile(
                name=file,
                rel_path="/" if rel_dir == "." else f"{rel_dir.replace(os.sep, '/')}/",
            )
            savefile.console = console

            # Mark this file as found locally if it exists remotely
            available_savefiles[savefile] = (
                SavefileAvailability.BOTH
                if savefile in available_savefiles
                else SavefileAvailability.LOCAL
            )

    return available_savefiles


def update_progress_bars(
    primary_bar: Any, secondary_bar: Optional[Any], do_close: bool = False
) -> None:
    """Update both primary and secondary progress bars

    Args:
        primary_bar (Any): The primary progress bar to update
        secondary_bar (Optional[Any]): The secondary progress bar to update
        do_close (bool, optional): Whether to close the progress bars. Defaults to False.
    """

    if do_close:
        primary_bar.close()
        if secondary_bar is not None:
            secondary_bar.close()
    else:
        primary_bar.update(1)
        if secondary_bar is not None:
            secondary_bar.update(1)


def log_savefile_stats(
    console_name: str, available_savefiles: dict[Savefile, SavefileAvailability]
) -> None:
    """Log statistics about the available savefiles

    Args:
        console_name (str): The name of the console
        available_savefiles (dict[Savefile, SavefileAvailability]): The available savefiles
    """

    logger.log_info(
        f"Found {len(available_savefiles)} savefiles for console '{console_name}'"
    )
    logger.log_info(
        f"Remote only savefiles: "
        f"{sum(1 for v in available_savefiles.values() if v == SavefileAvailability.REMOTE)}"
    )
    logger.log_info(
        f"Local only savefiles: "
        f"{sum(1 for v in available_savefiles.values() if v == SavefileAvailability.LOCAL)}"
    )
    logger.log_info(
        f"Both remote and local savefiles: "
        f"{sum(1 for v in available_savefiles.values() if v == SavefileAvailability.BOTH)}"
    )


def process_console_savefiles(
    console: Console,
    savefile_controller: SavefileController,
    crawling_modes: tuple[CrawlingMode, CrawlingMode],
) -> list[int]:
    """Process all savefiles for a single console

    Args:
        console (Console): The console to process savefiles for
        savefile_controller (SavefileController): Controller for savefile operations
        crawling_modes (tuple[CrawlingMode, CrawlingMode]): The crawling modes to use

    Returns:
        list[int]: The results of processing savefiles
    """

    available_savefiles = retrieve_local_remote_savefiles(console, savefile_controller)
    log_savefile_stats(console.name, available_savefiles)

    console_result = [0] * 9
    savefile_pbar, savefile_2nd_pbar = create_progress_bars(
        len(available_savefiles), is_console=False
    )

    for savefile, availability in available_savefiles.items():
        set_sized_description(savefile_pbar, savefile.name, savefile.rel_path)

        processing_result = process_savefile(
            savefile, availability, savefile_controller, crawling_modes
        )

        console_result[processing_result.value] += 1
        update_progress_bars(savefile_pbar, savefile_2nd_pbar)

    update_progress_bars(savefile_pbar, savefile_2nd_pbar, do_close=True)
    return console_result


def crawl_savefiles(
    console_names: list[str],
    saves_paths: list[str],
    console_controller: ConsoleController,
    savefile_controller: SavefileController,
    crawling_modes: tuple[CrawlingMode, CrawlingMode],
) -> dict[Console, list[int]]:
    """
    Crawl savefiles based on the provided parameters

    Args:
        console_names (list[str]): List of local console names
        saves_paths (list[str]): List of local savefile paths
        console_controller (ConsoleController): Controller for console operations
        savefile_controller (SavefileController): Controller for savefile operations
        crawling_modes (tuple[CrawlingMode, CrawlingMode]): Savefile crawling and downloading modes

    Returns:
        dict[Console, list[int]]: Dictionary mapping consoles to their processing results
    """

    create_new_consoles = crawling_modes[0].value >= CrawlingMode.NEW.value
    local_consoles = retrieve_local_consoles(
        console_names, console_controller, create_new_consoles
    )
    results: dict[Console, list[int]] = {}

    console_pbar, console_2nd_pbar = create_progress_bars(
        len(local_consoles), is_console=True
    )

    for index, console in enumerate(local_consoles):
        set_sized_description(console_pbar, console.name)

        if console.id is None:
            results[console] = [1]
            update_progress_bars(console_pbar, console_2nd_pbar)
            continue

        logger.log_info(f'Processing console "{console.name}" with ID {console.id}')
        console.saves_path = saves_paths[index]

        if not os.path.exists(console.saves_path):
            logger.log_warning(f"Non existing path at {console.saves_path}")
            results[console] = [1]
            update_progress_bars(console_pbar, console_2nd_pbar)
            continue

        logger.log_info(
            f"Crawling '{console.name}' saves inside '{console.saves_path}'"
        )
        results[console] = process_console_savefiles(
            console, savefile_controller, crawling_modes
        )
        update_progress_bars(console_pbar, console_2nd_pbar)

    set_sized_description(console_pbar, "All Console Done")

    update_progress_bars(console_pbar, console_2nd_pbar, do_close=True)

    return results


def print_results(results: dict[Console, list[int]]) -> None:
    """
    Print the results of the savefile crawling and downloading process

    Args:
        results (dict[Console, list[int]]): Dictionary containing results for each console
    """

    logger.log_info("Crawling results:")

    any_failed = False

    for console, counts in results.items():
        if counts[ProcessingResult.CONSOLE_FAILED.value] > 0:
            error_str = f"Console - Failed to process console {console.name}"

            if console.id is not None:
                error_str += f" with ID {console.id}"

            logger.log_error(error_str)
            any_failed = True
            continue

        if not any_failed:
            any_failed = any(
                counts[ProcessingResult.FAILED_CREATION.value :]
                or counts[ProcessingResult.FAILED_UPLOAD.value :]
                or counts[ProcessingResult.FAILED_DOWNLOAD.value :]
            )

        logger.log_info(f"Results for Console: {console.name}")
        logger.log_info(f"Created:          {counts[ProcessingResult.CREATED.value]}")
        logger.log_info(f"Updated:          {counts[ProcessingResult.UPLOADED.value]}")
        logger.log_info(
            f"Downloaded:       {counts[ProcessingResult.DOWNLOADED.value]}"
        )
        logger.log_info(f"Skipped:          {counts[ProcessingResult.SKIPPED.value]}")
        logger.log_info(f"Ignored:          {counts[ProcessingResult.IGNORED.value]}")
        logger.log_info(
            f"Failed Creation:  {counts[ProcessingResult.FAILED_CREATION.value]}"
        )
        logger.log_info(
            f"Failed Upload:    {counts[ProcessingResult.FAILED_UPLOAD.value]}"
        )
        logger.log_info(
            f"Failed Download:  {counts[ProcessingResult.FAILED_DOWNLOAD.value]}"
        )

    if not any_failed:
        logger.log_success("Crawling and downloading process completed successfully!")
    else:
        logger.log_error("Crawling and downloading process completed with errors!")

    logger.log_success(f"Total consoles processed:            {len(results)}")

    if (
        console_failed := sum(
            counts[ProcessingResult.CONSOLE_FAILED.value] for counts in results.values()
        )
        > 0
    ):
        logger.log_error(f"Total consoles with errors:          {console_failed}")

    total_processed = sum(sum(counts) for counts in results.values())
    total_created = sum(
        counts[ProcessingResult.CREATED.value] for counts in results.values()
    )
    total_updated = sum(
        counts[ProcessingResult.UPLOADED.value] for counts in results.values()
    )
    total_downloaded = sum(
        counts[ProcessingResult.DOWNLOADED.value] for counts in results.values()
    )
    total_ignored_skipped = sum(
        counts[ProcessingResult.IGNORED.value] + counts[ProcessingResult.SKIPPED.value]
        for counts in results.values()
    )

    if total_created + total_updated + total_downloaded + total_ignored_skipped > 0:
        logger.log_success(f"Total savefiles processed:           {total_processed}")
        logger.log_success(f"Total savefiles created:             {total_created}")
        logger.log_success(f"Total savefiles updated:             {total_updated}")
        logger.log_success(f"Total savefiles downloaded:          {total_downloaded}")
        logger.log_success(
            f"Total savefiles ignored or skipped:  {total_ignored_skipped}"
        )

    if (
        total_savefiles_errors := sum(
            counts[ProcessingResult.FAILED_CREATION.value]
            + counts[ProcessingResult.FAILED_UPLOAD.value]
            + counts[ProcessingResult.FAILED_DOWNLOAD.value]
            for counts in results.values()
        )
        > 0
    ):
        logger.log_error(
            f"Total savefiles with errors:         {total_savefiles_errors}"
        )


def main() -> None:
    """
    Main function to run the Savefile Manager application
    It sets up the environment, authenticates the user, retrieves controllers,
    and crawls savefiles based on the provided parameters
    """

    console_names, saves_paths, api_url, crawling_modes = setup_env()

    token = AuthManager.login(
        api_url, os.getenv("EMAIL") or "", os.getenv("PASSWORD") or ""
    )

    if not token:
        logger.log_error("Failed to authenticate or register")
        return

    logger.log_info("Login successful")

    console_controller, savefile_controller = get_controllers(api_url, token)

    if len(console_names) != len(saves_paths):
        logger.log_error(
            "CONSOLE_NAMES and SAVES_PATHS arrays must have the same length"
        )

        return

    results = crawl_savefiles(
        console_names,
        saves_paths,
        console_controller,
        savefile_controller,
        crawling_modes,
    )

    AuthManager.logout(api_url, token)

    print_results(results)


if __name__ == "__main__":
    main()
