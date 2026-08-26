from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from .model_runtime import Modality, ModelRuntimeError, RuntimeErrorCode


WORKFLOW_CONTRACT_VERSION = "visual-text-workflow/v2"
SAFE_CAPABILITIES = frozenset({"generate", "stream", "structured_output"})


def _safe_label(value: str) -> str:
    lowered = value.casefold()
    if any(marker in lowered for marker in ("api_key", "authorization", "bearer ", "credential", "sk-")):
        return "文本模型"
    return value


class WorkflowNodeView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stable_id: str
    kind: str
    label: str
    summary: str
    production_boundary: str
    capabilities: tuple[str, ...] = ()
    provider_id: str | None = None
    model_id: str | None = None
    available: bool | None = None


class WorkflowEdgeView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    target: str
    relationship: str


class VisualTextWorkflowView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_contract_version: str
    title: str
    description: str
    read_only: bool
    nodes: tuple[WorkflowNodeView, ...]
    edges: tuple[WorkflowEdgeView, ...]


@dataclass(frozen=True, slots=True)
class VisualTextWorkflowAdapter:
    provider_registry: object
    model_registry: object

    def compose(self, provider_id: str, model_id: str) -> VisualTextWorkflowView:
        model = self.model_registry.resolve(provider_id, model_id, Modality.TEXT)
        if not model.streaming or "stream" not in model.capabilities:
            raise ModelRuntimeError(RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED, "当前模型不支持流式文本生成")
        providers = {item.provider_id: item for item in self.provider_registry.descriptors()}
        provider = providers.get(provider_id)
        if provider is None:
            raise ModelRuntimeError(RuntimeErrorCode.PROVIDER_NOT_FOUND, "未找到指定的模型服务")
        available = bool(provider.configured and provider.available and model.enabled)
        model_node_id = f"text-model:{provider_id}:{model_id}"
        return VisualTextWorkflowView(
            workflow_contract_version=WORKFLOW_CONTRACT_VERSION,
            title="文本生成流程",
            description="只读展示当前文本模型如何接收上下文并产生待确认草稿。",
            read_only=True,
            nodes=(
                WorkflowNodeView(
                    stable_id="context:privacy-filtered",
                    kind="context",
                    label="隐私筛选上下文",
                    summary="只将当前任务允许使用的小说与章节信息送入生成流程。",
                    production_boundary="context.privacy_filter",
                    capabilities=("结构化摘要", "隐私筛选"),
                ),
                WorkflowNodeView(
                    stable_id=model_node_id,
                    kind="text_model",
                    label=_safe_label(model.display_name),
                    summary="通过现有文本模型运行时生成草稿。",
                    production_boundary="runtime.text_model_node",
                    capabilities=tuple(sorted(SAFE_CAPABILITIES.intersection(model.capabilities))),
                    provider_id=provider_id,
                    model_id=model_id,
                    available=available,
                ),
                WorkflowNodeView(
                    stable_id="stream:generation-events",
                    kind="stream",
                    label="流式生成",
                    summary="沿用现有开始、增量和完成事件，并可按原有规则取消。",
                    production_boundary="runtime.generation_events",
                    capabilities=("增量输出", "可取消"),
                ),
                WorkflowNodeView(
                    stable_id="draft:diff-preview",
                    kind="draft",
                    label="草稿与差异预览",
                    summary="生成内容先保留为草稿，并与当前正文显示差异。",
                    production_boundary="generation.draft_diff",
                    capabilities=("草稿隔离", "差异预览"),
                ),
                WorkflowNodeView(
                    stable_id="accept:explicit",
                    kind="accept",
                    label="显式采用",
                    summary="只有作者主动采用且版本检查通过后，草稿才会进入正文。",
                    production_boundary="generation.explicit_accept",
                    capabilities=("版本检查", "作者确认"),
                ),
                WorkflowNodeView(
                    stable_id="revision:immutable",
                    kind="revision",
                    label="创建新修订",
                    summary="采用结果写入新的不可变修订，既有历史继续保留。",
                    production_boundary="revision.immutable_append",
                    capabilities=("AI_ACCEPT", "历史保留"),
                ),
            ),
            edges=(
                WorkflowEdgeView(source="context:privacy-filtered", target=model_node_id, relationship="提供经过筛选的创作信息"),
                WorkflowEdgeView(source=model_node_id, target="stream:generation-events", relationship="沿用现有流式事件"),
                WorkflowEdgeView(source="stream:generation-events", target="draft:diff-preview", relationship="形成待确认草稿"),
                WorkflowEdgeView(source="draft:diff-preview", target="accept:explicit", relationship="等待作者明确决定"),
                WorkflowEdgeView(source="accept:explicit", target="revision:immutable", relationship="通过版本检查后写入"),
            ),
        )
