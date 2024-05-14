#-*- coding: utf-8 -*-

import logging
import logging.config
from typing import Any, Union


class UpToInfoFilter(logging.Filter):
	def filter(self, record: logging.LogRecord) -> bool:
		return record.levelno <= logging.INFO


class ErrorColorFormatter(logging.Formatter):
	def format(self, record: logging.LogRecord) -> Any:
		result = super().format(record)
		return f'\033[1;31:40m{result}\033[0m'


LOGGER_NAME = "Kapowarr"
LOGGER_DEBUG_FILENAME = "Kapowarr.log"
LOGGER = logging.getLogger(LOGGER_NAME)
LOGGING_CONFIG = {
	"version": 1,
	"disable_existing_loggers": False,
	"formatters": {
		"simple": {
			"format": "[%(asctime)s][%(levelname)s] %(message)s",
			"datefmt": "%H:%M:%S"
		},
		"simple_red": {
			"()": ErrorColorFormatter,
			"format": "[%(asctime)s][%(levelname)s] %(message)s",
			"datefmt": "%H:%M:%S"
		},
		"detailed": {
			"format": "%(asctime)s | %(threadName)s | %(filename)sL%(lineno)s | %(levelname)s | %(message)s",
			"datefmt": "%Y-%m-%dT%H:%M:%S%z",
		}
	},
	"filters": {
		"up_to_info": {
			"()": UpToInfoFilter
		}
	},
	"handlers": {
		"console_error": {
			"class": "logging.StreamHandler",
			"level": "WARNING",
			"formatter": "simple_red",
			"stream": "ext://sys.stderr"
		},
		"console": {
			"class": "logging.StreamHandler",
			"level": "DEBUG",
			"formatter": "simple",
			"filters": ["up_to_info"],
			"stream": "ext://sys.stdout"
		},
		"file": {
			"class": "logging.handlers.RotatingFileHandler",
			"level": "DEBUG",
			"formatter": "detailed",
			"filename": "",
			"maxBytes": 1_000_000,
			"backupCount": 1
		}
	},
	"loggers": {
		LOGGER_NAME: {}
	},
	"root": {
		"level": "INFO",
		"handlers": [
			"console",
			"console_error",
			"file"
		]
	}
}

def setup_logging() -> None:
	"Setup the basic config of the logging module"
	LOGGING_CONFIG["handlers"]["file"]["filename"] = get_debug_log_filepath()
	logging.config.dictConfig(LOGGING_CONFIG)
	return

def get_debug_log_filepath() -> str:
	"""
	Get the filepath to the debug logging file.
	Not in a global variable to avoid unnecessary computation.
	"""
	from backend.files import folder_path
	return folder_path(LOGGER_DEBUG_FILENAME)

def set_log_level(
	level: Union[int, str]
) -> None:
	"""Change the logging level.

	Args:
		level (Union[int, str]): The level to set the logging to.
			Should be a logging level, like `logging.INFO` or `"DEBUG"`.
	"""
	if isinstance(level, str):
		level = logging._nameToLevel[level.upper()]

	root_logger = logging.getLogger()
	if root_logger.level == level:
		return

	LOGGER.debug(f'Setting logging level: {level}')
	root_logger.setLevel(level)

	return
