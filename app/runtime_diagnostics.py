from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from .model_runtime import Modality, ModelRuntimeError, RuntimeErrorCode


DIAGNOSTICS_CONTRACT_VERSION = "text-runtime-diagnostics/v1"
SAFE_CAPABILITIES = frozenset({"generate", "stream", "structured_output"})


class TextRuntimeState(StrEnum):
    READY = "READY"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNAVAILABLE = "UNAVAILABLE"
    MODEL_DISABLED = "MODEL_DISABLED"
    STREAMING_UNSUPPORTED = "STREAMING_UNSUPPORTED"


class TextRuntimeDiagnosticsView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    diagnostics_contract_version: str
    read_only: bool
    provider_id: str
    model_id: str
    state: TextRuntimeState
    state_label: str
    explanation: str
    author_action: str
    safe_capabilities: tuple[str, ...]


_PRESENTATION = {
    TextRuntimeState.READY: ("可用", "所选文本路线已具备现有流式生成能力。", "可以返回写作面板开始生成。"),
    TextRuntimeState.NOT_CONFIGURED: ("未配置", "所选模型服务尚未由运行环境配置。", "请联系运行环境管理员完成模型服务配置。"),
    TextRuntimeState.UNAVAILABLE: ("暂时不可用", "所选模型服务当前不可用。", "请稍后重试，或联系运行环境管理员检查服务状态。"),
    TextRuntimeState.MODEL_DISABLED: ("模型已停用", "所选模型已在运行环境中停用。", "请选择其他已启用的文本模型。"),
    TextRuntimeState.STREAMING_UNSUPPORTED: ("不支持流式生成", "所选模型不满足当前写作流程的流式能力要求。", "请选择支持流式生成的文本模型。"),
}


@dataclass(frozen=True, slots=True)
class TextRuntimeDiagnosticsAdapter:
    provider_registry: object
    model_registry: object

    def diagnose(self, provider_id: str, model_id: str) -> TextRuntimeDiagnosticsView:
        providers = {item.provider_id: item for item in self.provider_registry.descriptors()}
        models = {(item.provider_id, item.model_id): item for item in self.model_registry.descriptors()}
        provider = providers.get(provider_id)
        if provider is None:
            raise ModelRuntimeError(RuntimeErrorCode.PROVIDER_NOT_FOUND, "未找到指定的模型服务")
        model = models.get((provider_id, model_id))
        if model is None:
            raise ModelRuntimeError(RuntimeErrorCode.MODEL_NOT_FOUND, "未找到指定模型")
        if model.modality is not Modality.TEXT:
            raise ModelRuntimeError(RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED, "所选模型不是文本模型")

        if not provider.configured:
            state = TextRuntimeState.NOT_CONFIGURED
        elif not provider.available:
            state = TextRuntimeState.UNAVAILABLE
        elif not model.enabled:
            state = TextRuntimeState.MODEL_DISABLED
        elif not model.streaming or "stream" not in model.capabilities:
            state = TextRuntimeState.STREAMING_UNSUPPORTED
        else:
            state = TextRuntimeState.READY

        label, explanation, action = _PRESENTATION[state]
        return TextRuntimeDiagnosticsView(
            diagnostics_contract_version=DIAGNOSTICS_CONTRACT_VERSION,
            read_only=True,
            provider_id=provider_id,
            model_id=model_id,
            state=state,
            state_label=label,
            explanation=explanation,
            author_action=action,
            safe_capabilities=tuple(sorted(SAFE_CAPABILITIES.intersection(model.capabilities))),
        )
