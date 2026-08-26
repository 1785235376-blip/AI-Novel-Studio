from app.application.runtime_service import RuntimeService


class FakeRuntime:
    def provider_status(self):
        return {
            "cloud": {"configured": False, "available": False, "kind": "cloud"},
            "local": {"configured": True, "available": True, "kind": "local", "models": [{"name": "m"}]},
        }

    def models(self):
        return [{"name": "m", "provider": "local"}]


def test_runtime_status_is_deterministic_and_transport_neutral():
    service = RuntimeService(FakeRuntime())
    status = service.status()
    assert status.healthy
    assert [provider.name for provider in status.providers] == ["cloud", "local"]
    assert service.health().status == "ok"
    assert service.models() == ({"name": "m", "provider": "local"},)


def test_runtime_health_is_degraded_when_nothing_is_available():
    class Offline(FakeRuntime):
        def provider_status(self):
            return {"local": {"configured": True, "available": False, "kind": "local"}}

    assert RuntimeService(Offline()).health().status == "degraded"
