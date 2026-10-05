import { useEffect, useRef, useState } from 'react';
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import { apiErrorView, type CollaborationContext } from '../api';
import { authorContextRequest, authorRequestKey, type AuthorPreview, type AuthorPreviewReceipt, type AuthorRequestBody } from './authorContextClient';
import './AiContextPreview.css';
import './AuthorRequestPreview.css';

export function AuthorRequestPreviewPanel({ body, context, saved, disabled, onReceipt }: {
  body: AuthorRequestBody | null; context: CollaborationContext; saved: boolean; disabled: boolean;
  onReceipt: (value: AuthorPreviewReceipt | undefined) => void;
}) {
  const key = body ? authorRequestKey(body, context) : '';
  const [result, setResult] = useState<{ key: string; value: AuthorPreview }>();
  const [busy, setBusy] = useState(false), [error, setError] = useState<unknown>();
  const request = useRef<AbortController>(), epoch = useRef(0), currentKey = useRef(key), callback = useRef(onReceipt);
  currentKey.current = key; callback.current = onReceipt;
  useEffect(() => {
    epoch.current += 1; request.current?.abort(); setResult(undefined); setError(undefined); setBusy(false); callback.current(undefined);
    return () => { epoch.current += 1; request.current?.abort(); };
  }, [key, saved]);
  const refresh = async () => {
    if (!body || !saved || disabled || busy) return;
    request.current?.abort(); const controller = new AbortController(); request.current = controller;
    const ticket = ++epoch.current; setBusy(true); setError(undefined); setResult(undefined); callback.current(undefined);
    try {
      const value = await authorContextRequest<AuthorPreview>(body.novel_id, 'preview', body, context, controller.signal);
      if (!controller.signal.aborted && ticket === epoch.current && currentKey.current === key) {
        setResult({ key, value }); callback.current({ previewDigest: value.preview_digest, chapterVersion: value.chapter_version, requestKey: key, requestId: globalThis.crypto.randomUUID() });
      }
    } catch (failure) { if (!controller.signal.aborted && ticket === epoch.current) setError(failure); }
    finally { if (!controller.signal.aborted && ticket === epoch.current) setBusy(false); }
  };
  const value = result?.key === key && saved ? result.value : undefined;
  return <section className="ai-context-preview author-request-preview" aria-label="真实生成请求预检">
    <header className="ai-context-preview__header"><div><h3>真实生成请求预检</h3><p className="novel-help">与本次单草稿生成共用请求构造器。改变正文、选区、模型或要求后，旧预检失效。</p></div><Badge tone={value ? 'success' : 'info'}>{value ? '请求已预检' : '需要预检'}</Badge></header>
    {!body && <EmptyState title="请选择明确的 Provider / 模型" detail="自动路由和多方案生成不使用这个已验证预检路径。" />}
    {!saved && <StatusMessage tone="warning">请先保存当前正文，解决冲突后再预检。未保存的编辑内容不会被悄悄替换成旧正文提交。</StatusMessage>}
    <Button disabled={!body || !saved || disabled || busy} loading={busy} onClick={() => void refresh()}>{error ? '重试真实请求预检' : '检查真实生成请求'}</Button>
    {busy && <StatusMessage>正在构造真实请求，未调用模型…</StatusMessage>}
    {!!error && <StatusMessage tone="error">{apiErrorView(error, '预检未完成，请重试。').message}</StatusMessage>}
    {value && <>
      <dl className="ai-context-preview__meta"><div><dt>目标 Provider / 模型</dt><dd>{value.target === 'cloud' ? '云端' : '本地'} · {value.provider_id} / {value.model_id}</dd></div><div><dt>保存的章节版本</dt><dd>{value.chapter_version}</dd></div><div><dt>实际 Prompt 长度</dt><dd>{value.prompt_characters} 字符；Token 数未知</dd></div><div><dt>正文策略</dt><dd>{value.source_strategy === 'EXACT_SAVED_SELECTION' ? '已保存的精确选区' : '已保存正文的最后 2000 字符'} · {value.source_characters} 字符</dd></div></dl>
      <StatusMessage>生成前和模型发送前会重新检查当前来源、隐私与权限。取消不能收回已经发送的内容；本次预检尚未产生模型费用。</StatusMessage>
      {value.privacy_omissions.length > 0 && <StatusMessage tone="info">隐私策略排除了受限资料；不会展示被排除来源的标识、名称、数量或正文。</StatusMessage>}
      <ul className="ai-context-preview__sources" aria-label="真实请求上下文章节">{value.context_sections.map(row => <li className="ai-context-preview__source" key={row.name}><strong>{row.name}</strong><span>{row.characters} 字符 · Adapter 请求包含</span></li>)}</ul>
      <details><summary>查看准确 Prompt（本机显示，不代表已发送）</summary><textarea aria-label="准确生成 Prompt" readOnly value={value.request.prompt} /></details>
      <details><summary>查看 Adapter 参数与上下文</summary><pre>{JSON.stringify({ context: value.request.context, parameters: value.request.parameters, system_instruction: value.request.system_instruction, creation_records: value.creation_records }, null, 2)}</pre></details>
      <p className="novel-help">这里展示发送给 Adapter 的准确字段，Provider 的协议编码由对应 Adapter 处理。资料移除 / 固定引用控制尚未提供；可先修改选区或已有资料范围，再重新预检。</p>
    </>}
  </section>;
}
