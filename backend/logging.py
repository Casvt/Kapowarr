#-*- coding: utf-8 -*-

import logging
import logging.config
from os.path import exists
from typing import Any


class UpToInfoFilter(logging.Filter):
	def filter(self, record: logging.LogRecord) -> bool:
		return record.levelno <= logging.INFO


class DebuggingOnlyFilter(logging.Filter):
	def filter(self, record: logging.LogRecord) -> bool:
		return LOGGER.level == logging.DEBUG


class ErrorColorFormatter(logging.Formatter):
	def format(self, record: logging.LogRecord) -> Any:
		result = super().format(record)
		return f'\033[1;31:40m{result}\033[0m'


LOGGER_NAME = "Kapowarr"
LOGGER_DEBUG_FILENAME = "Kapowarr_debug.log"
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
		},
		"only_if_debugging": {
			"()": DebuggingOnlyFilter
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
		"debug_file": {
			"class": "logging.StreamHandler",
			"level": "DEBUG",
			"formatter": "detailed",
			"filters": ["only_if_debugging"],
			"stream": ""
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
			"debug_file"
		]
	}
}

def setup_logging() -> None:
	"Setup the basic config of the logging module"
	logging.config.dictConfig(LOGGING_CONFIG)
	logging.getLogger().handlers[
		LOGGING_CONFIG["root"]["handlers"].index("debug_file")
	].setStream(
		open(get_debug_log_filepath(), 'a')
	)
	return

def get_debug_log_filepath() -> str:
	"""
	Get the filepath to the debug logging file.
	Not in a global variable to avoid unnecessary computation.
	"""
	from backend.files import folder_path
	return folder_path(LOGGER_DEBUG_FILENAME)

def set_log_level(
	level: int,
	clear_file: bool = True
) -> None:
	"""Change the logging level.

	Args:
		level (int): The level to set the logging to.
			Should be a logging level, like `logging.INFO` or `logging.DEBUG`.

		clear_file (bool, optional): Empty the debug logging file.
			Defaults to True.
	"""
	root_logger = logging.getLogger()
	if root_logger.level == level:
		return

	LOGGER.debug(f'Setting logging level: {level}')
	root_logger.setLevel(level)

	if level == logging.DEBUG and clear_file:
		file = get_debug_log_filepath()
		open(file, "w").close()

	return
