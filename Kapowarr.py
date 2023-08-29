#!/usr/bin/env python3
#-*- coding: utf-8 -*-

import logging
from sys import version_info

from backend.db import __DATABASE_FILEPATH__, set_db_location, setup_db
from backend.files import folder_path
from backend.logging import setup_logging
from backend.server import create_app, create_waitress_server, set_url_base
from frontend.api import download_handler, settings, task_handler


def _check_python_version() -> bool:
	"""Check if the python version that is used is a minimum version.

	Returns:
		bool: Whether or not the python version is version 3.8 or above or not.
	"""
	if not (version_info.major == 3 and version_info.minor >= 8):
		logging.critical(
			'The minimum python version required is python3.8 ' + 
			'(currently ' + version_info.major + '.' + version_info.minor + '.' + version_info.micro + ').'
		)
		return False
	return True

def Kapowarr() -> None:
	"""The main function of Kapowarr
	"""
	setup_logging()
	logging.info('Starting up Kapowarr')

	if not _check_python_version():
		exit(1)

	set_db_location(folder_path(*__DATABASE_FILEPATH__))

	app = create_app()

	with app.app_context():
		setup_db()
		
		url_base = settings.get_settings()['url_base']
		set_url_base(app, url_base)

		download_handler.create_download_folder()

	download_handler.load_download_thread.start()
	task_handler.handle_intervals()

	host: str = settings.cache['host']
	port: int = settings.cache['port']
	server = create_waitress_server(app, host, port)
	logging.info(f'Kapowarr running on http://{host}:{port}{url_base}/')
	# =================
	server.run()
	# =================

	download_handler.stop_handle()
	task_handler.stop_handle()

	return

if __name__ == "__main__":
	Kapowarr()
