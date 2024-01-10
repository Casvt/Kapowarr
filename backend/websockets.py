from threading import Event, Thread

from simple_websocket_server import WebSocketServer, WebSocket

class EventServer:

    def __init__(self) -> None:
        self.thread = None
        self.server = None

    def publish(self, data):
        pass

    def run(self):
        self.thread = StoppableThread(
            target=self._start_server,
            args=(),
            name="Websocket Server Thread",
            daemon=True
        )
        self.thread.start()

    def stop(self):
        self.thread.stop()

    def _start_server(self):
        self.server = WebSocketServer('', 8000, SimpleEcho)
        print("serving")
        self.server.serve_forever()



class StoppableThread(Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self,  *args, **kwargs):
        super(StoppableThread, self).__init__(*args, **kwargs)
        self._stop_event = Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()


class SimpleEcho(WebSocket):
    def handle(self):
        # echo message back to client
        self.send_message(self.data)

    def connected(self):
        print(self.address, 'connected')

    def handle_close(self):
        print(self.address, 'closed')
