import time
from threading import Thread
from typing import Callable


class Daemon:
    thread: Thread | None = None

    def __init__(self, handle: Callable):
        self.thread = Thread(target=handle, daemon=True)
        self.thread.start()
        time.sleep(1)  # Даем время на инициализацию
