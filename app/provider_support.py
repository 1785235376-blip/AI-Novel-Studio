from __future__ import annotations

import re
from threading import RLock
from typing import Iterable


STATIC_CREDENTIAL_PROVIDERS = frozenset({
    "deepseek", "openai", "claude", "gemini", "ddshub", "siliconflow",
    "aliyun-bailian", "runway", "kling", "minimax", "seedance", "custom",
})
_CANONICAL_PROVIDER_ID = re.compile(r"[a-z0-9_-]{1,64}")


def is_canonical_provider_id(provider_id: object) -> bool:
    return isinstance(provider_id, str) and _CANONICAL_PROVIDER_ID.fullmatch(provider_id) is not None


class ProviderSupportRegistry:
    def __init__(self, static_providers: Iterable[str] = STATIC_CREDENTIAL_PROVIDERS) -> None:
        self._static = frozenset(static_providers)
        self._sources: dict[str, frozenset[str]] = {}
        self._lock = RLock()

    def replace_source(self, source: str, provider_ids: Iterable[str]) -> None:
        values = frozenset(item for item in provider_ids if is_canonical_provider_id(item))
        with self._lock:
            self._sources[source] = values

    def register(self, source: str, provider_id: str) -> None:
        if not is_canonical_provider_id(provider_id):
            raise ValueError("unsupported provider")
        with self._lock:
            self._sources[source] = self._sources.get(source, frozenset()) | {provider_id}

    def remove(self, source: str, provider_id: str | None = None) -> None:
        with self._lock:
            if provider_id is None:
                self._sources.pop(source, None)
                return
            remaining = self._sources.get(source, frozenset()) - {provider_id}
            if remaining:
                self._sources[source] = frozenset(remaining)
            else:
                self._sources.pop(source, None)

    def supports_provider(self, provider_id: str) -> bool:
        if not is_canonical_provider_id(provider_id):
            return False
        with self._lock:
            return provider_id in self._static or any(provider_id in values for values in self._sources.values())

    def sources_for(self, provider_id: str) -> frozenset[str]:
        with self._lock:
            return frozenset(source for source, values in self._sources.items() if provider_id in values)

    def supports_after_removing(self, source: str, provider_id: str) -> bool:
        with self._lock:
            return provider_id in self._static or any(
                provider_id in values for current, values in self._sources.items() if current != source
            )


provider_support_registry = ProviderSupportRegistry()
