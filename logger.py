"""
Logger module for the Savefile Manager application
Provides logging functionality with support for file and console outputs
"""

import os
import datetime
from enum import Enum
from typing import Optional
import colorama


class LogLevel(Enum):
    """
    Enum representing log levels for the Logger
    """

    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    NONE = 4


class Logger:
    """
    Logger class for logging messages to files and console
        Supports different log levels and automatic log file management
    """

    _file_log_level: Optional[LogLevel] = None
    _print_log_level: Optional[LogLevel] = None
    _initialized = False

    @classmethod
    def get_file_log_level(cls):
        """
        Get the current file log level

        Returns:
            LogLevel: Current file log level
        """
        return cls._file_log_level

    @classmethod
    def get_print_log_level(cls):
        """
        Get the current print log level

        Returns:
            LogLevel: Current print log level
        """
        return cls._print_log_level

    def __init__(
        self,
        calling_class: str = "Main",
        file_log_level: LogLevel = LogLevel.DEBUG,
        print_log_level: LogLevel = LogLevel.WARNING,
    ) -> None:
        """
        Initialize the Logger instance

        Args:
            calling_class (str, optional): Name of the calling class. Defaults to "Main"
            file_log_level (LogLevel, optional): Log level for file output. Defaults to DEBUG
            print_log_level (LogLevel, optional): Log level for console output. Defaults to WARNING
        """
        self.calling_class = calling_class
        self.log_file = (
            f"log/savefile_{datetime.datetime.now().strftime('%Y.%m.%d-%H.%M.%S')}.log"
        )

        if not Logger._initialized:
            Logger._file_log_level = file_log_level
            Logger._print_log_level = print_log_level
            Logger._initialized = True

        if not os.path.exists("log"):
            os.makedirs("log")

        # Remove logs older than a week
        one_week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        for file in os.listdir("log"):
            file_path = os.path.join("log", file)
            if os.path.isfile(file_path):
                file_creation_time = datetime.datetime.fromtimestamp(
                    os.path.getctime(file_path)
                )
                if file_creation_time < one_week_ago:
                    os.remove(file_path)

    # Log a message with timestamp and level
    def log(self, message: str, message_level: LogLevel = LogLevel.INFO) -> None:
        """
        Log a message with the specified log level

        Args:
            message (str): Message to log
            message_level (LogLevel, optional): Log level of the message. Defaults to LogLevel.INFO
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        log_message = (
            f"[{timestamp}] [{message_level.name:<7} "
            f"@ {self.calling_class:>8}] => {message}"
        )

        # Write to a log file
        if (
            Logger._file_log_level is not None
            and message_level.value >= Logger._file_log_level.value
        ):
            with open(self.log_file, "a", encoding="utf-8") as log_file:
                log_file.write(log_message + "\n")

        # Print to console
        if (
            Logger._print_log_level is not None
            and message_level.value >= Logger._print_log_level.value
        ):
            if os.name == "nt":
                colorama.init()
                color_map = {
                    LogLevel.DEBUG: colorama.Fore.LIGHTBLACK_EX,
                    LogLevel.INFO: colorama.Fore.WHITE,
                    LogLevel.WARNING: colorama.Fore.YELLOW,
                    LogLevel.ERROR: colorama.Fore.RED,
                }
                print(
                    color_map.get(message_level, colorama.Fore.WHITE)
                    + log_message
                    + colorama.Style.RESET_ALL
                )
            else:
                color_map = {
                    LogLevel.DEBUG: "\033[90m",  # Gray
                    LogLevel.INFO: "\033[97m",  # White
                    LogLevel.WARNING: "\033[93m",  # Yellow
                    LogLevel.ERROR: "\033[91m",  # Red
                }
                print(color_map.get(message_level, "\033[0m") + log_message + "\033[0m")

    def log_debug(self, message: str) -> None:
        """
        Log a debug-level message

        Args:
            message (str): Debug message to log
        """
        self.log(message, LogLevel.DEBUG)

    def log_info(self, message: str) -> None:
        """
        Log an info-level message

        Args:
            message (str): Info message to log
        """
        self.log(message, LogLevel.INFO)

    def log_warning(self, message: str) -> None:
        """
        Log a warning-level message

        Args:
            message (str): Warning message to log
        """
        self.log(message, LogLevel.WARNING)

    def log_error(self, message: str) -> None:
        """
        Log an error-level message

        Args:
            message (str): Error message to log
        """
        self.log(message, LogLevel.ERROR)
