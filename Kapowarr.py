#!/usr/bin/env python3
#-*- coding: utf-8 -*-

import logging

from backend.db import __DATABASE_FILEPATH__, set_db_location, setup_db
from backend.files import folder_path
from backend.helpers import check_python_version
from backend.logging import setup_logging
from backend.server import SERVER
from frontend.api import Settings, download_handler, task_handler


def Kapowarr() -> None:
	"""The main function of Kapowarr
	"""
	setup_logging()
	logging.info('Starting up Kapowarr')

	if not check_python_version():
		exit(1)

	set_db_location(folder_path(*__DATABASE_FILEPATH__))

	SERVER.create_app()

	with SERVER.app.app_context():
		setup_db()

		settings = Settings()
		host: str = settings['host']
		port: int = settings['port']
		url_base: str = settings['url_base']
		SERVER.set_url_base(url_base)

		download_handler.create_download_folder()

	download_handler.load_download_thread.start()
	task_handler.handle_intervals()

	# =================
	SERVER.run(host, port)
	# =================

	download_handler.stop_handle()
	task_handler.stop_handle()

	if SERVER.do_restart:
		SERVER.handle_restart()

	return

if __name__ == "__main__":
	Kapowarr()
