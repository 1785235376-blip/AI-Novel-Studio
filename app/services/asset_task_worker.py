from dataclasses import dataclass
import threading
import time


@dataclass
class AssetTaskWorker:
    screenplay_service: object

    def __post_init__(self):
        self._thread = None
        self._stop_event = threading.Event()
        self._state = "STOPPED"

    def run_once(self, novel_id: str, limit: int = 10, execute: bool = False,
                 provider_id: str | None = None, timeout_seconds: int = 3600):
        """Run one bounded poll; caller owns scheduling and process lifecycle."""
        timeout = self.screenplay_service.timeout_asset_tasks(novel_id, timeout_seconds)
        dispatch = self.screenplay_service.dispatch_asset_tasks(
            novel_id, limit=limit, execute=execute, provider_id=provider_id
        )
        return {"timeout": timeout, "dispatch": dispatch}

    def run_loop(self, novel_id: str, limit: int = 10, execute: bool = False,
                 provider_id: str | None = None, timeout_seconds: int = 3600,
                 interval_seconds: float = 5.0, max_polls: int | None = None,
                 stop_event: threading.Event | None = None):
        stop_event = stop_event or threading.Event()
        polls = 0
        results = []
        while not stop_event.is_set() and (max_polls is None or polls < max_polls):
            results.append(self.run_once(novel_id, limit, execute, provider_id, timeout_seconds))
            polls += 1
            if stop_event.wait(max(0.1, float(interval_seconds))):
                break
        return {"novel_id": novel_id, "polls": polls, "stopped": stop_event.is_set(), "results": results}

    def start(self, novel_id: str, **kwargs):
        if self._thread and self._thread.is_alive():
            raise RuntimeError("asset task worker is already running")
        self._stop_event = threading.Event()
        self._state = "RUNNING"
        def target():
            try:
                self.run_loop(novel_id, stop_event=self._stop_event, **kwargs)
            finally:
                self._state = "STOPPED"
        self._thread = threading.Thread(target=target, name="asset-task-worker", daemon=True)
        self._thread.start()
        return self.status()

    def stop(self, timeout_seconds: float = 5.0):
        self._stop_event.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(max(0.0, float(timeout_seconds)))
        self._state = "STOPPED"
        return self.status()

    def status(self):
        return {"state": self._state, "running": bool(self._thread and self._thread.is_alive())}
