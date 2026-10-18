import { useEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { createModelCenterClient } from './modelCenterClient';
import type { ModelCenterPanelProps } from './modelCenterTypes';

/** Configuration hints for existing Runtime.register_native_text_route only. */
export const nativeTextHints = {
  claude: { label: 'Claude', variable: 'ANTHROPIC_MODEL', baseUrl: 'https://api.anthropic.com/v1',
    protocol: 'Anthropic Messages', reference: 'https://platform.claude.com/docs/en/api/overview' },
  gemini: { label: 'Gemini', variable: 'GEMINI_MODEL', baseUrl: 'https://generativelanguage.googleapis.com/v1beta',
    protocol: 'Gemini generateContent', reference: 'https://ai.google.dev/api/generate-content' },
} as const;
export function nativeTextHostPreview(provider: string, model: string): string | undefined {
  if (!Object.hasOwn(nativeTextHints, provider) || !/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$/.test(model)
      || model.split('/').some(part => part === '.' || part === '..')) return;
  return `${nativeTextHints[provider as keyof typeof nativeTextHints].variable}=${model}`;
}
type Props = Pick<ModelCenterPanelProps, 'projectId' | 'transport' | 'scope' | 'identity' | 'active' | 'denied' | 'busy' | 'isCurrent'>;
export function NativeTextPresetPanel(props: Props) {
  const key = JSON.stringify([props.projectId, props.scope, props.identity, props.active, props.denied]);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const owner = useRef({key, transport: props.transport, token: {}});
  if (owner.current.key !== key || owner.current.transport !== props.transport) owner.current = {key, transport: props.transport, token: {}};
  const token = owner.current.token;
  const latest = useRef(props); latest.current = props;
  const [state, setState] = useState<{token: object; provider: string; model: string}>();
  let validProject = true;
  try { createModelCenterClient(props.projectId, props.transport, props.scope); } catch { validProject = false; }
  // The original client defers this scope fence until a read; this local-only
  // guide makes the same check without issuing any request.
  if (props.scope && props.scope.projectId !== props.projectId) validProject = false;
  const current = () => alive.current && owner.current.token === token && validProject && latest.current.active
    && !latest.current.denied && !latest.current.busy && latest.current.isCurrent();
  if (!props.active || props.denied || !props.isCurrent()) return null;
  const visible = state?.token === token ? state : undefined;
  const hint = visible && Object.hasOwn(nativeTextHints, visible.provider)
    ? nativeTextHints[visible.provider as keyof typeof nativeTextHints] : undefined;
  const preview = visible ? nativeTextHostPreview(visible.provider, visible.model) : undefined;
  const change = (field: 'provider' | 'model', value: string) => {
    if (!current()) return;
    setState(previous => previous?.token === token ? {...previous, [field]: value,
      ...(field === 'provider' ? {model: ''} : {})} : previous);
  };
  return <section aria-label="原生云端文本连接预设">
    <h3>Claude / Gemini · 文本连接预设</h3>
    <p>沿用现有原生文本适配器，只准备手动主机配置提示；不读取当前配置、收集密钥、联网检测或启用路线。</p>
    <Button disabled={!validProject || props.busy} onClick={() => { if (current()) setState({token, provider: '', model: ''}); }}>查看 Claude / Gemini 文本预设</Button>
    {!validProject && <StatusMessage tone="warning">当前项目上下文无效，预设提示已停用。</StatusMessage>}
    {visible && <>
      <label>原生文本 API 平台<select value={visible.provider} disabled={props.busy} onChange={event => change('provider', event.target.value)}>
        <option value="">明确选择平台</option><option value="claude">Claude</option><option value="gemini">Gemini</option>
      </select></label>
      <label>平台文本模型 ID<input value={visible.model} maxLength={200} disabled={props.busy} placeholder="填写平台账户实际可用的模型 ID" onChange={event => change('model', event.target.value)} /></label>
      {hint && <><p>原适配协议：{hint.protocol}；内置 Base URL：{hint.baseUrl}。</p>
        <a href={hint.reference} target="_blank" rel="noreferrer">查看 {hint.label} 官方 API 说明</a></>}
      {preview ? <label>原生文本主机配置预览（未应用）<textarea readOnly value={preview} /></label>
        : <StatusMessage>选择平台并填写有效模型 ID 后显示提示。不会猜测最新模型、账户可用性或价格。</StatusMessage>}
      <p>仅对应原生文本请求，不代表图片、视频、工具调用或云厂商转接平台已接通。密钥继续使用原凭据入口。
        应用配置、检查来源隐私及确认调用费用仍需单独操作；本地／云端偏好不会改变。</p>
    </>}
  </section>;
}
