from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}

@dataclass(frozen=True)
class Settings:
    root: Path = Path(os.getenv("PROJECT_ROOT", Path(__file__).resolve().parents[1])).resolve()
    novel_data: Path = Path(os.getenv("NOVEL_DATA_PATH", "novel_data"))
    profile: str = os.getenv("CREATION_PROFILE", "HYBRID").upper()
    enable_cloud: bool = _bool("ENABLE_CLOUD", True)
    enable_fallback: bool = _bool("ENABLE_PROVIDER_FALLBACK", True)
    ollama_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    local_model: str = os.getenv("LOCAL_UTILITY_MODEL", "qwen2.5:7b-instruct-q4_K_M")
    max_revisions: int = int(os.getenv("MAX_REVISION_COUNT", "2"))
    mock_provider: bool = _bool("MOCK_PROVIDER", False)
    mock_delay_ms: int = int(os.getenv("MOCK_STREAM_DELAY_MS", "35"))
    mock_failure: str = os.getenv("MOCK_FAILURE_MODE", "")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    prompt_path: Path = Path(os.getenv("PROMPT_PATH", "prompts"))
    storage_backend: str = os.getenv("STORAGE_BACKEND", "file").strip().lower()
    database_url: str = os.getenv("DATABASE_URL", "")
    enable_lore_context: bool = _bool("ENABLE_LORE_CONTEXT", False)
    enable_narrative_context: bool = _bool("ENABLE_NARRATIVE_CONTEXT", False)
    narrative_context_token_budget: int = int(os.getenv("NARRATIVE_CONTEXT_TOKEN_BUDGET", "800"))
    context_policy_token_budget: int = int(os.getenv("CONTEXT_POLICY_TOKEN_BUDGET", "2400"))
    enable_continuity_rules: bool = _bool("ENABLE_CONTINUITY_RULES", False)
    enable_optimistic_concurrency: bool = _bool("ENABLE_OPTIMISTIC_CONCURRENCY", False)
    enable_context_pack_v2: bool = _bool("ENABLE_CONTEXT_PACK_V2", False)
    autosave_idle_debounce_seconds: float = float(os.getenv("AUTOSAVE_IDLE_DEBOUNCE_SECONDS", "3"))
    autosave_periodic_seconds: float = float(os.getenv("AUTOSAVE_PERIODIC_SECONDS", "30"))
    enable_collaboration_runtime: bool = _bool("ENABLE_COLLABORATION_RUNTIME", False)
    enable_packaged_runtime: bool = _bool("ENABLE_PACKAGED_RUNTIME", False)
    collaboration_dev_sessions_json: str = os.getenv("COLLABORATION_DEV_SESSIONS_JSON", "")
    outbound_loopback_allowlist: str = os.getenv("OUTBOUND_LOOPBACK_ALLOWLIST", "")
    credential_vault_backend: str = os.getenv("CREDENTIAL_VAULT_BACKEND", "auto")
    credential_vault_service: str = os.getenv("CREDENTIAL_VAULT_SERVICE", "AI-Novel-Studio")
    credential_vault_allow_memory_fallback: bool = _bool("CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK", not _bool("ENABLE_PACKAGED_RUNTIME", False))

    def data_path(self) -> Path:
        return self.novel_data if self.novel_data.is_absolute() else self.root / self.novel_data

settings = Settings()
