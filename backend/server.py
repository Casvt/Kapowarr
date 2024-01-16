#-*- coding: utf-8 -*-

"""
Setting up, running and shutting down the API and web-ui
"""

import logging
from os import urandom
from threading import current_thread

from flask import Flask, render_template, request
from waitress import create_server
from waitress.task import ThreadedTaskDispatcher as OldThreadedTaskDispatcher
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from backend.db import DBConnection, close_db
from backend.files import folder_path
from backend.helpers import DB_ThreadSafeSingleton, WebSocket
from backend.settings import private_settings
from frontend.api import api
from frontend.ui import ui, ui_vars

__API_PREFIX__ = '/api'

class ThreadedTaskDispatcher(OldThreadedTaskDispatcher):
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
		logging.info('Shutting down Kapowarr...')
		WebSocket().request_disconnect()
		result = super().shutdown(cancel_pending, timeout)
		DBConnection(20.0).close()
		return result

def create_app() -> Flask:
	"""Creates an flask app instance that can be used to start a web server

	Returns:
		Flask: The app instance
	"""
	app = Flask(
		__name__,
		template_folder=folder_path('frontend','templates'),
		static_folder=folder_path('frontend','static'),
		static_url_path='/static'
	)
	app.config['SECRET_KEY'] = urandom(32)
	app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
	app.config['JSON_SORT_KEYS'] = False

	WebSocket().init_app(
		app,
		path=f'{__API_PREFIX__}/socket.io',
		cors_allowed_origins='*',
		async_mode='threading',
		transports='polling'
	)

	# Add error handlers
	@app.errorhandler(404)
	def not_found(e):
		if request.path.startswith(__API_PREFIX__):
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
	app.register_blueprint(api, url_prefix=__API_PREFIX__)

	# Setup db handling
	app.teardown_appcontext(close_db)

	return app

def set_url_base(app: Flask, url_base: str) -> None:
	"""Change the URL base of the server.

	Args:
		app (Flask): The `Flask` instance to change the URL base of.
		url_base (str): The desired URL base to set it to.
	"""
	app.config['APPLICATION_ROOT'] = url_base
	app.wsgi_app = DispatcherMiddleware(Flask(__name__), {url_base: app.wsgi_app})
	ui_vars.update({'url_base': url_base})
	return

def create_waitress_server(app: Flask, host: str, port: int):
	"""Create a waitress server with a Flask instance.

	Args:
		app (Flask): The `Flask` instance to build the server for.
		host (str): Where to host the server on (e.g. `0.0.0.0`).
		port (int): The port to host the server on (e.g. `5656`).

	Returns:
		TcpWSGIServer: The waitress server instance.
	"""
	dispatcher = ThreadedTaskDispatcher()
	dispatcher.set_thread_count(private_settings['hosting_threads'])

	server = create_server(
		app,
		_dispatcher=dispatcher,
		host=host,
		port=port,
		threads=private_settings['hosting_threads']
	)
	return server
