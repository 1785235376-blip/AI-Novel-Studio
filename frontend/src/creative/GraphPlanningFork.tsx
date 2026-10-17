import { useLayoutEffect, useRef, useState } from 'react';
import { apiErrorView } from '../api';
import { Button, StatusMessage } from '../ui/primitives';
import type { StudioGraphClient } from './studioGraphClient';
import { checkedPlanningDocument, type PlanningDocument, type PlanningSnapshot } from './studioProductionGraphContract';

type Props = {
  client: Pick<StudioGraphClient, 'planningDocuments'>;
  pin: PlanningSnapshot;
  mode: 'DIRECTOR' | 'STORYBOARD';
  scope: object;
  disabled: boolean;
  isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>;
  prepare: (document: PlanningDocument, scope: object) => boolean;
};

export function GraphPlanningFork(props: Props) {
  const live = useRef(props); live.current = props;
  const alive = useRef(true), locked = useRef(false), sequence = useRef(0), consumed = useRef<object>();
  const request = useRef<AbortController>();
  const [loading, setLoading] = useState(false), [error, setError] = useState('');
  const [preview, setPreview] = useState<{ document: PlanningDocument; scope: object; ticket: object }>();
  const [consent, setConsent] = useState<object>();
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; sequence.current++; }; }, []);
  useLayoutEffect(() => {
    sequence.current++; request.current?.abort(); locked.current = false;
    setLoading(false); setPreview(undefined); setConsent(undefined); setError('');
    return () => { sequence.current++; request.current?.abort(); };
  }, [props.scope]);
  const current = (scope: object) => alive.current && scope === live.current.scope && live.current.isCurrent();
  const visible = preview?.scope === props.scope && current(props.scope) ? preview : undefined;
  async function inspect() {
    if (locked.current || props.disabled || !current(props.scope) || !props.client.planningDocuments) return;
    locked.current = true; setLoading(true); setError(''); setPreview(undefined); setConsent(undefined);
    const sequenceId = ++sequence.current, scope = props.scope;
    const abort = new AbortController(); request.current = abort;
    try {
      const result = await props.read(() => {
        if (!current(scope) || sequence.current !== sequenceId || abort.signal.aborted) throw new DOMException('Read retired', 'AbortError');
        return props.client.planningDocuments!(abort.signal);
      });
      if (!current(scope) || sequence.current !== sequenceId) return;
      const rows = result.documents.filter(row => row.id === props.pin.id);
      if (rows.length !== 1) throw new Error('当前来源不可唯一读取；没有准备新图。');
      const document = checkedPlanningDocument(rows[0]);
      if (document.mode !== props.mode || document.version <= props.pin.version || document.digest === props.pin.digest) {
        throw new Error('当前目录没有同一来源的更新版本；原图与草稿保持不变。');
      }
      setPreview({ document, scope, ticket: {} });
    } catch (reason) {
      if (current(scope) && sequence.current === sequenceId) setError(apiErrorView(reason, '未能核对来源，原图与草稿保持不变。').message);
    } finally {
      if (sequence.current === sequenceId) {
        locked.current = false;
        if (alive.current) setLoading(false);
      }
    }
  }
  return <section aria-label="以更新来源准备独立图">
    <p>原图的版本引用保持不变。可明确读取该来源的新版本，核对后只替换所选节点，在独立新图草稿中继续。</p>
    <Button disabled={props.disabled || loading || !props.client.planningDocuments} onClick={() => void inspect()}>核对更新来源用于独立新图</Button>
    {loading && <StatusMessage>正在读取原来源目录…</StatusMessage>}
    {error && current(props.scope) && <StatusMessage tone="warning">{error}</StatusMessage>}
    {visible && <>
      <p>{visible.document.title}：v{props.pin.version} → v{visible.document.version}</p>
      <p>原摘要：{props.pin.digest}</p><p>新摘要：{visible.document.digest}</p>
      <p>其他节点、连接与作者内容保留；不会自动更新其他引用、重建分镜、运行模型或继承旧运行／审核。保存和执行仍会重新校验来源与依赖。</p>
      <label><input type="checkbox" checked={consent === visible.ticket} disabled={props.disabled || loading}
        onChange={event => { if (current(visible.scope) && !live.current.disabled && !locked.current) setConsent(event.target.checked ? visible.ticket : undefined); }} />确认以这份更新来源准备独立新图草稿，保留原图</label>
      <Button disabled={props.disabled || loading || consent !== visible.ticket} onClick={() => {
        if (!current(visible.scope) || live.current.disabled || locked.current || consent !== visible.ticket || consumed.current === visible.ticket) return;
        consumed.current = visible.ticket;
        if (props.prepare(visible.document, visible.scope)) { setPreview(undefined); setConsent(undefined); }
        else { setPreview(undefined); setConsent(undefined); setError('当前图或权限已变化，请重新核对来源。'); }
      }}>准备使用更新来源的独立草稿</Button>
    </>}
  </section>;
}
