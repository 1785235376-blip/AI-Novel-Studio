import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Button, Panel } from "../ui/primitives";
import {
  FOCUS_FAILED_TASKS_EVENT,
  publishTaskSummary,
} from "../ui/taskSummary";
import type { ImageInspection } from "./ImageTaskInspector";
import { addImageToCanvas } from "./imageCanvasEvents";
import { safeImagePreviewUri } from "./ImageInfiniteCanvas";

type ImageProvider = {
  provider_id: string;
  display_name?: string;
  default_model: string;
  configured: boolean;
  registered: boolean;
  reachable?: boolean;
  local?: boolean;
};
type ImageTask = {
  id: string;
  status: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";
  prompt: string;
  provider_id: string;
  model_id: string;
  asset_uri?: string;
  error?: string;
};

export function ImageGenerationPanel({
  novelId,
  characterId,
  sceneId,
  onInspect,
}: {
  novelId?: string;
  characterId?: string;
  sceneId?: string;
  onInspect?: (inspection?: ImageInspection) => void;
}) {
  const [prompt, setPrompt] = useState("生成适合小说设定的角色或场景概念图。");
  const [referenceInput, setReferenceInput] = useState("");
  const [uri, setUri] = useState(""),
    [history, setHistory] = useState<any[]>([]),
    [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [imported, setImported] = useState(false);
  const [providers, setProviders] = useState<ImageProvider[]>([]),
    [providerId, setProviderId] = useState(""),
    [modelId, setModelId] = useState(""),
    [task, setTask] = useState<ImageTask | null>(null);
  const generateButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (novelId)
      api
        .imageGenerations(novelId, characterId, sceneId)
        .then((data) => setHistory(data.items || []))
        .catch(() => setHistory([]));
  }, [novelId, characterId, sceneId]);
  useEffect(() => {
    let active = true;
    api
      .assetProviders()
      .then((data) => {
        if (!active) return;
        const items = data.items || [];
        setProviders(items);
        const preferred = items.find(
          (item) =>
            item.configured && item.registered && item.reachable !== false,
        );
        if (preferred) {
          setProviderId(preferred.provider_id);
          setModelId(preferred.default_model);
        }
      })
      .catch(() => {
        if (active) setProviders([]);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    publishTaskSummary("image", task ? [task] : []);
  }, [task]);
  useEffect(() => {
    onInspect?.(
      task
        ? {
            id: task.id,
            status: task.status,
            providerId: task.provider_id,
            modelId: task.model_id,
            assetUri: task.asset_uri,
            error: task.error,
            imported,
          }
        : undefined,
    );
  }, [task, imported, onInspect]);
  useEffect(() => {
    const listener = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (
        detail?.source === "image" &&
        (!detail.taskId ||
          String(detail.taskId) === String(task?.id || "image-task"))
      )
        requestAnimationFrame(() => generateButton.current?.focus());
    };
    window.addEventListener(FOCUS_FAILED_TASKS_EVENT, listener);
    return () => window.removeEventListener(FOCUS_FAILED_TASKS_EVENT, listener);
  }, [task]);
  async function generate() {
    const requestPrompt = prompt.trim(),
      requestProvider = providerId,
      requestModel = modelId.trim();
    if (!requestPrompt || !requestProvider || !requestModel) return;
    setLoading(true);
    setError("");
    setUri("");
    setImported(false);
    setTask({
      id: "image-task",
      status: "QUEUED",
      prompt: requestPrompt,
      provider_id: requestProvider,
      model_id: requestModel,
    });
    try {
      setTask((current) =>
        current ? { ...current, status: "RUNNING" } : current,
      );
      const references = referenceInput.split(/\r?\n/).map((value) => value.trim()).filter(Boolean);
      const result = references.length
        ? await api.imageEdit({
            provider_id: requestProvider,
            model_id: requestModel,
            prompt: requestPrompt,
            images: references,
            size: "auto",
            quality: "auto",
            output_format: "png",
            novel_id: novelId,
            character_id: characterId,
            scene_id: sceneId,
          })
        : await api.imageGenerate({
            provider_id: requestProvider,
            model_id: requestModel,
            prompt: requestPrompt,
            novel_id: novelId,
            character_id: characterId,
            scene_id: sceneId,
          });
      setUri(result.asset_uri);
      setTask((current) =>
        current
          ? { ...current, status: "SUCCEEDED", asset_uri: result.asset_uri }
          : current,
      );
    } catch {
      const message = referenceInput.trim()
        ? "参考图融合失败，请检查图片地址、数量和 Provider 配置。"
        : "图片生成失败，请检查 Provider 配置。";
      setError(message);
      setTask((current) =>
        current ? { ...current, status: "FAILED", error: message } : current,
      );
    } finally {
      setLoading(false);
    }
  }
  const available = providers.some(
    (item) => item.configured && item.registered && item.reachable !== false,
  );
  const previewUri = safeImagePreviewUri(uri);
  const references = referenceInput.split(/\r?\n/).map((value) => value.trim()).filter(Boolean);
  const referencesValid = references.length <= 5 && references.every((value) => /^https?:\/\//i.test(value) || /^data:image\//i.test(value));
  return (
    <Panel title="图片生成">
      <label>
        图片 Provider
        <select
          aria-label="图片 Provider"
          value={providerId}
          onChange={(event) => {
            const next = providers.find(
              (item) => item.provider_id === event.target.value,
            );
            setProviderId(event.target.value);
            setModelId(next?.default_model || "");
          }}
        >
          <option value="">选择已配置 Provider</option>
          {providers.map((item) => (
            <option
              key={item.provider_id}
              value={item.provider_id}
              disabled={
                !item.configured || !item.registered || item.reachable === false
              }
            >
              {item.display_name || item.provider_id}
              {item.local ? " · 本地" : ""}
              {item.configured && item.registered && item.reachable !== false
                ? ""
                : "（不可用）"}
            </option>
          ))}
        </select>
      </label>
      <label>
        模型
        <input
          aria-label="图片模型"
          value={modelId}
          onChange={(event) => setModelId(event.target.value)}
        />
      </label>
      <label>
        生成描述
        <textarea
          rows={5}
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
        />
      </label>
      <details>
        <summary>多参考图融合{references.length ? `（${references.length}）` : ""}</summary>
        <label>
          参考图地址（每行一张，最多 5 张）
          <textarea
            aria-label="多参考图地址"
            rows={4}
            value={referenceInput}
            placeholder="https://... 或 data:image/..."
            onChange={(event) => setReferenceInput(event.target.value)}
          />
        </label>
        <p className="novel-help">填写后将调用 DDSHub 图片编辑接口；参考图用于角色、构图、服装或场景一致性约束。</p>
        {references.length > 0 && !referencesValid && <p role="alert">仅支持 1–5 个 http(s) 或 data:image 地址。</p>}
      </details>
      <Button
        ref={generateButton}
        disabled={loading || !prompt.trim() || !providerId || !modelId.trim() || !referencesValid || (references.length > 0 && providerId !== "ddshub")}
        onClick={generate}
      >
        {loading ? "生成中…" : references.length ? "融合参考图" : "生成图片"}
      </Button>
      {references.length > 0 && providerId !== "ddshub" && <p role="alert">当前多参考图融合仅支持 DDSHub Provider。</p>}
      {!available && (
        <p className="novel-help">请先在主控中配置并连接图片 Provider。</p>
      )}
      {task && (
        <p className="novel-help" aria-live="polite">
          任务状态：
          {task.status === "QUEUED"
            ? "已提交，等待执行"
            : task.status === "RUNNING"
              ? "执行中"
              : task.status === "SUCCEEDED"
                ? "已完成"
                : "失败"}
          {task.error ? ` · ${task.error}` : ""}
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {uri && (
        <div>
          {previewUri ? (
            <img
              src={previewUri}
              alt="生成结果"
              referrerPolicy="no-referrer"
              style={{ maxWidth: "100%", maxHeight: 360 }}
            />
          ) : (
            <p role="alert">Provider 返回了不受支持的图片地址，已阻止预览。</p>
          )}
          <p className="novel-help">结果地址：{uri}</p>
          <Button
            variant="ghost"
            disabled={!previewUri}
            onClick={() =>
              addImageToCanvas({
                novelId,
                uri,
                source: "generation",
                role: characterId ? "角色" : sceneId ? "场景" : "构图",
                providerId: task?.provider_id,
                modelId: task?.model_id,
              })
            }
          >
            加入画布
          </Button>
          {novelId && (
            <Button
              variant="ghost"
              onClick={async () => {
                await api.importGeneratedImage(novelId, {
                  asset_uri: uri,
                  character_id: characterId,
                  scene_id: sceneId,
                });
                setImported(true);
              }}
            >
              {imported ? "已导入资产库" : "导入资产库"}
            </Button>
          )}
        </div>
      )}
      {history.length > 0 && (
        <details>
          <summary>生成历史（{history.length}）</summary>
          {history.map((item: any, index: number) => (
            <p key={`${item.created_at}-${index}`} className="novel-help">
              {item.created_at} · {item.prompt} ·{" "}
              <Button
                variant="ghost"
                onClick={() => {
                  setUri(item.asset_uri);
                  setPrompt(item.prompt || prompt);
                  setImported(false);
                  setTask({
                    id: String(item.id || `history-${index + 1}`),
                    status: "SUCCEEDED",
                    prompt: item.prompt || "",
                    provider_id: item.provider_id || providerId,
                    model_id: item.model_id || modelId,
                    asset_uri: item.asset_uri,
                  });
                }}
              >
                预览
              </Button>
              <Button
                variant="ghost"
                disabled={!item.asset_uri}
                onClick={() =>
                  addImageToCanvas({
                    novelId,
                    uri: item.asset_uri,
                    source: "generation",
                    role: characterId ? "角色" : sceneId ? "场景" : "构图",
                    providerId: item.provider_id,
                    modelId: item.model_id,
                  })
                }
              >
                加入画布
              </Button>
            </p>
          ))}
        </details>
      )}
    </Panel>
  );
}
