import { useEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import { Button, EmptyState, StatusMessage } from '../ui/primitives';
import type { changeImpactClient, ImpactView } from './changeImpactClient';
import { ImpactDecisionPanel } from './ImpactDecisionPanel';
import { Field } from './shared';

type Props = { api: ReturnType<typeof changeImpactClient> };
export function StoryboardImpactDecisions({ api }: Props) {
  const [documentId, setDocumentId] = useState('');
  const [reading, setReading] = useState<{ generation: number; busy: boolean; view?: ImpactView; error?: string }>();
  const running = useRef<number>();
  const lifetime = useRef({ api, documentId, generation: 0, alive: true });
  if (lifetime.current.api !== api || lifetime.current.documentId !== documentId) {
    lifetime.current = { api, documentId, generation: lifetime.current.generation + 1, alive: true };
  }
  const generation = lifetime.current.generation;
  const state = reading?.generation === generation ? reading : undefined;
  const busy = state?.busy === true, error = state?.error, current = state?.view;
  useEffect(() => { lifetime.current.alive = true; return () => { lifetime.current.alive = false; }; }, []);
  const valid = (ticket: number) => lifetime.current.alive && lifetime.current.generation === ticket;
  async function inspect() {
    if (running.current === generation || !documentId.trim() || documentId.length > 240) return;
    const ticket = generation;
    running.current = ticket;
    setReading({ generation: ticket, busy: true });
    try {
      const result = await api.query({ kind: 'CREATIVE_STORYBOARD', id: documentId.trim(), label: documentId.trim(), binding: null });
      if (valid(ticket)) setReading({ generation: ticket, busy: false, view: result });
    } catch (reason) {
      if (valid(ticket)) setReading({ generation: ticket, busy: false, error: reason instanceof ApiError && [401, 403, 404].includes(reason.status)
        ? '当前范围无法读取该 Storyboard 及其关联，请核对权限、功能和原文档。'
        : '影响读取未完成；超过 20 项或证据变化时不会返回部分清单，请重新核对原范围。' });
    } finally { if (valid(ticket)) running.current = undefined; }
  }
  function change(value: string) {
    lifetime.current = { ...lifetime.current, documentId: value, generation: lifetime.current.generation + 1 };
    setDocumentId(value); setReading(undefined);
  }
  return <section className="experimental-section" aria-label="Storyboard 来源决策">
    <h3>Storyboard 来源决策</h3>
    <p>输入一个已保存的 Storyboard ID，读取最多 20 个已保存图中的直接来源引用。无需正式资产；其他模块和间接关系仍为未知。</p>
    <Field label="Storyboard 文档 ID"><input value={documentId} maxLength={240} onChange={event => change(event.target.value)} /></Field>
    <Button disabled={busy || !documentId.trim()} onClick={() => void inspect()}>读取 Storyboard 直接影响</Button>
    {busy && <StatusMessage>正在核对原 Storyboard 和每个图的读取权限与版本…</StatusMessage>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    {current && !busy && <>
      <p>已读取 {current.items.length} 项直接引用；保存重建意图后，仍需到原模块核对和执行。</p>
      {!current.items.length && <EmptyState title="未找到可读取的直接引用" detail="此结果不代表其他模块或间接依赖没有影响。" />}
      <ImpactDecisionPanel key={generation} api={api} view={current} disabled={busy} />
    </>}
  </section>;
}
