from threading import Event, Thread

from websocket_server import WebsocketServer


class EventServer:
    def __init__(self) -> None:
        self.thread = None
        self.server = None

    def publish(self, data):
        self.server.send_message_to_all(data)

    def run(self):
        self.thread = StoppableThread(
            target=self._start_server,
            args=(),
            name="Websocket Server Thread",
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.server.shutdown_gracefully()
        self.thread.stop()

    def _new_client(self, client, server):
        print("New client connected and was given id %d" % client["id"])

    def _receive(self, client, server, message):
        print(f"Received message from client {client['id']}: {message}")

    def _start_server(self):
        self.server = WebsocketServer(host="", port=8000)
        self.server.set_fn_new_client(self._new_client)
        self.server.set_fn_message_received(self._receive)
        self.server.run_forever()


class StoppableThread(Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self, *args, **kwargs):
        super(StoppableThread, self).__init__(*args, **kwargs)
        self._stop_event = Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()
