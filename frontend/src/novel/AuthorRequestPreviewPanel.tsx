import { useEffect, useRef, useState } from 'react';
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import { apiErrorView, type CollaborationContext } from '../api';
import { authorContextRequest, authorContextVariants, authorVariantsKey, type AuthorVariantsReceipt, type AuthorVariantsPreview, authorRequestKey, type AuthorPreview, type AuthorPreviewReceipt, type AuthorRequestBody } from './authorContextClient';
import './AiContextPreview.css';
import './AuthorRequestPreview.css';

export function AuthorRequestPreviewPanel({ body, context, saved, disabled, onReceipt, variantCount = 1, onVariantsReceipt }: {
  body: AuthorRequestBody | null; context: CollaborationContext; saved: boolean; disabled: boolean;
  variantCount?: number; onVariantsReceipt?: (value: AuthorVariantsReceipt | undefined) => void;
  onReceipt: (value: AuthorPreviewReceipt | undefined) => void;
}) {
  const key = body ? authorVariantsKey(body, variantCount, context) : '';
  const [result, setResult] = useState<{ key: string; values: AuthorPreview[] }>();
  const [busy, setBusy] = useState(false), [error, setError] = useState<unknown>();
  const request = useRef<AbortController>(), epoch = useRef(0), currentKey = useRef(key), callback = useRef(onReceipt), batchCallback = useRef(onVariantsReceipt);
  currentKey.current = key; callback.current = onReceipt; batchCallback.current = onVariantsReceipt;
  useEffect(() => {
    epoch.current += 1; request.current?.abort(); setResult(undefined); setError(undefined); setBusy(false); callback.current(undefined); batchCallback.current?.(undefined);
    return () => { epoch.current += 1; request.current?.abort(); };
  }, [key, saved]);
  const refresh = async () => {
    if (!body || !saved || disabled || busy) return;
    request.current?.abort(); const controller = new AbortController(); request.current = controller;
    const ticket = ++epoch.current; setBusy(true); setError(undefined); setResult(undefined); callback.current(undefined); batchCallback.current?.(undefined);
    try {
      if (variantCount > 1) {
        const batch = { author: structuredClone(body), count: variantCount, group_id: globalThis.crypto.randomUUID() };
        const value = await authorContextVariants<AuthorVariantsPreview>(body.novel_id, 'preview-variants', batch, context, controller.signal);
        if (!controller.signal.aborted && ticket === epoch.current && currentKey.current === key) {
          if (value.count !== variantCount || value.variants.length !== variantCount || value.group_id !== batch.group_id
              || new Set(value.variants.map(row => row.variant?.job_id)).size !== variantCount
              || value.variants.some((row, index) => row.variant?.variant_index !== index + 1 || row.variant.group_id !== batch.group_id
                || row.variant.count !== variantCount || !row.variant.job_id || !/^[0-9a-f]{64}$/.test(row.preview_digest)
                || row.chapter_version !== body.chapter_version || row.chapter_id !== body.chapter_id
                || row.provider_id !== body.provider_id || row.model_id !== body.model_id))
            throw new Error('方案预检映射不完整，请重新检查。');
          setResult({ key, values: value.variants }); batchCallback.current?.({ requestBody: structuredClone(body), requestKey: key,
            chapterVersion: body.chapter_version, jobIds: value.variants.map(row => row.variant.job_id),
            batch: { ...batch, receipts: value.variants.map(row => ({ variant_index: row.variant.variant_index, preview_digest: row.preview_digest })) } });
        }
      } else {
        const value = await authorContextRequest<AuthorPreview>(body.novel_id, 'preview', body, context, controller.signal);
        if (!controller.signal.aborted && ticket === epoch.current && currentKey.current === key) {
          setResult({ key, values: [value] }); callback.current({ requestBody: structuredClone(body), previewDigest: value.preview_digest,
            chapterVersion: value.chapter_version, requestKey: authorRequestKey(body, context), requestId: globalThis.crypto.randomUUID() });
        }
      }
    } catch (failure) { if (!controller.signal.aborted && ticket === epoch.current) setError(failure); }
    finally { if (!controller.signal.aborted && ticket === epoch.current) setBusy(false); }
  };
  const values = result?.key === key && saved ? result.values : undefined;
  return <section className="ai-context-preview author-request-preview" aria-label="真实生成请求预检">
    <header className="ai-context-preview__header"><div><h3>真实生成请求预检</h3><p className="novel-help">与本次每份草稿共用请求构造器。改变正文、选区、模型或要求后，旧预检失效。</p></div><Badge tone={values ? 'success' : 'info'}>{values ? '请求已预检' : '需要预检'}</Badge></header>
    {!body && <EmptyState title="请选择明确的 Provider / 模型" detail="每次请求必须明确指定已启用的模型，不能自动换路线。" />}
    {!saved && <StatusMessage tone="warning">请先保存当前正文，解决冲突后再预检。未保存的编辑内容不会被悄悄替换成旧正文提交。</StatusMessage>}
    <Button disabled={!body || !saved || disabled || busy} loading={busy} onClick={() => void refresh()}>{error ? '重试真实请求预检' : '检查真实生成请求'}</Button>
    {busy && <StatusMessage>正在构造真实请求，未调用模型…</StatusMessage>}
    {!!error && <StatusMessage tone="error">{apiErrorView(error, '预检未完成，请重试。').message}</StatusMessage>}
    {variantCount > 1 && <StatusMessage>本次明确请求 {variantCount} 个本地候选，每份准确 Prompt 单独预检。不自动追加或重试；本地费用仍标未知，用量按原任务记录，不当作免费。云端或适用调度预算的批次尚需组预算预占支持。</StatusMessage>}
    {values?.map((value, index) => <section key={index} aria-label={variantCount > 1 ? `方案 ${index + 1} 请求预览` : '单份请求预览'}>
      {variantCount > 1 && <h4>方案 {index + 1} / {variantCount}</h4>}
      <dl className="ai-context-preview__meta"><div><dt>目标 Provider / 模型</dt><dd>{value.target === 'cloud' ? '云端' : '本地'} · {value.provider_id} / {value.model_id}</dd></div><div><dt>保存的章节版本</dt><dd>{value.chapter_version}</dd></div><div><dt>实际 Prompt 长度</dt><dd>{value.prompt_characters} 字符；Token 数未知</dd></div><div><dt>正文策略</dt><dd>{value.source_strategy === 'CHARACTER_KNOWLEDGE_ONLY' ? '仅人物可知信息，不含正文' : value.source_strategy === 'NO_MANUSCRIPT' ? '不包含正文，不回退到章节末尾' : value.source_strategy === 'EXACT_SAVED_SELECTION' ? '已保存的精确选区' : value.source_strategy === 'LAST_2000_SAVED_CHARACTERS' ? '已保存正文的最后 2000 字符' : '服务器指定的受限范围'} · {value.source_characters} 字符</dd></div></dl>
      <StatusMessage>生成前和模型发送前会重新检查当前来源、隐私与权限。取消不能收回已经发送的内容；本次预检尚未产生模型费用。</StatusMessage>
      {value.privacy_omissions.length > 0 && <StatusMessage tone="info">隐私策略排除了受限资料；不会展示被排除来源的标识、名称、数量或正文。</StatusMessage>}
      {value.scope_effects?.references_omitted_for_source_isolation && <StatusMessage>来源精简已生效：自动派生上下文与固定参考均已移除。</StatusMessage>}
      <ul className="ai-context-preview__sources" aria-label="真实请求上下文章节">{value.context_sections.map(row => <li className="ai-context-preview__source" key={row.name}><strong>{row.name}</strong><span>{row.characters} 字符 · Adapter 请求包含</span></li>)}</ul>
      <details><summary>查看准确 Prompt（本机显示，不代表已发送）</summary><textarea aria-label={variantCount > 1 ? `方案 ${index + 1} 准确生成 Prompt` : "准确生成 Prompt"} readOnly value={value.request.prompt} /></details>
      <details><summary>查看请求摘要与任务映射</summary><dl><dt>准确请求摘要</dt><dd>{value.preview_digest}</dd>{value.variant && <><dt>原任务 ID</dt><dd>{value.variant.job_id}</dd><dt>原任务组 ID</dt><dd>{value.variant.group_id}</dd></>}</dl></details>
      <details><summary>查看 Adapter 参数与上下文</summary><pre>{JSON.stringify({ context: value.request.context, parameters: value.request.parameters, system_instruction: value.request.system_instruction, creation_records: value.creation_records, variant_policy: value.variant_policy }, null, 2)}</pre></details>
      <p className="novel-help">这里展示发送给 Adapter 的准确字段，Provider 的协议编码由对应 Adapter 处理。资料范围使用整包隔离；固定引用版本与移除结果可在准确字段中核对。</p>
    </section>)}
  </section>;
}
