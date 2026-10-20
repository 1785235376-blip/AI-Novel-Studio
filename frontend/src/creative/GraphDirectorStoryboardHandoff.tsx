import { useEffect, useRef, useState } from 'react';
import type { PlanningCanvasHandoff } from './directorCanvasHandoff';
import { storyboardCanvasSnapshot } from './storyboardCanvasHandoff';
import { ApiError, apiErrorView } from '../api';
import { Button, StatusMessage } from '../ui/primitives';
import type { GraphDirectorSource } from './GraphDirectorConsole';
import type { CreativeDocument } from './types';
import { storyboardEditorRequest, validStoryboardDocument, type OpenStoryboardEditor } from './storyboardEditorHandoff';
import type { PlanningSnapshot } from './studioProductionGraphContract';
type Props = {
  canvasHandoff?: PlanningCanvasHandoff; sourceScope?: string; isSourceCurrent?: () => boolean;
  client: GraphDirectorSource; source: CreativeDocument; snapshot?: PlanningSnapshot;
  onOpenStoryboard?: OpenStoryboardEditor; canOpen?: boolean;
  active: boolean; canCreate: boolean; busy: boolean; isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>;
  mutate: <T>(work: () => Promise<T>) => Promise<T>; onPending: (value: boolean) => void;
};
/** Creative owns derivation; explicit placement delegates to the original Graph editor. */
export function GraphDirectorStoryboardHandoff(props: Props) {
  const { client, source, snapshot, active, canCreate, busy, read, mutate, onPending } = props;
  const [confirmed, setConfirmed] = useState(false), [working, setWorking] = useState(false), [unknown, setUnknown] = useState(false);
  const [error, setError] = useState(''), [rows, setRows] = useState<CreativeDocument[]>([]);
  const [result, setResult] = useState<{ document: CreativeDocument; digest?: string }>();
  const openEpoch = useRef(0);
  const verified = useRef<{ pin: PlanningSnapshot; generation: number; canvasGeneration: number; isCanvasCurrent: () => boolean; isSourceCurrent: () => boolean; consumed: boolean }>();
  const [placed, setPlaced] = useState(false);
  const canvasLifetime = useRef({ scope: props.canvasHandoff?.verificationScope, generation: 0 });
  if (canvasLifetime.current.scope !== props.canvasHandoff?.verificationScope) {
    canvasLifetime.current = { scope: props.canvasHandoff?.verificationScope, generation: canvasLifetime.current.generation + 1 };
  }
  const alive = useRef(true), lock = useRef(false), current = useRef(props); current.current = props;
  const key = JSON.stringify([source.id, source.version, snapshot, active, props.sourceScope, props.canOpen, !!props.onOpenStoryboard]);
  const identity = useRef({ key, client, generation: 0 });
  if (identity.current.key !== key || identity.current.client !== client) identity.current = { key, client, generation: identity.current.generation + 1 };
  const renderedGeneration = identity.current.generation;
  const valid = (generation: number) => alive.current && current.current.active && current.current.isCurrent() && generation === identity.current.generation;
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => { setConfirmed(false); setRows([]); setResult(undefined); verified.current = undefined; setPlaced(false); setError(''); }, [key, client]);
  useEffect(() => { if (!canCreate) setConfirmed(false); }, [canCreate]);
  const exact = !!snapshot && source.id === snapshot.id && source.version === snapshot.version;
  const ready = exact && canCreate && !busy && !working && !unknown && !!source.scenes.length && !!source.director_notes.length;
  const linked = (row: CreativeDocument) => row.mode === 'STORYBOARD' && !!row.source_documents?.[source.id];
  const matches = (row: CreativeDocument) => linked(row) && row.source_documents?.[source.id]?.version === snapshot?.version && row.source_documents?.[source.id]?.digest === snapshot?.digest;
  async function create() {
    if (!ready || !confirmed || lock.current || !valid(renderedGeneration) || current.current.busy) return;
    const generation = renderedGeneration;
    verified.current = undefined; setPlaced(false);
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
    if (!valid(renderedGeneration) || current.current.busy || busy || lock.current) return;
    const generation = renderedGeneration, canvasGeneration = canvasLifetime.current.generation;
    const canvas = props.canvasHandoff, sourceCurrent = props.isSourceCurrent || props.isCurrent;
    const expected = result && result.document.id === id && result.digest ? { id: result.document.id, version: result.document.version, digest: result.digest } : undefined;
    if (!sourceCurrent()) return;
    verified.current = undefined; setPlaced(false);
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
        let pin: PlanningSnapshot | undefined;
        if (canvas && snapshot && !unknown) {
          const origin = await read(() => client.export(snapshot.id));
          if (!valid(generation) || !sourceCurrent() || canvasGeneration !== canvasLifetime.current.generation || !canvas.isVerificationCurrent()) return;
          if (result?.document.id === id && result.document.version !== value.document.version) throw new Error('分镜版本已变化，请重新读取关联分镜。');
          pin = storyboardCanvasSnapshot(value.document, value.document_digest, snapshot, origin.document, origin.document_digest, expected);
        }
        if (!valid(generation) || !sourceCurrent()) return;
        setResult({ document: value.document, digest: value.document_digest });
        if (pin && canvas) verified.current = { pin, generation, canvasGeneration, isCanvasCurrent: canvas.isVerificationCurrent, isSourceCurrent: sourceCurrent, consumed: false };
        // An older sibling cannot settle an uncertain create operation.
      }
    } catch (reason) { if (valid(generation)) { setRows([]); setError(apiErrorView(reason, '分镜状态读取失败。').message); } }
    finally { lock.current = false; if (alive.current) setWorking(false); }
  }
  function openEditor() {
    if (current.current.canOpen === false || !result?.digest || !snapshot || !props.onOpenStoryboard || busy || working || lock.current || !matches(result.document) || !valid(renderedGeneration)) return;
    const generation = renderedGeneration, ticket = ++openEpoch.current;
    try {
      const request = storyboardEditorRequest(result.document, result.digest, snapshot);
      props.onOpenStoryboard(request, () => valid(generation) && ticket === openEpoch.current);
    } catch (reason) { setError(apiErrorView(reason, '无法打开此分镜，请重新核对原文档。').message); }
  }
  const renderedIntent = verified.current;
  const canPlace = () => {
    const intent = renderedIntent, live = current.current;
    return !!intent && intent === verified.current && !intent.consumed && !unknown && !live.busy && !busy && !working && !lock.current
      && live.canOpen !== false && !!live.canvasHandoff?.available && valid(intent.generation)
      && intent.canvasGeneration === canvasLifetime.current.generation && intent.isCanvasCurrent() && intent.isSourceCurrent();
  };
  function place() {
    if (!canPlace()) return;
    const intent = verified.current!, canvas = current.current.canvasHandoff!;
    intent.consumed = true;
    if (canvas.insert(intent.pin, canvas.scope)) setPlaced(true);
    else setError('当前画布权限、格式、容量或选择已变化，请重新核对分镜；未添加节点。');
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
      {props.canvasHandoff && <Button disabled={!canPlace()} onClick={place}>将此分镜草稿添加到当前画布</Button>}
      {placed && <StatusMessage>已添加一个未连接的分镜草稿节点，尚未保存；可在当前画布撤销或重做。分镜仍需人工复审，素材未获批。</StatusMessage>}
      <ol>{result.document.shots.map(shot => <li key={shot.id}>Shot {shot.number} · {shot.id} · {shot.duration_seconds} 秒 · {shot.shot_size} / {shot.camera_motion}<p>{shot.frame_prompt || shot.action}</p></li>)}</ol>
      <p>后续编辑、复审与制作沿原分镜工作区进行；核对后可明确添加到当前画布，再沿原图保存流程保存。添加不代表任务完成或素材获批，不自动连线或执行。</p>
    </aside>}
  </section>;
}
