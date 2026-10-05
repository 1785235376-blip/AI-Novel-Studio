import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { ApiError } from '../api';
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import type { Row } from './api';

export function useResource<T>(load: (signal: AbortSignal) => Promise<T>, dependencies: unknown[]) {
  const loader = useRef(load); loader.current = load;
  const [data, setData] = useState<T>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>();
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(undefined);
    loader.current(controller.signal).then(value => { if (!controller.signal.aborted) setData(value); })
      .catch(value => { if (!controller.signal.aborted) setError(value); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [...dependencies, revision]);
  return { data, loading, error, reload: useCallback(() => setRevision(value => value + 1), []) };
}
export function useAction(refresh?: () => void) {
  const [busy, setBusy] = useState(false), [error, setError] = useState<unknown>(), [notice, setNotice] = useState('');
  const alive = useRef(true), running = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const run = async (operation: () => Promise<unknown>, message = '已保存') => {
    if (running.current) return;
    running.current = true; setBusy(true); setError(undefined); setNotice('');
    try { await operation(); if (alive.current) { setNotice(message); refresh?.(); } }
    catch (value) { if (alive.current) setError(value); }
    finally { running.current = false; if (alive.current) setBusy(false); }
  };
  return { run, busy, feedback: <>{error && <ErrorMessage error={error} />}{notice && <StatusMessage tone="success">{notice}</StatusMessage>}</> };
}
export function ErrorMessage({ error }: { error: unknown }) {
  return <StatusMessage tone="error">{error instanceof ApiError ? `${error.message} (${error.problem.code})` : '读取或操作失败，请重试。'}</StatusMessage>;
}
export function ResourceState({ loading, error, empty = false }: { loading: boolean; error?: unknown; empty?: boolean }) {
  return <>{loading && <StatusMessage>正在读取…</StatusMessage>}{!!error && <ErrorMessage error={error} />}{!loading && !error && empty && <EmptyState title="暂无记录" detail="创建记录后会显示在这里。" />}</>;
}
export function Details({ value, label = '来源与详情', open = false }: { value: unknown; label?: string; open?: boolean }) {
  return <details open={open || undefined} className="experimental-details"><summary>{label}</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>;
}
export function RecordStatus({ row }: { row: Row }) {
  return <div className="experimental-actions"><Badge tone={row.status === 'APPROVED' || row.status === 'COMMITTED' || row.status === 'SUCCEEDED' ? 'success' : 'neutral'}>{row.status || 'DRAFT'} · v{row.version}</Badge>{row.stale && <Badge tone="warning">STALE · 来源已变化</Badge>}{row.execution_mode && <Badge tone="info">{row.execution_mode}</Badge>}</div>;
}
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="experimental-field"><span>{label}</span>{children}</label>;
}
export function Form({ children, onSubmit }: { children: ReactNode; onSubmit: () => void }) {
  return <form className="experimental-form" onSubmit={(event: FormEvent) => { event.preventDefault(); onSubmit(); }}>{children}</form>;
}
export function Refresh({ reload, busy }: { reload: () => void; busy?: boolean }) {
  return <Button type="button" disabled={busy} onClick={reload}>刷新实验记录</Button>;
}
export function ids(text: string) { return text.split(/[,，\s]+/).map(value => value.trim()).filter(Boolean); }
export function ObjectInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <Field label={label}><textarea value={value} onChange={event => onChange(event.target.value)} /></Field>;
}
export function objectValue(value: string): Record<string, any> {
  const parsed = JSON.parse(value || '{}');
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error('请输入 JSON 对象');
  return parsed;
}
