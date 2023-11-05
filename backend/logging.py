#-*- coding: utf-8 -*-

import logging

log_levels = {
	'info': logging.INFO,
	'debug': logging.DEBUG
}

def setup_logging() -> None:
	"""Setup the basic config of the logging module.
	"""	
	logging.basicConfig(
		level=logging.INFO,
		format='[%(asctime)s][%(threadName)s][%(levelname)s] %(message)s',
		datefmt='%Y-%m-%d %H:%M:%S',
		force=True
	)
	return

def set_log_level(level: str) -> None:
	"""Change the logging level

	Args:
		level (str): The level to set the logging to.
			Should be one of the keys of `logging.log_levels`.
	"""
	logging.debug(f'Setting logging level: {log_levels[level]}')
	logging.getLogger().setLevel(
		level=log_levels[level]
	)
	return
