import { useStudioProductionLeaveRisk, type StudioProductionLeaveGuard } from './studioProductionLeaveRisk';
import { useLayoutEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView, type Asset } from '../api';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import type { StudioClient } from './studioClient';
import { BinaryMaskDraft } from './studioBinaryMask';
import { maskDimension, maskSha256, type StudioMaskInput, type StudioMaskResult } from './studioManualMaskContract';

export type StudioManualMaskProps = {
  leaveGuard?: StudioProductionLeaveGuard;
  asset: Asset; client: Pick<StudioClient, 'asset' | 'download' | 'createMask'>;
  canMutate: boolean; busy: boolean; isBusy: () => boolean; isCurrent: () => boolean; isSourceCurrent?: () => boolean; watchHost?: boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>; mutate: <T>(work: () => Promise<T>) => Promise<T>;
  onDirtyChange: (dirty: boolean) => void; onUnavailable: () => void; onSaved: (result: StudioMaskResult) => void;
};
const tuple = (asset: Asset) => JSON.stringify([asset.novel_id, asset.branch_id ?? null, asset.id, asset.version, asset.sha256, asset.media_type, asset.kind, asset.deleted_at ?? null]);
const supported = (asset: Asset) => asset.kind === 'image' && asset.media_type === 'image/png' && !asset.deleted_at
  && Number.isSafeInteger(asset.version) && asset.version! > 0 && /^[a-f0-9]{64}$/.test(asset.sha256);
const cancelled = () => new DOMException('来源或会话已改变。', 'AbortError');
const hostIdentity = () => { const host = useLocalHostSession.getState(); return JSON.stringify([host.token, host.actorId, host.epoch]); };
/** Header validation bounds native decoding; authoritative PNG validation remains server-side. */
export function maskPngDimensions(bytes: Uint8Array): { width: number; height: number } {
  const signature = [137, 80, 78, 71, 13, 10, 26, 10];
  if (bytes.length < 33 || !signature.every((value, index) => bytes[index] === value)) throw new Error('仅支持 PNG 原始文件。');
  const data = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const width = data.getUint32(16), height = data.getUint32(20);
  if (data.getUint32(8) !== 13 || String.fromCharCode(...bytes.slice(12, 16)) !== 'IHDR'
    || bytes[24] !== 8 || ![0, 2, 4, 6].includes(bytes[25]) || bytes[26] !== 0 || bytes[27] !== 0 || bytes[28] !== 0
    || !maskDimension(width) || !maskDimension(height)) throw new Error('需要非隔行 8 位 PNG；宽高须为 64–1024 且均为 8 的倍数。不自动缩放。');
  let offset = 33, image = false, end = false, chunks = 1;
  while (offset + 12 <= bytes.length) {
    if (++chunks > 1024) throw new Error('PNG 数据块超过支持上限，未打开编辑器。');
    const length = data.getUint32(offset), type = String.fromCharCode(...bytes.slice(offset + 4, offset + 8));
    if (length > bytes.length - offset - 12 || !['IDAT', 'IEND'].includes(type)) throw new Error('此 PNG 含不受支持的附加块；不自动转换来源。');
    offset += length + 12;
    if (type === 'IDAT') image = true;
    else { end = image && length === 0 && offset === bytes.length; break; }
  }
  if (!end) throw new Error('PNG 数据不完整，未打开编辑器。');
  return { width, height };
}

type Editor = { mask: BinaryMaskDraft; url: string; source: Asset };
type Attempt = { body: StudioMaskInput; revision: number; retryable: boolean; uncertain: boolean };
/** Ephemeral pixel draft, pinned to one source and the original owner lifetime. */
export function useStudioManualMask(props: StudioManualMaskProps) {
  const live = useRef(props); live.current = props;
  const [origin] = useState(() => ({ client: props.client, source: tuple(props.asset), host: hostIdentity(), watchHost: props.watchHost === true }));
  const alive = useRef(true), revoked = useRef(false), ticket = useRef(0), operation = useRef<AbortController>();
  const editorRef = useRef<Editor>(), attemptRef = useRef<Attempt>(), consentRef = useRef<number>();
  const [editor, setEditor] = useState<Editor>(), [pending, setPending] = useState<'LOAD' | 'SAVE'>();
  const [attempt, setAttempt] = useState<Attempt>(), [consent, setConsent] = useState(false), [result, setResult] = useState<StudioMaskResult>();
  const [message, setMessage] = useState(''), [revision, setRevision] = useState(0), [unavailable, setUnavailable] = useState(false);
  const authorityCurrent = () => live.current.isCurrent() && (!origin.watchHost || hostIdentity() === origin.host);
  const current = () => alive.current && !revoked.current && live.current.client === origin.client
    && tuple(live.current.asset) === origin.source && authorityCurrent() && (live.current.isSourceCurrent?.() ?? true);
  const leaveGuard = useStudioProductionLeaveRisk(props.leaveGuard, () => ({ unknown: !!attemptRef.current && (!!operation.current || attemptRef.current.uncertain),
    requests: attemptRef.current && (operation.current || attemptRef.current.uncertain) ? [{ requestId: attemptRef.current.body.idempotency_key, owner: 'image', operationId: 'manual-binary-mask/1' }] : [] }));
  function clearEditor() {
    editorRef.current?.mask.dispose(); if (editorRef.current?.url) URL.revokeObjectURL(editorRef.current.url);
    editorRef.current = undefined; consentRef.current = undefined; setEditor(undefined); setConsent(false);
  }
  function revoke(notify = true) {
    if (revoked.current) return; leaveGuard?.capture(); revoked.current = true; ticket.current++; operation.current?.abort(); clearEditor();
    attemptRef.current = undefined; setAttempt(undefined); setResult(undefined); setMessage(''); setPending(undefined); setUnavailable(true);
    live.current.onDirtyChange(false); if (notify) live.current.onUnavailable();
  }
  function verify() { if (!current() || !live.current.canMutate) { if (alive.current) revoke(!authorityCurrent()); throw cancelled(); } }
  useLayoutEffect(() => {
    alive.current = true;
    const changed = () => { if (!current()) revoke(!authorityCurrent()); };
    const owner = useStudio.subscribe(changed), host = useLocalHostSession.subscribe(changed);
    changed();
    return () => {
      alive.current = false; ticket.current++; operation.current?.abort(); editorRef.current?.mask.dispose();
      if (editorRef.current?.url) URL.revokeObjectURL(editorRef.current.url);
      owner(); host(); live.current.onDirtyChange(false);
    };
  }, []);
  useLayoutEffect(() => {
    if (!revoked.current && (!current() || !props.canMutate && (editorRef.current || operation.current))) revoke(!authorityCurrent());
  });
  const admissible = () => current() && live.current.canMutate && !operation.current && !live.current.isBusy();
  const changed = () => { consentRef.current = undefined; setConsent(false); setRevision(value => value + 1); live.current.onDirtyChange(!!editorRef.current || !!attemptRef.current); };
  async function load() {
    if (!admissible() || !supported(live.current.asset) || attemptRef.current || editorRef.current) return;
    const source = { ...live.current.asset }, id = ++ticket.current, abort = new AbortController(); operation.current = abort;
    setPending('LOAD'); setMessage(''); setResult(undefined);
    let url: string | undefined;
    try {
      await live.current.mutate(async () => {
        verify(); const first = await live.current.read(() => origin.client.asset(source.id, abort.signal)); verify();
        if (tuple(first) !== origin.source || !supported(first)) throw new Error('来源版本已变化，请重新读取资产。');
        const blob = await live.current.read(() => origin.client.download(source.id, abort.signal)); verify();
        if (blob.size > 8 * 1024 * 1024 || blob.size < 33) throw new Error('PNG 文件须不超过 8 MiB，且包含完整图片数据。');
        const bytes = new Uint8Array(await blob.arrayBuffer()); verify();
        if (await maskSha256(bytes) !== source.sha256) throw new Error('来源文件摘要不匹配，请重新读取资产。'); verify();
        const { width, height } = maskPngDimensions(bytes);
        if (typeof createImageBitmap !== 'function') throw new Error('当前浏览器无法安全解码此 PNG，未打开编辑器。');
        const bitmap = await createImageBitmap(blob);
        try { verify(); if (bitmap.width !== width || bitmap.height !== height) throw new Error('解码尺寸与 PNG 来源不一致。'); }
        finally { bitmap.close(); }
        const second = await live.current.read(() => origin.client.asset(source.id, abort.signal)); verify();
        if (tuple(second) !== origin.source || abort.signal.aborted || id !== ticket.current) throw new Error('来源版本已变化，请重新读取资产。');
        url = URL.createObjectURL(blob); const value = { mask: new BinaryMaskDraft(width, height), url, source }; url = undefined;
        editorRef.current = value; setEditor(value); setRevision(value.mask.revision); live.current.onDirtyChange(true);
      });
    } catch (error) {
      if (error instanceof ApiError && [401, 403].includes(error.status) && current()) revoke();
      else if (current() && id === ticket.current) setMessage(apiErrorView(error, '来源未能验证，编辑器没有打开。').message);
    } finally { if (url) URL.revokeObjectURL(url); if (operation.current === abort) operation.current = undefined; if (current() && id === ticket.current) setPending(undefined); }
  }
  function agree(value: boolean) {
    if (!admissible() || !editorRef.current || attemptRef.current || editorRef.current.mask.activeStroke) return;
    consentRef.current = value ? editorRef.current.mask.revision : undefined; setConsent(value);
  }
  async function save(retry = false) {
    if (!admissible()) return;
    const edit = editorRef.current;
    if (!edit || edit.mask.activeStroke) return;
    let request = attemptRef.current;
    if (retry ? !request?.retryable : !!request || consentRef.current !== edit.mask.revision) return;
    if (!retry) {
      try {
        const pixels = edit.mask.serialize();
        request = { body: Object.freeze({ contract: 'manual-binary-mask/1', source_version: edit.source.version!, source_sha256: edit.source.sha256,
          width: edit.mask.width, height: edit.mask.height, bitplane_base64: pixels.bitplane_base64, idempotency_key: crypto.randomUUID() }), revision: edit.mask.revision, retryable: true, uncertain: false };
      } catch (error) { setMessage(apiErrorView(error, '遮罩必须同时包含黑色和白色像素。').message); return; }
    }
    const frozen = request!; attemptRef.current = frozen; setAttempt(frozen); consentRef.current = undefined; setConsent(false);
    const id = ++ticket.current, abort = new AbortController(); operation.current = abort; setPending('SAVE'); setMessage('');
    let sent = false;
    try {
      const saved = await live.current.mutate(async () => {
        verify(); const source = await live.current.read(() => origin.client.asset(edit.source.id, abort.signal)); verify();
        if (tuple(source) !== origin.source) throw new ApiError({ status: 409, code: 'EXPERIMENTAL_SOURCE_STALE', message: '来源版本已改变；请在原资产列表核对已有结果。' });
        if (edit.mask.revision !== frozen.revision || edit.mask.activeStroke || abort.signal.aborted || id !== ticket.current) throw cancelled();
        sent = true; return origin.client.createMask(edit.source.id, frozen.body, abort.signal);
      });
      verify(); if (id !== ticket.current || abort.signal.aborted) return;
      clearEditor(); attemptRef.current = undefined; setAttempt(undefined); setResult(saved); live.current.onDirtyChange(false);
      setMessage('二值遮罩已保存到原资产库。未创建任务或执行抠图。');
      try { live.current.onSaved(saved); } catch { setMessage('遮罩已保存；列表刷新未完成，请在原资产库重新读取。'); }
    } catch (error) {
      if (error instanceof ApiError && [401, 403].includes(error.status) && current()) revoke();
      else if (current() && id === ticket.current) {
        const stale = error instanceof ApiError && [404, 409].includes(error.status);
        const failed = { ...frozen, retryable: !stale, uncertain: frozen.uncertain || sent };
        attemptRef.current = failed; setAttempt(failed); live.current.onDirtyChange(true);
        setMessage(stale ? '来源已变化或不可用；不能重试此保存。结果可能已在原资产库，请刷新列表核对。'
          : '保存结果尚待核对。可明确重试完全相同的像素与请求标识，或先在原资产库核对；不会自动重发。');
      }
    } finally { if (operation.current === abort) operation.current = undefined; if (current() && id === ticket.current) setPending(undefined); }
  }
  function discard() {
    if (!current() || operation.current) return;
    clearEditor(); live.current.onDirtyChange(false);
    // A lost response never becomes a fresh-key retry within this editor lifetime.
    if (attemptRef.current) setMessage('本地像素已丢弃，但保存结果仍待核对。请刷新原资产列表，勿将重新创建当作重试。'); else setMessage('本地遮罩已丢弃，未保存文件。');
  }
  let mixed = false;
  if (editor && !editor.mask.activeStroke) { try { editor.mask.serialize(); mixed = true; } catch { /* Explicit empty mask feedback in panel. */ } }
  return { editor, pending, attempt, consent, result, message, revision, unavailable,
    eligible: supported(props.asset), editable: current() && props.canMutate && !props.busy && !operation.current && !attempt,
    canLoad: admissible() && supported(props.asset) && !editor && !attempt,
    canSave: admissible() && !!editor && mixed && !editor.mask.activeStroke && !attempt && consent && consentRef.current === editor.mask.revision,
    mixed, load, save, discard, agree, changed,
    isEditable: () => admissible() && !attemptRef.current,
  };
}
