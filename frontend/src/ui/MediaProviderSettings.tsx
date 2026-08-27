import { useEffect, useRef, useState } from "react";
import { Cloud, HardDrive, RefreshCw, Save } from "lucide-react";
import {
  api,
  apiErrorView,
  type AssetProviderStatus,
  type VideoProviderStatus,
} from "../api";
import { Badge, Button, Panel } from "./primitives";
import "./MediaProviderSettings.css";

type Mode = "image" | "video" | "audio";
type AudioProviderStatus = Awaited<ReturnType<typeof api.audioProviders>>["items"][number];
type Draft = {
  id: string;
  displayName: string;
  endpoint: string;
  model: string;
  local: boolean;
  requiresCredential: boolean;
  enabled: boolean;
  apiStyle: "openai" | "comfyui" | "automatic1111";
  credentialConfigured: boolean;
  capabilities: string[];
};
type FieldErrors = Partial<
  Record<"id" | "endpoint" | "model" | "credential" | "capabilities", string>
>;
const emptyDraft: Draft = {
  id: "custom",
  displayName: "其他服务商",
  endpoint: "",
  model: "",
  local: false,
  requiresCredential: true,
  enabled: true,
  apiStyle: "openai",
  credentialConfigured: false,
  capabilities: ["TTS"],
};

const audioCapabilities = [
  ["TTS", "语音合成"], ["TEXT_TO_AUDIO", "文本生成音频"], ["SFX", "音效"],
  ["FOLEY", "拟音 / Foley"], ["MUSIC", "音乐"], ["AUDIO_EDIT", "音频编辑"],
  ["VIDEO_TO_AUDIO", "视频同步音频"],
] as const;

export function MediaProviderSettings() {
  const [mode, setMode] = useState<Mode>("image");
  const [images, setImages] = useState<AssetProviderStatus[]>([]);
  const [videos, setVideos] = useState<VideoProviderStatus[]>([]);
  const [audio, setAudio] = useState<AudioProviderStatus[]>([]);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [credential, setCredential] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const errorRef = useRef<HTMLDivElement>(null);
  async function refresh() {
    const [imageResult, videoResult, audioResult] = await Promise.all([
      api.assetProviders(),
      api.videoProviders(),
      api.audioProviders(),
    ]);
    setImages(imageResult.items || []);
    setVideos(videoResult.items || []);
    setAudio(audioResult.items || []);
  }
  useEffect(() => {
    void refresh().catch(() =>
      setError("Provider 状态读取失败，请检查本地服务。"),
    );
  }, []);
  const rows = mode === "image" ? images : mode === "video" ? videos : audio;
  function select(id: string) {
    setCredential("");
    setFieldErrors({});
    setError("");
    setMessage("");
    if (mode === "image") {
      const item = images.find((value) => value.provider_id === id);
      if (!item) return;
      setDraft({
        id: item.provider_id,
        displayName: item.display_name || item.provider_id,
        endpoint: item.endpoint || "",
        model: item.default_model,
        local: Boolean(item.local),
        requiresCredential: item.requires_credential !== false,
        enabled: item.enabled !== false,
        apiStyle: item.api_style || "openai",
        credentialConfigured: Boolean(item.credential_configured),
        capabilities: [],
      });
    } else if (mode === "video") {
      const item = videos.find((value) => value.id === id);
      if (!item) return;
      setDraft({
        id: item.id,
        displayName: item.display_name,
        endpoint: item.endpoint,
        model: item.model,
        local: item.local,
        requiresCredential: item.requires_credential,
        enabled: true,
        apiStyle: "openai",
        credentialConfigured: item.credential_configured,
        capabilities: [],
      });
    } else {
      const item = audio.find((value) => value.provider_id === id);
      if (!item) return;
      setDraft({id:item.provider_id,displayName:item.display_name||item.provider_id,endpoint:item.endpoint||"",model:item.default_model,local:Boolean(item.local),requiresCredential:item.requires_credential!==false,enabled:item.enabled!==false,apiStyle:"openai",credentialConfigured:Boolean(item.credential_configured),capabilities:item.capabilities||["TTS"]});
    }
  }
  useEffect(() => {
    const first = mode === "image" ? images[0] : mode === "video" ? videos[0] : audio[0];
    if (first)
      select(
        mode === "image"
          ? (first as AssetProviderStatus).provider_id
          : mode === "video" ? (first as VideoProviderStatus).id : (first as AudioProviderStatus).provider_id,
      );
    else setDraft(emptyDraft);
  }, [mode, images.length, videos.length, audio.length]);
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    const issues: FieldErrors = {};
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(draft.id))
      issues.id = "只能使用字母、数字、下划线和连字符，最多 64 位。";
    try {
      const parsed = new URL(draft.endpoint);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:")
        issues.endpoint = "服务地址必须以 http:// 或 https:// 开头。";
    } catch {
      issues.endpoint = "请输入完整的 http:// 或 https:// 服务地址。";
    }
    if (!draft.model.trim())
      issues.model =
        mode === "image" && draft.apiStyle === "comfyui"
          ? "请填写 ComfyUI checkpoint 文件名。"
          : "请填写模型 ID。";
    if (mode === "audio" && !draft.capabilities.length)
      issues.capabilities = "至少选择一种声音能力。";
    if (
      draft.requiresCredential &&
      !draft.credentialConfigured &&
      !credential.trim()
    )
      issues.credential = "该云端服务需要独立密钥；密钥只会写入系统凭据库。";
    setFieldErrors(issues);
    if (Object.keys(issues).length) {
      requestAnimationFrame(() => errorRef.current?.focus());
      return;
    }
    setLoading(true);
    try {
      if (draft.requiresCredential && credential.trim())
        await api.saveCredential(draft.id, credential.trim());
      if (mode === "image")
        await api.configureAssetProvider(draft.id, {
          endpoint: draft.endpoint,
          default_model: draft.model,
          api_style: draft.apiStyle,
          local: draft.local,
          enabled: draft.enabled,
          requires_credential: draft.requiresCredential,
          display_name: draft.displayName,
        });
      else if (mode === "video")
        await api.configureVideoProvider(draft.id, {
          endpoint: draft.endpoint,
          model_id: draft.model,
          enabled: draft.enabled,
          local: draft.local,
          requires_credential: draft.requiresCredential,
          display_name: draft.displayName,
        });
      else await api.configureAudioProvider(draft.id,{endpoint:draft.endpoint,default_model:draft.model,display_name:draft.displayName,local:draft.local,enabled:draft.enabled,requires_credential:draft.requiresCredential,capabilities:draft.capabilities});
      setCredential("");
      setMessage("配置已保存，路由将优先选择可用的本地 Provider。");
      await refresh();
    } catch (reason) {
      setError(apiErrorView(reason, "Provider 配置保存失败。").message);
    } finally {
      setLoading(false);
    }
  }
  function providerState(item: AssetProviderStatus | VideoProviderStatus | AudioProviderStatus) {
    const configured =
      "configured" in item
        ? Boolean(item.configured)
        : Boolean("available" in item && (item.available || item.endpoint));
    const reachable =
      "reachable" in item
        ? Boolean(item.reachable)
        : Boolean("available" in item && item.available);
    if (!configured) return { label: "未配置", tone: "neutral" as const };
    if (!reachable) return { label: "不可达", tone: "warning" as const };
    return { label: "就绪", tone: "success" as const };
  }
  return (
    <Panel
      title="媒体 Provider"
      actions={
        <Button
          title="刷新 Provider"
          aria-label="刷新 Provider"
          onClick={() => void refresh()}
        >
          <RefreshCw aria-hidden="true" size={16} />
        </Button>
      }
      className="media-provider-settings"
    >
      <div
        className="media-provider-settings__tabs"
        role="tablist"
        aria-label="媒体类型"
      >
        <button
          role="tab"
          aria-selected={mode === "image"}
          onClick={() => setMode("image")}
        >
          图片
        </button>
        <button
          role="tab"
          aria-selected={mode === "video"}
          onClick={() => setMode("video")}
        >
          视频
        </button>
        <button role="tab" aria-selected={mode === "audio"} onClick={() => setMode("audio")}>声音</button>
      </div>
      <div className="media-provider-settings__layout">
        <nav
          aria-label={`${mode === "image" ? "图片" : mode === "video" ? "视频" : "声音"} Provider`}
          className="media-provider-settings__list"
        >
          {rows.map((item) => {
            const id = "provider_id" in item ? item.provider_id : item.id;
            const name = ("display_name" in item && item.display_name) || id;
            const local = Boolean(item.local);
            const state = providerState(item);
            return (
              <button
                type="button"
                key={id}
                aria-current={draft.id === id ? "true" : undefined}
                onClick={() => select(id)}
              >
                {local ? (
                  <HardDrive aria-hidden="true" size={16} />
                ) : (
                  <Cloud aria-hidden="true" size={16} />
                )}
                <span>
                  <strong title={name}>{name}</strong>
                  <small>
                    {local ? "本地" : "云端"} · {state.label}
                  </small>
                </span>
                <Badge tone={state.tone}>{state.label}</Badge>
              </button>
            );
          })}
          <button
            type="button"
            aria-current={
              !rows.some(
                (item) =>
                  ("provider_id" in item ? item.provider_id : item.id) ===
                  draft.id,
              )
                ? "true"
                : undefined
            }
            onClick={() => {
              setCredential("");
              setFieldErrors({});
              setDraft({ ...emptyDraft, id: `custom-${mode}`, capabilities: mode === "audio" ? ["TTS"] : [] });
            }}
          >
            + 其他服务商
          </button>
        </nav>
        <form className="media-provider-settings__form" onSubmit={save}>
          {Object.keys(fieldErrors).length > 0 && (
            <div
              className="media-provider-settings__error-summary"
              role="alert"
              tabIndex={-1}
              ref={errorRef}
            >
              <strong>配置尚未保存</strong>
              <span>请修正标出的字段后重试。</span>
            </div>
          )}
          <div className="media-provider-settings__form-grid">
            <label htmlFor="media-provider-id">
              Provider ID
              <input
                id="media-provider-id"
                aria-invalid={Boolean(fieldErrors.id)}
                aria-describedby={
                  fieldErrors.id ? "media-provider-id-error" : undefined
                }
                value={draft.id}
                onChange={(event) => {
                  setFieldErrors((value) => ({ ...value, id: undefined }));
                  setDraft((value) => ({
                    ...value,
                    id: event.target.value,
                    credentialConfigured: false,
                  }));
                }}
              />
              {fieldErrors.id && (
                <small
                  id="media-provider-id-error"
                  className="media-provider-settings__field-error"
                >
                  {fieldErrors.id}
                </small>
              )}
            </label>
            <label htmlFor="media-provider-name">
              显示名称
              <input
                id="media-provider-name"
                value={draft.displayName}
                onChange={(event) =>
                  setDraft((value) => ({
                    ...value,
                    displayName: event.target.value,
                  }))
                }
              />
            </label>
          </div>
          <label htmlFor="media-provider-endpoint">
            服务地址
            <input
              id="media-provider-endpoint"
              aria-invalid={Boolean(fieldErrors.endpoint)}
              aria-describedby={
                fieldErrors.endpoint
                  ? "media-provider-endpoint-error"
                  : undefined
              }
              value={draft.endpoint}
              onBlur={() => {
                if (draft.endpoint && !/^https?:\/\//i.test(draft.endpoint))
                  setFieldErrors((value) => ({
                    ...value,
                    endpoint: "服务地址必须以 http:// 或 https:// 开头。",
                  }));
              }}
              onChange={(event) => {
                setFieldErrors((value) => ({ ...value, endpoint: undefined }));
                setDraft((value) => ({
                  ...value,
                  endpoint: event.target.value,
                }));
              }}
              placeholder={
                draft.local
                  ? "http://127.0.0.1:8188"
                  : "https://provider.example/v1"
              }
            />
            {fieldErrors.endpoint && (
              <small
                id="media-provider-endpoint-error"
                className="media-provider-settings__field-error"
              >
                {fieldErrors.endpoint}
              </small>
            )}
          </label>
          <label htmlFor="media-provider-model">
            模型 ID / Checkpoint
            <input
              id="media-provider-model"
              aria-invalid={Boolean(fieldErrors.model)}
              aria-describedby={
                fieldErrors.model ? "media-provider-model-error" : undefined
              }
              value={draft.model}
              onChange={(event) => {
                setFieldErrors((value) => ({ ...value, model: undefined }));
                setDraft((value) => ({ ...value, model: event.target.value }));
              }}
              placeholder={
                draft.apiStyle === "comfyui"
                  ? "model.safetensors"
                  : "provider-model-id"
              }
            />
            {fieldErrors.model && (
              <small
                id="media-provider-model-error"
                className="media-provider-settings__field-error"
              >
                {fieldErrors.model}
              </small>
            )}
          </label>
          {mode === "image" && (
            <label>
              接口协议
              <select
                value={draft.apiStyle}
                onChange={(event) => {
                  const apiStyle = event.target.value as Draft["apiStyle"];
                  setDraft((value) => ({
                    ...value,
                    apiStyle,
                    local: apiStyle !== "openai",
                    requiresCredential: apiStyle === "openai",
                  }));
                }}
              >
                <option value="openai">OpenAI-compatible</option>
                <option value="comfyui">ComfyUI</option>
                <option value="automatic1111">Stable Diffusion WebUI</option>
              </select>
            </label>
          )}
          {mode === "audio" && <fieldset className="media-provider-settings__capabilities" aria-describedby={fieldErrors.capabilities?"audio-capabilities-error":undefined}><legend>支持的声音能力</legend>{audioCapabilities.map(([value,label])=><label key={value}><input type="checkbox" checked={draft.capabilities.includes(value)} onChange={event=>{setFieldErrors(current=>({...current,capabilities:undefined}));setDraft(current=>({...current,capabilities:event.target.checked?[...current.capabilities,value]:current.capabilities.filter(item=>item!==value)}))}}/>{label}</label>)}{fieldErrors.capabilities&&<small id="audio-capabilities-error" className="media-provider-settings__field-error">{fieldErrors.capabilities}</small>}</fieldset>}
          <div className="media-provider-settings__checks">
            <label>
              <input
                type="checkbox"
                checked={draft.local}
                onChange={(event) =>
                  setDraft((value) => ({
                    ...value,
                    local: event.target.checked,
                  }))
                }
              />
              本地服务
            </label>
            <label>
              <input
                type="checkbox"
                checked={draft.enabled}
                onChange={(event) =>
                  setDraft((value) => ({
                    ...value,
                    enabled: event.target.checked,
                  }))
                }
              />
              启用
            </label>
            <label>
              <input
                type="checkbox"
                checked={draft.requiresCredential}
                onChange={(event) =>
                  setDraft((value) => ({
                    ...value,
                    requiresCredential: event.target.checked,
                  }))
                }
              />
              需要密钥
            </label>
          </div>
          {draft.requiresCredential && (
            <label htmlFor="media-provider-key">
              API Key / Token
              <input
                id="media-provider-key"
                aria-invalid={Boolean(fieldErrors.credential)}
                aria-describedby={
                  fieldErrors.credential
                    ? "media-provider-key-error"
                    : undefined
                }
                type="password"
                value={credential}
                onChange={(event) => {
                  setFieldErrors((value) => ({
                    ...value,
                    credential: undefined,
                  }));
                  setCredential(event.target.value);
                }}
                autoComplete="new-password"
                placeholder={
                  draft.credentialConfigured
                    ? "已安全保存；留空保持不变"
                    : "输入服务商密钥"
                }
              />
              {fieldErrors.credential && (
                <small
                  id="media-provider-key-error"
                  className="media-provider-settings__field-error"
                >
                  {fieldErrors.credential}
                </small>
              )}
            </label>
          )}
          {error && (
            <p className="media-provider-settings__error" role="alert">
              {error}
            </p>
          )}
          {message && (
            <p className="notice" role="status">
              {message}
            </p>
          )}
          <Button type="submit" variant="primary" loading={loading}>
            <Save aria-hidden="true" size={16} />
            保存 Provider
          </Button>
        </form>
      </div>
    </Panel>
  );
}
