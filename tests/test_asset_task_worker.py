from app.services.asset_task_worker import AssetTaskWorker


class Service:
    def __init__(self): self.calls = 0
    def timeout_asset_tasks(self, novel_id, timeout): return {"timed_out": 0}
    def dispatch_asset_tasks(self, novel_id, limit, execute, provider_id):
        self.calls += 1
        return {"count": 0}


def test_worker_loop_respects_max_polls():
    service = Service()
    result = AssetTaskWorker(service).run_loop("n", interval_seconds=0, max_polls=2)
    assert result["polls"] == 2
    assert service.calls == 2

def test_worker_start_stop_lifecycle():
    service = Service(); worker = AssetTaskWorker(service)
    worker.start("n", interval_seconds=0.1, max_polls=1)
    assert worker.status()["state"] in {"RUNNING", "STOPPED"}
    worker.stop()
    assert worker.status()["running"] is False
