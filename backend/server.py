#-*- coding: utf-8 -*-

"""
Setting up, running and shutting down the API and web-ui
"""

from __future__ import annotations

from os import execv, urandom
from sys import argv
from threading import Timer, current_thread
from typing import TYPE_CHECKING, NoReturn

from flask import Flask, render_template, request
from waitress import create_server
from waitress.task import ThreadedTaskDispatcher as TTD
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from backend.db import DBConnection, close_db
from backend.files import folder_path
from backend.helpers import DB_ThreadSafeSingleton, Singleton, WebSocket
from backend.logging import LOGGER
from backend.settings import private_settings

if TYPE_CHECKING:
	from waitress.server import TcpWSGIServer


class ThreadedTaskDispatcher(TTD):
	def handler_thread(self, thread_no: int) -> None:
		super().handler_thread(thread_no)

		i = f'{DBConnection}{current_thread()}'
		if (
			i in DB_ThreadSafeSingleton._instances
			and
			not DB_ThreadSafeSingleton._instances[i].closed
		):
			DB_ThreadSafeSingleton._instances[i].close()

		return

	def shutdown(self,
		cancel_pending: bool = True,
		timeout: int = 5
	) -> bool:
		print()
		LOGGER.info('Shutting down Kapowarr...')

		ws = WebSocket()
		if '/' in ws.server.manager.rooms:
			for sid in tuple(ws.server.manager.rooms['/'][None]):
				ws.server.disconnect(sid)

		result = super().shutdown(cancel_pending, timeout)
		DBConnection(20.0).close()
		return result


class Server(metaclass=Singleton):
	api_prefix = "/api"

	def __init__(self) -> None:
		self.do_restart = False
		self.url_base = ''
		return

	def create_app(self) -> None:
		"""Creates an flask app instance that can be used to start a web server"""

		from frontend.api import api
		from frontend.ui import ui

		app = Flask(
			__name__,
			template_folder=folder_path('frontend', 'templates'),
			static_folder=folder_path('frontend', 'static'),
			static_url_path='/static'
		)
		app.config['SECRET_KEY'] = urandom(32)
		app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
		app.config['JSON_SORT_KEYS'] = False

		ws = WebSocket()
		ws.init_app(
			app,
			path=f'{self.api_prefix}/socket.io',
			cors_allowed_origins='*',
			async_mode='threading',
			transports='polling'
		)

		# Add error handlers
		@app.errorhandler(404)
		def not_found(e):
			if request.path.startswith(self.api_prefix):
				return {'error': 'NotFound', 'result': {}}, 404
			return render_template('page_not_found.html')

		@app.errorhandler(400)
		def bad_request(e):
			return {'error': 'BadRequest', 'result': {}}, 400

		@app.errorhandler(405)
		def method_not_allowed(e):
			return {'error': 'MethodNotAllowed', 'result': {}}, 405

		@app.errorhandler(500)
		def internal_error(e):
			return {'error': 'InternalError', 'result': {}}, 500

		# Add endpoints
		app.register_blueprint(ui)
		app.register_blueprint(api, url_prefix=self.api_prefix)

		# Setup db handling
		app.teardown_appcontext(close_db)

		self.app = app
		return

	def set_url_base(self, url_base: str) -> None:
		"""Change the URL base of the server.

		Args:
			url_base (str): The desired URL base to set it to.
		"""
		self.app.config['APPLICATION_ROOT'] = url_base
		self.app.wsgi_app = DispatcherMiddleware(
			Flask(__name__),
			{url_base: self.app.wsgi_app}
		)
		self.url_base = url_base
		return

	def __create_waitress_server(self, host: str, port: int) -> TcpWSGIServer:
		"""From the `Flask` instance created in `self.create_app()`, create
		a waitress server instance.

		Args:
			host (str): Where to host the server on (e.g. `0.0.0.0`).
			port (int): The port to host the server on (e.g. `5656`).

		Returns:
			TcpWSGIServer: The waitress server instance.
		"""
		dispatcher = ThreadedTaskDispatcher()
		dispatcher.set_thread_count(private_settings['hosting_threads'])

		server = create_server(
			self.app,
			_dispatcher=dispatcher,
			host=host,
			port=port,
			threads=private_settings['hosting_threads']
		)
		return server

	def run(self, host: str, port: int) -> None:
		"""Start the webserver.

		Args:
			host (str): The host to bind to.
			port (int): The port to listen on.
		"""
		self.server = self.__create_waitress_server(host, port)
		LOGGER.info(f'Kapowarr running on http://{host}:{port}{self.url_base}')
		self.server.run()

		return

	def __shutdown_thread_function(self) -> None:
		"""Shutdown waitress server. Intended to be run in a thread.
		"""
		self.server.task_dispatcher.shutdown()
		self.server.close()
		self.server._map.clear()
		return

	def shutdown(self) -> None:
		"""Stop the waitress server. Starts a thread that
		shuts down the server.
		"""
		t = Timer(1.0, self.__shutdown_thread_function)
		t.name = "InternalStateHandler"
		t.start()
		return

	def restart(self) -> None:
		"""Same as `self.shutdown()`, but restart instead of shutting down.
		"""
		self.do_restart = True
		self.shutdown()
		return

	def handle_restart(self) -> NoReturn:
		"""Restart the interpreter.

		Returns:
			NoReturn: No return because it replaces the interpreter.
		"""
		LOGGER.info('Restarting Kapowarr')
		from Kapowarr import __file__ as k_file
		execv(folder_path(k_file), [argv[0]])

SERVER = Server()
