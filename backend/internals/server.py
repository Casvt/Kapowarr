# -*- coding: utf-8 -*-

"""
Setting up, running and shutting down the webserver.
Also handling startup types.
"""

from __future__ import annotations

from multiprocessing import SimpleQueue
from os import urandom
from threading import Thread, Timer
from typing import (TYPE_CHECKING, Any, Callable, Dict,
                    Iterable, List, Mapping, Union)

from flask import Flask, render_template, request
from flask.json.provider import DefaultJSONProvider
from flask_socketio import SocketIO
from socketio import PubSubManager
from waitress.server import create_server
from waitress.task import ThreadedTaskDispatcher as TTD
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from backend.base.definitions import (Constants, SocketEvent,
                                      StartType, StartTypeHandler)
from backend.base.files import folder_path
from backend.base.helpers import Singleton
from backend.base.logging import LOGGER, setup_logging
from backend.internals.db import (DBConnectionManager, close_db,
                                  set_db_location,
                                  setup_db_adapters_and_converters)
from backend.internals.settings import Settings

if TYPE_CHECKING:
    from flask.ctx import AppContext

    from backend.base.definitions import Download
    from backend.features.tasks import Task


# region Thread Manager
class ThreadedTaskDispatcher(TTD):
    def __init__(self) -> None:
        super().__init__()

        # The DB connection should be closed when the thread is ending, but
        # right before it actually has. Waitress will consider a thread closed
        # once it's not in the self.threads set anymore, regardless of whether
        # the thread has actually ended/joined, so anything we do after that
        # could be cut short by the main thread ending. So we need to close
        # the DB connection before the thread is discarded from the set.
        class TDDSet(set):
            def discard(self, element: Any) -> None:
                DBConnectionManager.close_connection_of_thread()
                return super().discard(element)

        self.threads = TDDSet()
        return

    def shutdown(self, cancel_pending: bool = True, timeout: int = 5) -> bool:
        print()
        LOGGER.info('Shutting down Kapowarr')

        WebSocket().disconnect_all()

        result = super().shutdown(cancel_pending, timeout)
        return result


# region Server
class Server(metaclass=Singleton):
    url_base = ''

    def __init__(self) -> None:
        self.__start_type = None
        self.app = self._create_app()
        return

    @staticmethod
    def _create_app() -> Flask:
        """Creates a flask app instance that can be used to start a web server.

        Returns:
            Flask: The instance.
        """
        from frontend.api import api
        from frontend.ui import ui

        app = Flask(
            __name__,
            template_folder=folder_path('frontend', 'templates'),
            static_folder=folder_path('frontend', 'static'),
            static_url_path='/static'
        )
        app.config['SECRET_KEY'] = urandom(32)

        json_provider = DefaultJSONProvider(app)
        json_provider.sort_keys = False
        json_provider.compact = False
        app.json = json_provider

        ws = WebSocket()
        ws.init_app(
            app,
            path=f'{Constants.API_PREFIX}/socket.io',
            cors_allowed_origins='*',
            async_mode='threading',
            client_manager=MPWebSocketQueue(SimpleQueue(), write_only=False)
        )

        # Add error handlers
        @app.errorhandler(400)
        def bad_request(e):
            return {'error': 'BadRequest', 'result': {}}, 400

        @app.errorhandler(404)
        def not_found(e):
            if request.path.startswith(Constants.API_PREFIX):
                return {'error': 'NotFound', 'result': {}}, 404
            return render_template('page_not_found.html')

        @app.errorhandler(405)
        def method_not_allowed(e):
            return {'error': 'MethodNotAllowed', 'result': {}}, 405

        @app.errorhandler(500)
        def internal_error(e):
            return {'error': 'InternalError', 'result': {}}, 500

        # Add endpoints
        app.register_blueprint(ui)
        app.register_blueprint(api, url_prefix=Constants.API_PREFIX)

        # Setup db handling
        app.teardown_appcontext(close_db)

        return app

    def run(
        self,
        host: str,
        port: int,
        url_base: str
    ) -> Union[StartType, None]:
        """Start the webserver.

        Args:
            host (str): IP address to bind to, or `0.0.0.0` for all.
            port (int): The port to listen on.
            url_base (str): The url prefix/base to host the endpoints on, or
                an empty string for no prefix.

        Returns:
            Union[StartType, None]: `None` on shutdown, `StartType` on restart.
        """
        self.app.config["APPLICATION_ROOT"] = url_base
        self.app.wsgi_app = DispatcherMiddleware( # type: ignore
            Flask(__name__),
            {url_base: self.app.wsgi_app}
        )
        self.__class__.url_base = url_base

        dispatcher = ThreadedTaskDispatcher()
        dispatcher.set_thread_count(Constants.HOSTING_THREADS)

        self.server = create_server(
            self.app,
            _dispatcher=dispatcher,
            host=host,
            port=port,
            threads=Constants.HOSTING_THREADS
        )

        LOGGER.info(f'Kapowarr running on http://{host}:{port}{self.url_base}')
        self.server.run()

        return self.__start_type

    def __trigger_server_shutdown(self) -> None:
        """Shutdown waitress server. Intended to be run in a thread."""
        if not hasattr(self, 'server'):
            return

        self.server.task_dispatcher.shutdown()
        self.server.close()
        self.server._map.clear() # type: ignore
        return

    def shutdown(self) -> None:
        """
        Stop the waitress server. Starts a thread that will trigger the server
        shutdown after one second.
        """
        self.get_db_timer_thread(
            interval=1.0,
            target=self.__trigger_server_shutdown,
            name="InternalStateHandler"
        ).start()
        return

    def restart(
        self,
        start_type: StartType = StartType.RESTART
    ) -> None:
        """Same as `self.shutdown()`, but restart instead of shutting down.

        Args:
            start_type (StartType, optional): Why Kapowarr should restart.
                Defaults to StartType.RESTART.
        """
        self.__start_type = start_type
        self.shutdown()
        return

    def get_db_thread(
        self,
        target: Callable,
        name: str,
        args: Iterable[Any] = (),
        kwargs: Mapping[str, Any] = {}
    ) -> Thread:
        """Create a thread that runs under Flask app context.

        Args:
            target (Callable): The function to run in the thread.

            name (str): The name of the thread.

            args (Iterable[Any], optional): The arguments to pass to the function.
                Defaults to ().

            kwargs (Mapping[str, Any], optional): The keyword arguments to pass
                to the function.
                Defaults to {}.

        Returns:
            Thread: The Thread instance.
        """
        def db_thread(*args, **kwargs) -> None:
            with self.app.app_context():
                target(*args, **kwargs)
            return

        t = Thread(
            target=db_thread,
            name=name,
            args=args,
            kwargs=kwargs
        )
        return t

    def get_db_timer_thread(
        self,
        interval: float,
        target: Callable,
        name: Union[str, None] = None,
        args: Iterable[Any] = (),
        kwargs: Mapping[str, Any] = {}
    ) -> Timer:
        """Create a timer thread that runs under Flask app context.

        Args:
            interval (float): The time to wait before running the target.

            target (Callable): The function to run in the thread.

            name (Union[str, None], optional): The name of the thread.
                Defaults to None.

            args (Iterable[Any], optional): The arguments to pass to the function.
                Defaults to ().

            kwargs (Mapping[str, Any], optional): The keyword arguments to pass
                to the function.
                Defaults to {}.

        Returns:
            Timer: The timer thread instance.
        """
        def db_thread(*args, **kwargs) -> None:
            with self.app.app_context():
                target(*args, **kwargs)
            return

        t = Timer(
            interval=interval,
            function=db_thread,
            args=args,
            kwargs=kwargs
        )
        if name:
            t.name = name
        return t


# region Websocket
class MPWebSocketQueue(PubSubManager):
    name = 'mp_queue'

    def __init__(
        self,
        queue: SimpleQueue[Dict[str, Any]],
        write_only: bool = False,
        channel='flask-socketio',
        logger=None
    ) -> None:
        super().__init__(channel, write_only, logger)
        self.queue = queue
        return

    def initialize(self):
        super().initialize()
        if not self.write_only:
            self.thread.name = "WebSocketQueueThread"

    def _publish(self, data: Dict[str, Any]):
        self.queue.put(data)
        return

    def _listen(self):
        while True:
            result = self.queue.get()
            yield result


class WebSocket(SocketIO, metaclass=Singleton):
    server_options: dict

    @property
    def client_manager(self) -> MPWebSocketQueue:
        return self.server_options['client_manager']

    def disconnect_all(self) -> None:
        """Disconnect all clients from the default namespace"""
        for sid, _ in self.client_manager.get_participants('/', None):
            self.client_manager.disconnect(sid, '/')
        return

    def emit( # type: ignore
        self,
        event: SocketEvent,
        data: Dict[str, Any]
    ) -> None:
        cm = self.client_manager

        if not cm.write_only:
            super().emit(event.value, data)
        else:
            message = {
                'method': 'emit',
                'event': event.value,
                'data': data,
                'namespace': '/',
                'host_id': cm.host_id
            }
            cm._handle_emit(message)
            cm._publish(message)

        return

    def send_task_added(self, task: Task) -> None:
        """Send a message stating a task that has been added
        to the queue.

        Args:
            task (Task): The task that has been added.
        """
        self.emit(
            SocketEvent.TASK_ADDED,
            {
                'action': task.action,
                'volume_id': task.volume_id,
                'issue_id': task.issue_id
            }
        )
        return

    def send_task_ended(self, task: Task) -> None:
        """Send a message stating a task that has been removed
        from the queue. Either because it's finished or canceled.

        Args:
            task (Task): The task that has been removed.
        """
        self.emit(
            SocketEvent.TASK_ENDED,
            {
                'action': task.action,
                'volume_id': task.volume_id,
                'issue_id': task.issue_id
            }
        )
        return

    def update_task_status(
        self,
        task: Union[Task, None] = None,
        message: Union[str, None] = None
    ) -> None:
        """Send a message with the new task queue status. Supply either
        the task or the message.

        Args:
            task (Union[Task, None], optional): The task instance to send
            the status of.
                Defaults to None.

            message (Union[str, None], optional): The message to send.
                Defaults to None.
        """
        if task is not None:
            self.emit(
                SocketEvent.TASK_STATUS,
                {
                    'message': task.message
                }
            )

        elif message is not None:
            self.emit(
                SocketEvent.TASK_STATUS,
                {
                    'message': message
                }
            )

        return

    def send_queue_added(self, download: Download) -> None:
        """Send a message stating a download that has been added
        to the queue.

        Args:
            download (Download): The download that has been added.
        """
        self.emit(
            SocketEvent.QUEUE_ADDED,
            download.as_dict()
        )
        return

    def send_queue_ended(self, download: Download) -> None:
        """Send a message stating a download that has been removed
        from the queue. Either because it's finished or canceled.

        Args:
            download (Download): The download that has been removed.
        """
        self.emit(
            SocketEvent.QUEUE_ENDED,
            {
                'id': download.id
            }
        )
        return

    def update_queue_status(self, download: Download) -> None:
        """Send a message with the new download queue status.

        Args:
            download (Download): The download instance to send the status of.
        """
        self.emit(
            SocketEvent.QUEUE_STATUS,
            {
                'id': download.id,
                'status': download.state.value,
                'size': download.size,
                'speed': download.speed,
                'progress': download.progress
            }
        )
        return

    def update_mass_editor_status(
        self,
        identifier: str,
        current_item: int,
        total_items: int
    ) -> None:
        """Send a message with the progress on a Mass Editor job.

        Args:
            identifier (str): The identifier of the job.
            current_item (int): The item number currently being worked on.
            total_items (int): The total number of items that will be worked on.
        """
        self.emit(
            SocketEvent.MASS_EDITOR_STATUS,
            {
                'identifier': identifier,
                'current_item': current_item,
                'total_items': total_items
            }
        )
        return

    def update_downloaded_status(
        self,
        volume_id: int,
        not_downloaded_issues: List[int] = [],
        downloaded_issues: List[int] = []
    ) -> None:
        """Send a message with the changes in which issues are downloaded and
        which aren't.

        Args:
            volume_id (int): The ID of the volume.

            not_downloaded_issues (List[int], optional): The issue IDs that were
            previously downloaded, but aren't anymore.
                Defaults to [].

            downloaded_issues (List[int], optional): The issue IDs that were
            previously not downloaded, but now are.
                Defaults to [].
        """
        self.emit(
            SocketEvent.DOWNLOADED_STATUS,
            {
                'volume_id': volume_id,
                'not_downloaded_issues': not_downloaded_issues,
                'downloaded_issues': downloaded_issues
            }
        )
        return


# region StartType Handling
class StartTypeHandlers:
    handlers: dict[StartType, StartTypeHandler] = {}
    timeout_thread: Union[Timer, None] = None
    running_handler: Union[StartType, None] = None

    @classmethod
    def register_handler(cls, start_type: StartType):
        """Register a handler for a certain start type.

        ```
        @StartTypeHandlers.register_handler(example_type)
        class ExampleHandler(StartTypeHandler):
            ...
        ```

        Args:
            start_type (StartType): The start type that the handler is for.
        """
        def wrapper(
            handler_class: type[StartTypeHandler]
        ) -> type[StartTypeHandler]:
            cls.handlers[start_type] = handler_class()
            return handler_class
        return wrapper

    @staticmethod
    def _on_timeout_wrapper(
        on_timeout: Callable[[], None],
        restart_on_timeout: bool
    ) -> None:
        on_timeout()
        if restart_on_timeout:
            Server().restart()
        return

    @classmethod
    def start_timer(cls, start_type: StartType) -> None:
        """Start the timer for a start type.

        Args:
            start_type (StartType): The start type to start the timer for.
        """
        if start_type not in cls.handlers:
            return

        if cls.timeout_thread and cls.timeout_thread.is_alive():
            cls.timeout_thread.cancel()

        handler = cls.handlers[start_type]
        cls.running_handler = start_type
        cls.timeout_thread = Server().get_db_timer_thread(
            interval=handler.timeout,
            target=cls._on_timeout_wrapper,
            name=f"StartTypeHandler.{start_type.name}",
            args=(handler.on_timeout, handler.restart_on_timeout)
        )
        cls.timeout_thread.start()
        LOGGER.info(
            "Starting timer for %s (%d seconds)",
            handler.description, handler.timeout
        )
        return

    @classmethod
    def diffuse_timer(cls, start_type: StartType) -> None:
        """Stop/Diffuse the timer for a start type.

        Args:
            start_type (StartType): The start type to stop the timer for.
        """
        if cls.running_handler != start_type:
            return

        if not (cls.timeout_thread and cls.timeout_thread.is_alive()):
            return

        handler = cls.handlers[start_type]
        LOGGER.info(
            "Timer for %s diffused",
            handler.description
        )
        cls.timeout_thread.cancel()
        cls.timeout_thread = None
        cls.running_handler = None
        handler.on_diffuse()
        return


@StartTypeHandlers.register_handler(StartType.RESTART_HOSTING_CHANGES)
class HostingChangesHandler(StartTypeHandler):
    description = "hosting changes"
    timeout = Constants.HOSTING_REVERT_TIME
    restart_on_timeout = True

    def on_timeout(self) -> None:
        Settings().restore_hosting_settings()
        return

    def on_diffuse(self) -> None:
        return


# region Subprocess Handling
def setup_process(
    log_level: int,
    log_folder: Union[str, None],
    log_file: Union[str, None],
    db_folder: Union[str, None],
    ws_queue: SimpleQueue
) -> Callable[[], AppContext]:
    setup_logging(log_folder, log_file, log_level, do_rollover=False)
    set_db_location(db_folder)
    setup_db_adapters_and_converters()

    WebSocket(client_manager=MPWebSocketQueue(ws_queue, write_only=True))

    app = Flask(__name__)
    app.teardown_appcontext(close_db)
    return app.app_context
