import { useLayoutEffect, useRef, useState } from 'react';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { Details, Field, useAction } from './shared';
import type { SyncApi, SyncCatalog, SyncChannel } from './offlineSyncClient';
import { MAX_OFFLINE_SYNC_BYTES, offlineSyncInputError, parseOfflineSyncMessage, readOfflineSyncFile } from './offlineSyncFile';

type Props = { api: SyncApi; channel: SyncChannel; catalog: SyncCatalog; blocked: boolean; reload: () => void };
type InputStatus = { tone: 'info' | 'success' | 'error'; message: string };
type Candidate = { value: unknown; text: string; target: string };

export function OfflineSyncReceive({ api, channel, catalog, blocked, reload }: Props) {
  const [text, setText] = useState(''), [target, setTarget] = useState('');
  const [preview, setPreview] = useState<Candidate>(), [receipt, setReceipt] = useState<unknown>();
  const [reading, setReading] = useState(false), [inputStatus, setInputStatus] = useState<InputStatus>();
  const [, setGeneration] = useState(0);
  const action = useAction(), alive = useRef(true), epoch = useRef(0), pending = useRef<AbortController>();
  const draft = useRef({ text: '', target: '', preview: undefined as Candidate | undefined }), receiving = useRef(false);
  const blockedRef = useRef(blocked); blockedRef.current = blocked || channel.status !== 'ACTIVE';
  const scope = JSON.stringify([channel.id, channel.version, channel.status, channel.stream_id, channel.endpoint_id, channel.peer_id, channel.chapter_ids, channel.withdrawn_chapter_ids, channel.allow_new_chapters]);
  const allowed = (id: string) => id === '__NEW__' ? channel.allow_new_chapters : channel.chapter_ids.includes(id) && !channel.withdrawn_chapter_ids?.includes(id);
  const current = (ticket: number) => alive.current && !blockedRef.current && epoch.current === ticket;
  const cancelRead = () => { epoch.current++; pending.current?.abort(); pending.current = undefined; };
  const invalidate = () => {
    cancelRead(); setGeneration(epoch.current); draft.current.preview = undefined;
    setReading(false); setPreview(undefined); setReceipt(undefined); setInputStatus(undefined);
  };
  useLayoutEffect(() => {
    alive.current = true;
    return () => { alive.current = false; cancelRead(); };
  }, []);
  useLayoutEffect(() => {
    cancelRead(); setGeneration(epoch.current); draft.current.preview = undefined;
    setReading(false); setPreview(undefined); setInputStatus(undefined);
    if (!allowed(target)) { draft.current.target = ''; setTarget(''); setReceipt(undefined); }
  }, [api, scope, blocked]);

  async function readFile(file: File) {
    const ticket = epoch.current, controller = new AbortController();
    pending.current = controller; setReading(true);
    try {
      const value = await readOfflineSyncFile(file, controller.signal);
      if (current(ticket)) {
        draft.current.text = value; setText(value);
        setInputStatus({ tone: 'success', message: '本地文件已载入文本框；请核对并预览，尚未接收或写入正文。' });
      }
    } catch (error) {
      if (current(ticket)) setInputStatus(error instanceof DOMException && error.name === 'AbortError'
        ? { tone: 'info', message: '文件读取已取消，原输入已保留。' }
        : { tone: 'error', message: offlineSyncInputError(error) });
    } finally {
      if (current(ticket)) { pending.current = undefined; setReading(false); }
    }
  }
  const disabled = blocked || channel.status !== 'ACTIVE' || action.busy;
  // Event callbacks carry the render generation, not the generation at invocation.
  // Live draft/candidate refs also fence same-batch edits before React paints.
  const renderedGeneration = epoch.current;
  return <Panel title="手动接收候选，不自动覆盖">
    <p>选择本地交换文件，或直接粘贴 JSON。仅支持不超过 512 KiB 的 UTF-8 JSON；读取只填入下方可编辑文本，不会自动接收或应用。</p>
    <p>先核对源标签和正文，再选择已批准范围内的目标；批次、来源、版本和重放游标仍由原同步服务重新检查。</p>
    <Field label="选择本地同步 JSON 文件"><input type="file" accept=".json,application/json" disabled={disabled} onChange={event => {
      const file = event.currentTarget.files?.[0]; event.currentTarget.value = '';
      if (disabled || !current(renderedGeneration) || receiving.current) return;
      invalidate();
      if (file) void readFile(file);
    }} /></Field>
    {reading && <><StatusMessage>正在本地读取文件，原输入暂时保留…</StatusMessage><Button onClick={() => { if (!current(renderedGeneration) || !pending.current) return; invalidate(); setInputStatus({ tone: 'info', message: '文件读取已取消，原输入已保留。' }); }}>取消文件读取</Button></>}
    <Field label="收到的同步消息 JSON"><textarea value={text} maxLength={MAX_OFFLINE_SYNC_BYTES} disabled={disabled} onChange={event => {
      if (!current(renderedGeneration) || receiving.current) return;
      invalidate(); draft.current.text = event.target.value; setText(event.target.value);
    }} /></Field>
    <Field label="收到章节的本机目标"><select value={target} disabled={disabled} onChange={event => {
      if (!current(renderedGeneration) || receiving.current) return;
      invalidate(); draft.current.target = event.target.value; setTarget(event.target.value);
    }}>
      <option value="">选择目标章节</option>
      {channel.allow_new_chapters && <option value="__NEW__">审阅后新增独立章节</option>}
      {channel.chapter_ids.filter(id => !channel.withdrawn_chapter_ids?.includes(id)).map(id => <option key={id} value={id}>{catalog.chapters.find(chapter => chapter.id === id)?.title || id}</option>)}
    </select></Field>
    <Button disabled={disabled || reading || !text || !allowed(target)} onClick={() => {
      if (!current(renderedGeneration) || receiving.current || pending.current || !text || !allowed(target) || draft.current.text !== text || draft.current.target !== target) return;
      draft.current.preview = undefined; setPreview(undefined); setReceipt(undefined);
      try {
        const candidate = { value: parseOfflineSyncMessage(text), text, target };
        draft.current.preview = candidate; setPreview(candidate);
        setInputStatus({ tone: 'success', message: '已预览输入，尚未接收或写入正文。' });
      }
      catch (error) { setInputStatus({ tone: 'error', message: offlineSyncInputError(error) }); }
    }}>预览待接收消息</Button>
    {preview && !blocked && allowed(target) && <><Details value={preview.value} label="待接收信封预览" /><Button disabled={disabled || reading} onClick={() => {
      if (!current(renderedGeneration) || receiving.current || pending.current || draft.current.preview !== preview || draft.current.text !== preview.text || draft.current.target !== preview.target || !allowed(preview.target)) return;
      // Consume this exact candidate before dispatch. Failure keeps its editable
      // text for explicit re-preview/retry; a retained callback cannot replay it.
      receiving.current = true; invalidate();
      const ticket = epoch.current;
      void action.run(async () => {
        try {
          const result = await api.receive(channel, preview.value, target === '__NEW__' ? '' : target, target === '__NEW__');
          if (current(ticket)) setReceipt(result.receipt);
        } finally { receiving.current = false; if (alive.current) reload(); }
      }, '候选已保存至本机收件箱，正文尚未修改。');
    }}>接收到待审核收件箱</Button></>}
    {!!receipt && <Field label="可复制给发送端的接收回执"><textarea readOnly value={JSON.stringify(receipt, null, 2)} /></Field>}
    {inputStatus && <StatusMessage tone={inputStatus.tone}>{inputStatus.message}</StatusMessage>}{action.feedback}
  </Panel>;
}
