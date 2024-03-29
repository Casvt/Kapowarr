#-*- coding: utf-8 -*-

import logging
from typing import Union

def setup_logging() -> None:
	"Setup the basic config of the logging module"
	logging.getLogger('engineio.server').level = logging.CRITICAL
	logging.basicConfig(
		level=logging.INFO,
		format='[%(asctime)s][%(threadName)s][%(levelname)s] %(message)s',
		datefmt='%Y-%m-%d %H:%M:%S',
		force=True
	)
	return

def set_log_level(level: Union[int, str]) -> None:
	"""Change the logging level

	Args:
		level (Union[int, str]): The level to set the logging to.
			Should be a logging level, like `logging.INFO` or `logging.DEBUG`
			or the string version.
	"""
	logging.debug(f'Setting logging level: {level}')
	if isinstance(level, str):
		level = level.upper()
	logging.getLogger().setLevel(
		level=level
	)
	return
