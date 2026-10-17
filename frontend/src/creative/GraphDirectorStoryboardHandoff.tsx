import { useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { Button, StatusMessage } from '../ui/primitives';
import type { GraphDirectorSource } from './GraphDirectorConsole';
import type { CreativeDocument } from './types';
import { storyboardEditorRequest, validStoryboardDocument, type OpenStoryboardEditor } from './storyboardEditorHandoff';
import type { PlanningSnapshot } from './studioProductionGraphContract';
type Props = {
  client: GraphDirectorSource; source: CreativeDocument; snapshot?: PlanningSnapshot;
  onOpenStoryboard?: OpenStoryboardEditor; canOpen?: boolean;
  active: boolean; canCreate: boolean; busy: boolean; isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>;
  mutate: <T>(work: () => Promise<T>) => Promise<T>; onPending: (value: boolean) => void;
};
/** Explicit handoff to the existing Creative derivation owner; no graph writes. */
export function GraphDirectorStoryboardHandoff(props: Props) {
  const { client, source, snapshot, active, canCreate, busy, read, mutate, onPending } = props;
  const [confirmed, setConfirmed] = useState(false), [working, setWorking] = useState(false), [unknown, setUnknown] = useState(false);
  const [error, setError] = useState(''), [rows, setRows] = useState<CreativeDocument[]>([]);
  const [result, setResult] = useState<{ document: CreativeDocument; digest?: string }>();
  const openEpoch = useRef(0);
  const alive = useRef(true), lock = useRef(false), current = useRef(props); current.current = props;
  const key = JSON.stringify([source.id, source.version, snapshot, active, props.canOpen, !!props.onOpenStoryboard]);
  const identity = useRef({ key, client, generation: 0 });
  if (identity.current.key !== key || identity.current.client !== client) identity.current = { key, client, generation: identity.current.generation + 1 };
  const valid = (generation: number) => alive.current && current.current.active && current.current.isCurrent() && generation === identity.current.generation;
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => { setConfirmed(false); setRows([]); setResult(undefined); setError(''); }, [key, client]);
  useEffect(() => { if (!canCreate) setConfirmed(false); }, [canCreate]);
  const exact = !!snapshot && source.id === snapshot.id && source.version === snapshot.version;
  const ready = exact && canCreate && !busy && !working && !unknown && !!source.scenes.length && !!source.director_notes.length;
  const linked = (row: CreativeDocument) => row.mode === 'STORYBOARD' && !!row.source_documents?.[source.id];
  const matches = (row: CreativeDocument) => linked(row) && row.source_documents?.[source.id]?.version === snapshot?.version && row.source_documents?.[source.id]?.digest === snapshot?.digest;
  async function create() {
    if (!ready || !confirmed || lock.current || !current.current.isCurrent()) return;
    const generation = identity.current.generation;
    lock.current = true; setWorking(true); setUnknown(true); onPending(true); setConfirmed(false); setError(''); setResult(undefined);
    try {
      const row = await mutate(() => client.derive(source, 'STORYBOARD', 'DIRECTOR_NOTES'));
      if (!valid(generation)) return;
      if (!row?.id || row.id === source.id || !Array.isArray(row.shots) || !Number.isSafeInteger(row.version) || row.version < 1 || row.status !== 'DRAFT' || !matches(row)) throw new Error('分镜回执与预览来源不一致。');
      setResult({ document: row }); setUnknown(false); onPending(false);
    } catch (reason) {
      if (!valid(generation)) return;
      setError(apiErrorView(reason, '分镜建立结果未核实，请读取原目录，勿重复建立。').message);
      if (reason instanceof ApiError && reason.status >= 400 && reason.status < 500 && reason.status !== 408) { setUnknown(false); onPending(false); }
    } finally { lock.current = false; if (alive.current) setWorking(false); }
  }
  async function inspect(id?: string) {
    if (!active || !current.current.isCurrent() || busy || lock.current) return;
    const generation = identity.current.generation;
    openEpoch.current++;
    lock.current = true; setWorking(true); setError(''); setResult(undefined);
    try {
      if (!id) {
        setRows([]); const value = await read(() => client.list());
        if (valid(generation)) setRows(value.items.filter(linked));
      } else {
        const value = await read(() => client.export(id));
        if (!valid(generation)) return;
        if (value.document?.id !== id || !validStoryboardDocument(value.document) || !linked(value.document) || !Number.isSafeInteger(value.document.version) || value.document.version < 1 || !/^[a-f0-9]{64}$/.test(value.document_digest)) throw new Error('分镜来源回执无效。');
        setResult({ document: value.document, digest: value.document_digest });
        // An older sibling cannot settle an uncertain create operation.
      }
    } catch (reason) { if (valid(generation)) { setRows([]); setError(apiErrorView(reason, '分镜状态读取失败。').message); } }
    finally { lock.current = false; if (alive.current) setWorking(false); }
  }
  function openEditor() {
    if (current.current.canOpen === false || !result?.digest || !snapshot || !props.onOpenStoryboard || busy || working || lock.current || !matches(result.document) || !valid(identity.current.generation)) return;
    const generation = identity.current.generation, ticket = ++openEpoch.current;
    try {
      const request = storyboardEditorRequest(result.document, result.digest, snapshot);
      props.onOpenStoryboard(request, () => valid(generation) && ticket === openEpoch.current);
    } catch (reason) { setError(apiErrorView(reason, '无法打开此分镜，请重新核对原文档。').message); }
  }
  if (!active) return null;
  return <section aria-label="导演到分镜交接">
    <h3>导演到分镜 · 原文档交接</h3>
    <p>人工调度的确定性复制，非模型分析。每条已保存导演调度建立一个 Shot 草稿；无调度的场景不产生 Shot。不会批准素材、执行任务或更新图绑定。</p>
    {exact ? <p>交接来源：{snapshot.id} · v{snapshot.version} · {snapshot.digest}；{source.director_notes.length} 条调度。目标：新的独立分镜草稿。</p> : <p>先核对导演原文档版本与摘要，再预览交接。</p>}
    <label><input type="checkbox" checked={confirmed} disabled={!ready} onChange={event => setConfirmed(event.target.checked)} />已核对来源，明确建立新的分镜草稿，仍需人工复审</label>
    <Button disabled={!ready || !confirmed} onClick={() => void create()}>交接到原分镜草稿</Button>
    <Button disabled={busy || working} onClick={() => void inspect()}>读取关联分镜与状态</Button>
    {unknown && <StatusMessage tone="warning">分镜建立结果未知或待核对，禁止重复提交。请在原分镜目录核对；读取已有记录不能证明本次请求未执行。关闭工作区前请记录此状态。</StatusMessage>}
    {working && <StatusMessage>正在与原 Creative owner 核对分镜…</StatusMessage>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    <ul>{rows.map(row => <li key={row.id}><Button disabled={busy || working} onClick={() => void inspect(row.id)}>读取分镜 {row.title} · v{row.version}</Button></li>)}</ul>
    {result && <aside aria-label="分镜原文档状态回传">
      <p>{result.document.title} · {result.document.id} · v{result.document.version} · {result.document.status} · {result.digest || '摘要尚未核对，请读取原分镜'}</p>
      <p>导演来源：v{result.document.source_documents?.[source.id]?.version} · {result.document.source_documents?.[source.id]?.digest}</p>
      {!matches(result.document) && <StatusMessage tone="warning">此分镜绑定另一导演版本；不会自动覆盖或重绑。</StatusMessage>}
      <Button disabled={busy || working} onClick={() => void inspect(result.document.id)}>核对分镜原文档版本</Button>
      {props.onOpenStoryboard && <Button disabled={!result.digest || !matches(result.document) || props.canOpen === false || busy || working} onClick={openEditor}>在原分镜编辑器打开</Button>}
      <ol>{result.document.shots.map(shot => <li key={shot.id}>Shot {shot.number} · {shot.id} · {shot.duration_seconds} 秒 · {shot.shot_size} / {shot.camera_motion}<p>{shot.frame_prompt || shot.action}</p></li>)}</ol>
      <p>后续编辑、复审与制作沿原分镜工作区进行；这里只回显文档状态，不代表任务完成或素材获批。在原制作节点目录明确添加分镜节点后，才会形成新的图绑定。</p>
    </aside>}
  </section>;
}
