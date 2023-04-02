#-*- coding: utf-8 -*-

"""This file contains general handy functions
"""

import logging

log_levels = {
	'info': logging.INFO,
	'debug': logging.DEBUG
}

def set_log_level(level: str) -> None:
	logging.getLogger().setLevel(
		level=log_levels[level]
	)
	return
