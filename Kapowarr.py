#!/usr/bin/env python3
#-*- coding: utf-8 -*-

import logging

from backend.db import __DATABASE_FILEPATH__, set_db_location, setup_db
from backend.files import folder_path
from backend.helpers import check_python_version
from backend.logging import setup_logging
from backend.server import create_app, create_waitress_server, set_url_base
from frontend.api import Settings, download_handler, task_handler


def Kapowarr() -> None:
	"""The main function of Kapowarr
	"""
	setup_logging()
	logging.info('Starting up Kapowarr')

	if not check_python_version():
		exit(1)

	set_db_location(folder_path(*__DATABASE_FILEPATH__))

	app = create_app()

	with app.app_context():
		setup_db()
		
		settings = Settings()
		url_base = settings['url_base']
		set_url_base(app, url_base)

		download_handler.create_download_folder()

	download_handler.load_download_thread.start()
	task_handler.handle_intervals()

	host: str = settings['host']
	port: int = settings['port']
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
