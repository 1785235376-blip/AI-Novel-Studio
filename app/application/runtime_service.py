"""Read-only application boundary around the existing runtime."""

from __future__ import annotations

from typing import Any, Protocol

from .contracts import HealthStatus, RuntimeProviderStatus, RuntimeStatus


class RuntimePort(Protocol):
    def provider_status(self) -> dict[str, dict[str, Any]]: ...
    def models(self) -> list[dict[str, Any]]: ...


class RuntimeService:
    def __init__(self, runtime: RuntimePort):
        self._runtime = runtime

    def status(self) -> RuntimeStatus:
        providers = tuple(
            RuntimeProviderStatus(
                name=name,
                configured=bool(value.get("configured")),
                available=bool(value.get("available")),
                kind=str(value.get("kind", "unknown")),
                status=value.get("status"),
                models=tuple(value.get("models") or ()),
            )
            for name, value in sorted(self._runtime.provider_status().items())
        )
        return RuntimeStatus(healthy=any(item.available for item in providers), providers=providers)

    def health(self) -> HealthStatus:
        status = self.status()
        return HealthStatus(status="ok" if status.healthy else "degraded", runtime=status)

    def models(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(model) for model in self._runtime.models())
