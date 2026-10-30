import { PromptVariablesPanel } from './PromptVariablesPanel';
/**
 * Prompt Editor（R3-U3-C2）。
 *
 * 只有用户明确点击保存才会产生修订。NOVICE 只展开常用字段，PROFESSIONAL 展开参数、
 * 版本身份与校验状态；两种模式共享同一份草稿，切换不丢内容、不保存、不删除任何资产。
 *
 * 正文不做 trim：中文、换行、emoji 与空白都是创作内容。
 */
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import type { StudioInterfaceMode } from '../creative/studioWorkspaceResume';
import type { Draft, DraftContent } from './promptDraft';
import { bodyStateLabel } from './PromptLibraryPanel';
import { PROMPT_BOUNDS, type PromptEntry } from './promptTypes';
import { PromptBodyFinder } from './PromptBodyFinder';
import { useTz } from '../i18n'; // [HERMIA-FE-20261031 VERA-EN]

type Props = {
  draft: Draft;
  /** UI receipt attribution only; never persisted or sent to the clipboard. */
  copyScopeKey?: string;
  detail: PromptEntry | null;
  mode: StudioInterfaceMode;
  locked: boolean;
  busy: boolean;
  canSave: boolean;
  conflictCode: string | null;
  saveError: string | null;
  fieldError: { field: string; message: string } | null;
  onEdit: (patch: Partial<DraftContent>) => void;
  onSave: () => void;
  onRetry: () => void;
  onRebase: () => void;
  onDiscard: () => void;
};

const ids = (value: string): string[] =>
  value.split(/[\s,]+/).map(item => item.trim()).filter(Boolean);

const bindingSummary = (entry: PromptEntry | null) => {
  if (!entry) return [];
  const rows = [
    ['角色', entry.bindings.characters],
    ['场景', entry.bindings.scenes],
    ['镜头', entry.bindings.shots],
    ['参考素材', entry.bindings.assets],
  ] as const;
  return rows.flatMap(([label, group]) => group.map(row => ({ label, ...row })));
};

export function PromptEditorPanel(props: Props) {
  const { draft, detail, mode, locked, busy, canSave, conflictCode, saveError, fieldError,
    onEdit, onSave, onRetry, onRebase, onDiscard } = props;
  const [bodyComposing, setBodyComposing] = useState(false);
  const bodyComposingRef = useRef(false);
  useEffect(() => { bodyComposingRef.current = false; setBodyComposing(false); }, [draft.key, props.copyScopeKey]);
  const professional = mode === 'PROFESSIONAL';
  const z = useTz();
  const status = z(draftStatus(draft));
  const fieldErrorId = useId();
  const byteCountId = useId();
  const textRef = useRef<HTMLTextAreaElement>(null);
  const seedRef = useRef<HTMLInputElement>(null);
  const parametersRef = useRef<HTMLTextAreaElement>(null);
  const copyEpoch = useRef(0);
  const copyBusy = useRef(false);
  const copyAlive = useRef(true);
  type CopySource = { scope: string | undefined; key: string; text: string };
  const [copyFeedback, setCopyFeedback] = useState<(CopySource & { state: 'COPIED' | 'FAILED' }) | null>(null);
  const [copyPending, setCopyPending] = useState<(CopySource & { stale: boolean }) | null>(null);
  const matchesCopySource = (source: CopySource) => source.scope === props.copyScopeKey
    && source.key === draft.key && source.text === draft.content.text;
  const currentCopyFeedback = copyFeedback && matchesCopySource(copyFeedback) ? copyFeedback.state : null;
  useEffect(() => {
    copyAlive.current = true;
    return () => { copyAlive.current = false; copyEpoch.current++; };
  }, []);
  useEffect(() => {
    copyEpoch.current++;
    setCopyFeedback(null);
    setCopyPending(current => current ? { ...current, stale: true } : null);
  }, [props.copyScopeKey, draft.key, draft.content.text]);
  const copyBody = async () => {
    if (copyBusy.current || locked || !draft.content.text) return;
    const epoch = copyEpoch.current;
    const source = { scope: props.copyScopeKey, key: draft.key, text: draft.content.text };
    copyBusy.current = true;
    setCopyPending({ ...source, stale: false });
    setCopyFeedback(null);
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(source.text);
      if (copyAlive.current && copyEpoch.current === epoch) setCopyFeedback({ ...source, state: 'COPIED' });
    } catch {
      if (copyAlive.current && copyEpoch.current === epoch) setCopyFeedback({ ...source, state: 'FAILED' });
    } finally {
      copyBusy.current = false;
      if (copyAlive.current) setCopyPending(null);
    }
  };
  const [parametersCorrectionKey, setParametersCorrectionKey] = useState<string | null>(null);
  const showParameters = professional || fieldError?.field === 'parameters' || parametersCorrectionKey === draft.key;
  const textBytes = useMemo(() => new TextEncoder().encode(draft.content.text).length, [draft.content.text]);
  const excessBytes = textBytes - PROMPT_BOUNDS.textBytes;
  useEffect(() => {
    if (!fieldError || locked) return;
    if (fieldError.field === 'parameters') setParametersCorrectionKey(draft.key);
    const input = fieldError.field === 'text' ? textRef.current
      : fieldError.field === 'seed' ? seedRef.current
      : fieldError.field === 'parameters' ? parametersRef.current : null;
    input?.focus();
  }, [fieldError, locked, draft.key]);

  return (
    <section className="prompt-editor" aria-label={z('Prompt 编辑器')}>
      {/* Persistent, screen-reader visible status — not a transient toast. */}
      <p className="prompt-status" role="status" aria-live="polite">{status}</p>
      {draft.message && <StatusMessage>{z(draft.message)}</StatusMessage>}
      {conflictCode && (
        <StatusMessage tone="warning">
          {z(conflictReason(conflictCode))} {z('你的草稿已保留；请先重新加载服务器版本，再明确重新基准。')}
        </StatusMessage>
      )}
      {saveError && <StatusMessage tone="error">{z(saveError)}</StatusMessage>}
      {fieldError && <StatusMessage tone="error"><span id={fieldErrorId}>{z(fieldError.message)}</span></StatusMessage>}

      {detail && detail.body.state !== 'COMPLETE' && (
        <StatusMessage tone="warning">
          {z(`服务器上这一修订的正文状态是「${bodyStateLabel(detail.body.state)}」，下方显示的内容**不是**完整正文，编辑前请先核对。`)}
        </StatusMessage>
      )}

      <label htmlFor="prompt-text">{z('正文')}</label>
      <textarea onCompositionStart={() => { bodyComposingRef.current = true; setBodyComposing(true); }} onCompositionEnd={() => { bodyComposingRef.current = false; setBodyComposing(false); }} ref={textRef} id="prompt-text" rows={8} value={draft.content.text} disabled={locked}
        aria-describedby={`prompt-text-hint ${byteCountId}${fieldError?.field === 'text' ? ` ${fieldErrorId}` : ''}`}
        aria-invalid={fieldError?.field === 'text' || excessBytes > 0}
        onChange={event => onEdit({ text: event.target.value })} />
      <p id="prompt-text-hint">{z('按 UTF-8 字节计最长 64 KiB。不会自动去除空格、换行或 emoji。')}</p>
      <p id={byteCountId}>{z(`正文已用 ${textBytes} / ${PROMPT_BOUNDS.textBytes} 字节`)} · {z(excessBytes > 0
        ? `超过上限 ${excessBytes} 字节，请缩短后保存；当前内容未被截断。`
        : `剩余 ${-excessBytes} 字节。`)}</p>
      <PromptBodyFinder
        key={JSON.stringify([props.copyScopeKey, draft.key, draft.familyId, draft.baseAssetId, draft.baseRevision])}
        text={draft.content.text} target={textRef} disabled={locked || busy || bodyComposing} />
      <div className="prompt-editor-actions">
        <Button type="button" disabled={locked || !draft.content.text || copyPending !== null}
          onClick={() => void copyBody()}>{z(copyPending !== null ? '正在复制正文…' : '复制当前正文')}</Button>
        {currentCopyFeedback === 'FAILED' && <Button type="button" variant="ghost" disabled={locked}
          onClick={() => { textRef.current?.focus(); textRef.current?.select(); }}>{z('选中正文手动复制')}</Button>}
      </div>
      <p>{z('只复制当前正文，不包含其他参数，也不代表已保存。请粘贴到你选择的位置并核对。')}</p>
      <p>{z('离开页面不会取消已发出的复制请求；重新打开后请核对粘贴内容。')}</p>
      {copyPending !== null && <StatusMessage>{z(copyPending.stale || !matchesCopySource(copyPending)
        ? '先前正文的复制请求仍在处理中；当前正文尚未复制。'
        : '正在请求剪贴板写入，尚未确认复制。')}</StatusMessage>}
      {currentCopyFeedback === 'COPIED' && <StatusMessage>{z('当前正文已复制到剪贴板；请粘贴后核对，未新增服务器修订。')}</StatusMessage>}
      {currentCopyFeedback === 'FAILED' && <StatusMessage tone="warning">
        {z('无法自动复制。可选中正文后按 Ctrl+C 或 Command+C 手动复制；不会自动重试。')}
      </StatusMessage>}

      <PromptVariablesPanel text={draft.content.text} owner={draft.content} scope={JSON.stringify([props.copyScopeKey,draft.key])} disabled={locked || busy || bodyComposing} onApply={text => { if (!bodyComposingRef.current && !locked && !busy) onEdit({text}); }} />

      <label htmlFor="prompt-negative">Negative Prompt</label>
      <textarea id="prompt-negative" rows={3} value={draft.content.negativePrompt} disabled={locked}
        onChange={event => onEdit({ negativePrompt: event.target.value })} />

      <div className="prompt-row">
        <div>
          <label htmlFor="prompt-purpose-select">{z('用途')}</label>
          <select id="prompt-purpose-select" value={draft.content.purpose} disabled={locked}
            onChange={event => onEdit({ purpose: event.target.value as DraftContent['purpose'] })}>
            <option value="IMAGE">IMAGE</option>
            <option value="VIDEO">VIDEO</option>
            <option value="AUDIO">AUDIO</option>
            <option value="TEXT">TEXT</option>
          </select>
        </div>
        <div>
          <label htmlFor="prompt-model">{z('模型偏好')}</label>
          <input id="prompt-model" value={draft.content.modelReference} disabled={locked}
            onChange={event => onEdit({ modelReference: event.target.value })} />
        </div>
        <div>
          <label htmlFor="prompt-seed">Seed</label>
          <input ref={seedRef} id="prompt-seed" inputMode="numeric" value={draft.content.seed} disabled={locked}
            aria-invalid={fieldError?.field === 'seed'}
            aria-describedby={fieldError?.field === 'seed' ? fieldErrorId : undefined}
            onChange={event => onEdit({ seed: event.target.value })} />
        </div>
      </div>

      {showParameters && (
        <>
          {!professional && <p>{z('参数已展开供修正与核对；修改不会自动保存。')}</p>}
          <label htmlFor="prompt-parameters">{z('参数（JSON，不会执行）')}</label>
          <textarea ref={parametersRef} id="prompt-parameters" rows={3} value={draft.content.parameters} disabled={locked}
            aria-invalid={fieldError?.field === 'parameters'}
            aria-describedby={fieldError?.field === 'parameters' ? fieldErrorId : undefined}
            onChange={event => onEdit({ parameters: event.target.value })} />
        </>
      )}

      <fieldset className="prompt-bindings" disabled={locked}>
        <legend>{z('引用绑定（逗号或空格分隔 ID）')}</legend>
        <label htmlFor="prompt-characters">{z('角色 ID')}</label>
        <input id="prompt-characters" value={draft.content.characterIds.join(', ')}
          onChange={event => onEdit({ characterIds: ids(event.target.value) })} />
        <label htmlFor="prompt-scenes">{z('场景 ID')}</label>
        <input id="prompt-scenes" value={draft.content.sceneIds.join(', ')}
          onChange={event => onEdit({ sceneIds: ids(event.target.value) })} />
        <label htmlFor="prompt-shots">{z('镜头 ID')}</label>
        <input id="prompt-shots" value={draft.content.shotIds.join(', ')}
          onChange={event => onEdit({ shotIds: ids(event.target.value) })} />
        <label htmlFor="prompt-assets">{z('参考素材 ID')}</label>
        <input id="prompt-assets" value={draft.content.referenceAssetIds.join(', ')}
          onChange={event => onEdit({ referenceAssetIds: ids(event.target.value) })} />
      </fieldset>

      {professional && detail && bindingSummary(detail).length > 0 && (
        <div className="prompt-binding-truth">
          <p>{z('服务器解析结果（绑定核实的唯一来源）：')}</p>
          <ul>
            {bindingSummary(detail).map(row => (
              <li key={`${row.label}:${row.id}`}>
                {z(row.label)} {row.id} ·{' '}
                <Badge tone={row.resolution === 'KNOWN' ? 'success' : 'warning'}>
                  {z(row.resolution === 'KNOWN' ? '索引中存在' : '未找到')}
                </Badge>{' '}
                {z(`来源 ${row.verification}`)}
              </li>
            ))}
          </ul>
          <p>
            <strong>{z('INDEX_SUPPLIED 只表示索引里有这个目标')}</strong>{z('，不代表已审核、可生成，也不代表保存时校验通过 —— 写入时引用校验仍为 NOT_RUN。')}
          </p>
        </div>
      )}

      <label htmlFor="prompt-note">{z('修改备注')}</label>
      <input id="prompt-note" value={draft.content.changeNote} disabled={locked}
        onChange={event => onEdit({ changeNote: event.target.value })} />
      <label htmlFor="prompt-reason">{z('修改原因')}</label>
      <input id="prompt-reason" value={draft.content.changeReason} disabled={locked}
        onChange={event => onEdit({ changeReason: event.target.value })} />

      <div className="prompt-editor-actions">
        <Button onClick={onSave} disabled={!canSave || locked || busy}>
          {z(draft.familyId ? '保存新版本' : '保存为新 Prompt')}
        </Button>
        {draft.state === 'UNKNOWN' && (
          <Button onClick={onRetry}>{z('用同一请求重试')}</Button>
        )}
        {conflictCode && <Button onClick={onRebase}>{z('重新基准到服务器最新修订')}</Button>}
        <Button onClick={onDiscard} disabled={locked}>{z('放弃本地修改')}</Button>
      </div>
      {professional && (
        <dl className="prompt-identity">
          <dt>{z('家族')}</dt><dd>{draft.familyId ?? z('（新建）')}</dd>
          <dt>{z('基准修订')}</dt><dd>{draft.baseRevision ?? z('（新建）')}</dd>
          <dt>{z('基准资产')}</dt><dd>{draft.baseAssetId ?? z('（新建）')}</dd>
          <dt>{z('请求标识')}</dt><dd>{draft.requestId ?? z('（未提交）')}</dd>
        </dl>
      )}
    </section>
  );
}

export function draftStatus(draft: Draft): string {
  switch (draft.state) {
    case 'DIRTY': return draft.conflictCode ? '有未保存修改（冲突未解决）' : '有未保存修改';
    case 'SUBMITTING': return '正在提交…（输入已锁定）';
    case 'UNKNOWN': return '提交结果未知：不会自动重发，请核对后决定是否重试';
    case 'CONFLICT': return '保存冲突：草稿已保留，需要重新加载并明确重新基准';
    case 'SAVED': return '已保存（服务器已确认）';
    default: return '尚无未保存修改';
  }
}

export function conflictReason(code: string): string {
  switch (code) {
    case 'PROMPT_REVISION_STALE': return '这个 Prompt 已经有人保存了更新的修订。';
    case 'PROMPT_REQUEST_ID_REUSED': return '这次提交的请求标识已用于另一份内容。';
    case 'PROMPT_REVISION_CONFLICT': return '另一个保存同时发生，你的内容被保留为冲突修订。';
    case 'PROMPT_ASSET_VERSION_CONFLICT': return '保存过程中这个 Prompt 被改动了。';
    default: return '保存被拒绝。';
  }
}
