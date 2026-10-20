"""Owned, bounded-lifetime jobs for application and presentation adapters."""

import logging
import threading
import time

logger = logging.getLogger("workbench.application")


class BackgroundJobs:
    def __init__(self):
        self._lock = threading.Lock()
        self._threads: set[threading.Thread] = set()
        self._closed = False

    def start(self, operation, completed=None, *, name):
        def run():
            try:
                try:
                    value, error = operation(), None
                except Exception as exc:
                    value, error = None, exc
                if completed is not None:
                    completed(value, error)
                elif error is not None:
                    logger.error("%s failed: %s", name, error)
            except Exception:
                logger.exception("%s completion failed", name)
            finally:
                with self._lock:
                    self._threads.discard(threading.current_thread())

        with self._lock:
            if self._closed:
                return None
            thread = threading.Thread(target=run, name=name, daemon=True)
            self._threads.add(thread)
            try:
                thread.start()
            except Exception:
                self._threads.discard(thread)
                raise
            return thread

    def close(self, timeout=3.0):
        deadline = time.monotonic() + timeout
        with self._lock:
            self._closed = True
            threads = tuple(self._threads)
        for thread in threads:
            if thread is not threading.current_thread():
                thread.join(max(0.0, deadline - time.monotonic()))
        alive = [t.name for t in threads if t is not threading.current_thread() and t.is_alive()]
        if alive:
            raise TimeoutError("Background jobs did not stop: " + ", ".join(alive))
