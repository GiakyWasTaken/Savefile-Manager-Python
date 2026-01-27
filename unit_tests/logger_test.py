"""Unit tests for the Logger module"""

import os.path
import datetime
import pytest
from logger import Logger, LogLevel

LOGS_PATH = "test_logs"


@pytest.fixture(autouse=True)
def reset_logger():
    """Reset Logger before each test"""
    Logger.reset_logger()
    yield


@pytest.fixture(scope="module", autouse=True)
def cleanup_logs():
    """Clean up log files after all tests"""
    yield
    if os.path.exists(LOGS_PATH):
        for filename in os.listdir(LOGS_PATH):
            file_path = os.path.join(LOGS_PATH, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
        os.rmdir(LOGS_PATH)


def test_logger_constructor():
    """
    Test the Logger constructor and initialization
    """
    now = datetime.datetime.now().replace(microsecond=0)

    logger = Logger(logs_path=LOGS_PATH)
    assert isinstance(logger, Logger)

    # Check if log file path is correctly set
    assert os.path.exists(LOGS_PATH)

    last_log_date_str = logger.log_file.rsplit("_", maxsplit=1)[-1].replace(".log", "")
    last_log_date = datetime.datetime.strptime(last_log_date_str, "%Y.%m.%d-%H.%M.%S")

    assert last_log_date >= now


def test_logger_log_levels():
    """
    Test the Logger log level getters and initialization
    """
    Logger(
        logs_path=LOGS_PATH,
        file_log_level=LogLevel.ERROR,
        print_log_level=LogLevel.DEBUG,
    )
    assert Logger.get_file_log_level() == LogLevel.ERROR
    assert Logger.get_print_log_level() == LogLevel.DEBUG

    # Create another logger instance with different levels
    Logger(
        logs_path=LOGS_PATH,
        file_log_level=LogLevel.WARNING,
        print_log_level=LogLevel.INFO,
    )
    # The log levels should remain as set by the first instance
    assert Logger.get_file_log_level() == LogLevel.ERROR
    assert Logger.get_print_log_level() == LogLevel.DEBUG


def test_logger_logging():
    """
    Test the logging functionality of Logger
    """
    logger = Logger(
        logs_path=LOGS_PATH,
        file_log_level=LogLevel.DEBUG,
        print_log_level=LogLevel.DEBUG,
    )

    # Test logging at different levels
    logger.log_debug("This is a debug message.")
    logger.log_info("This is an info message.")
    logger.log_warning("This is a warning message.")
    logger.log_error("This is an error message.")
    logger.log_success("This is a success message.")

    # Check if log file is created and contains the messages
    assert os.path.exists(logger.log_file)

    with open(logger.log_file, "r", encoding="utf-8") as f:
        log_contents = f.read()
        assert "This is a debug message." in log_contents
        assert "This is an info message." in log_contents
        assert "This is a warning message." in log_contents
        assert "This is an error message." in log_contents
        assert "This is a success message." in log_contents
