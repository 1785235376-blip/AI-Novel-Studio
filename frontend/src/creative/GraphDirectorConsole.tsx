import { useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { GraphDirectorStoryboardHandoff } from './GraphDirectorStoryboardHandoff';
import { CreativeCanvas } from './CreativeCanvas';
import type { creativeClient } from './client';
import { creativeAuthoringProblems, documentInput, newDocument, type CreativeDocument, type CreativeInput } from './types';
import type { PlanningSnapshot } from './studioProductionGraphContract';
import './creative.css';

export type GraphDirectorSource = Pick<ReturnType<typeof creativeClient>, 'create' | 'update' | 'export' | 'capabilities' | 'list' | 'derive'>;
type Props = {
  client: GraphDirectorSource;
  pin?: PlanningSnapshot;
  selectionKey?: string;
  active: boolean;
  canMutate: boolean;
  busy: boolean;
  isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>;
  mutate: <T>(work: () => Promise<T>) => Promise<T>;
  onDirtyChange: (dirty: boolean) => void;
};
const empty = (): CreativeInput => ({ ...newDocument('DIRECTOR'), source_independent: true });
const samePin = (a: PlanningSnapshot, b: PlanningSnapshot) => a.id === b.id && a.version === b.version && a.digest === b.digest;

/** A mounted view of the original Creative owner. Only author drafts live here;
 * Graph retains its exact pin and all execution/review remains with its owners. */
export function GraphDirectorConsole({ client, pin, selectionKey, active, canMutate, busy, isCurrent, read, mutate, onDirtyChange }: Props) {
  const [handoffPending, setHandoffPending] = useState(false), [storyboardAllowed, setStoryboardAllowed] = useState(false);
  const [open, setOpen] = useState(false), [authorized, setAuthorized] = useState(false);
  const [draft, setDraft] = useState<CreativeInput>(empty), [base, setBase] = useState<CreativeDocument>();
  const [dirty, setDirty] = useState(false), [blocked, setBlocked] = useState(false), [working, setWorking] = useState(false);
  const [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [candidate, setCandidate] = useState<{ document: CreativeDocument; pin: PlanningSnapshot }>();
  const [snapshot, setSnapshot] = useState<PlanningSnapshot>(), [discardConfirmed, setDiscardConfirmed] = useState(false);
  const [documents, setDocuments] = useState<Pick<CreativeDocument, 'id' | 'title' | 'version'>[]>([]), [choice, setChoice] = useState('');
  const [scene, setScene] = useState<string>(), [shot, setShot] = useState<string>();
  const alive = useRef(true), lock = useRef(false), epoch = useRef(0);
  const selectedPinRef = useRef(pin); selectedPinRef.current = pin;
  const scope = useRef({ active, isCurrent, client, generation: 0 });
  if (scope.current.active !== active || scope.current.client !== client) scope.current.generation++;
  scope.current = { active, isCurrent, client, generation: scope.current.generation };
  const selection = useRef({ key: '', generation: 0 });
  const selectedKey = JSON.stringify([selectionKey, pin]);
  if (selection.current.key !== selectedKey) selection.current = { key: selectedKey, generation: selection.current.generation + 1 };
  const ownerClient = useRef(client);
  const current = () => alive.current && scope.current.active && scope.current.isCurrent() && ownerClient.current === scope.current.client;
  const owns = (generation: number) => current() && scope.current.generation === generation;
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  useEffect(() => { if (!active) epoch.current++; }, [active]);
  const pending = dirty || blocked || handoffPending;
  const reportedPending = useRef(false);
  useEffect(() => { if (reportedPending.current !== pending) { reportedPending.current = pending; onDirtyChange(pending); } }, [pending, onDirtyChange]);
  const editing = authorized && canMutate && active && !busy && !working && !blocked && !handoffPending && isCurrent();
  const mark = (value: boolean) => { setDirty(value); onDirtyChange(value); };
  const fail = (reason: unknown) => {
    setError(apiErrorView(reason, '导演文档操作未完成，请核对连接与原文档。').message);
    if (reason instanceof ApiError && [401, 403].includes(reason.status)) {
      setAuthorized(false); setBase(undefined); setSnapshot(undefined); setCandidate(undefined); setDocuments([]); setChoice('');
    }
  };
  async function reveal() {
    if (!current() || lock.current || busy) return;
    const generation = scope.current.generation, ticket = ++epoch.current;
    lock.current = true; setWorking(true); setOpen(true); setError('');
    try {
      const caps = await read(() => client.capabilities());
      if (owns(generation) && ticket === epoch.current) { setAuthorized(caps.enabled && caps.can_mutate && caps.modes.includes('DIRECTOR')); setStoryboardAllowed(caps.enabled && caps.can_mutate && caps.modes.includes('STORYBOARD')); }
    } catch (reason) { if (owns(generation) && ticket === epoch.current) fail(reason); }
    finally { lock.current = false; if (alive.current) setWorking(false); }
  }
  async function listDocuments() {
    if (!current() || lock.current || busy) return;
    lock.current = true; setWorking(true); setError('');
    const ticket = ++epoch.current, generation = scope.current.generation;
    try {
      const value = await read(() => client.list());
      if (!owns(generation) || ticket !== epoch.current) return;
      setDocuments(value.items.filter(row => row.mode === 'DIRECTOR').map(({ id, title, version }) => ({ id, title, version })));
      setChoice('');
    } catch (reason) { if (owns(generation) && ticket === epoch.current) fail(reason); }
    finally { lock.current = false; if (alive.current) setWorking(false); }
  }
  function change(value: CreativeInput) {
    if (!editing || lock.current || value.mode !== 'DIRECTOR') return;
    setDraft(value); mark(true); setNotice(''); setCandidate(undefined); setDiscardConfirmed(false);
  }
  function fresh() {
    if (!editing || lock.current || pending) return;
    setDraft(empty()); setBase(undefined); setSnapshot(undefined); setCandidate(undefined); setScene(undefined); setShot(undefined); setNotice('');
  }
  async function save() {
    if (!editing || lock.current || !dirty || !draft.title.trim() || creativeAuthoringProblems(draft).length) return;
    lock.current = true; setWorking(true); setBlocked(true); setError('');
    setNotice('保存请求已提交，结果核对完成前不会重复写入。');
    const input = documentInput(draft), origin = base, generation = scope.current.generation, ticket = ++epoch.current;
    try {
      const row = await mutate(() => origin ? client.update(origin.id, origin.version, input) : client.create(input));
      if (!owns(generation) || ticket !== epoch.current) return;
      if (row.mode !== 'DIRECTOR' || typeof row.id !== 'string' || !row.id.trim() || !Number.isSafeInteger(row.version) || row.version < 1 || origin && (row.id !== origin.id || row.version !== origin.version + 1)) throw new Error('导演保存回执不匹配。');
      setBase(row); setDraft(documentInput(row)); setSnapshot(undefined); setBlocked(false); mark(false);
      setNotice(`导演原文档已保存 · v${row.version}。请读取原文档核对摘要；图绑定保持原版本。保存不批准、不调用模型。`);
    } catch (reason) {
      if (!owns(generation) || ticket !== epoch.current) return;
      fail(reason);
      if (!(reason instanceof ApiError) || reason.status >= 500 || reason.status === 409) {
        setBlocked(true); onDirtyChange(true);
        setNotice('保存冲突或回执不确定，草稿保留，禁止重复写入。核对原文档后明确采用，或到原文档目录核对首次创建结果。');
      } else setBlocked(false);
    } finally { lock.current = false; if (alive.current) setWorking(false); }
  }
  async function inspect(target: string, selectedPin?: PlanningSnapshot) {
    if (!current() || lock.current || busy || !target) return;
    lock.current = true; setWorking(true); setError(''); setCandidate(undefined); setDiscardConfirmed(false);
    const ticket = ++epoch.current, generation = scope.current.generation, selectedGeneration = selection.current.generation;
    try {
      const value = await read(() => client.export(target));
      if (!owns(generation) || ticket !== epoch.current || selectedPin && (selectedGeneration !== selection.current.generation || !selectedPinRef.current || !samePin(selectedPin, selectedPinRef.current))) return;
      if (value.document.id !== target || value.document.mode !== 'DIRECTOR' || !Number.isSafeInteger(value.document.version)
        || value.document.version < 1 || !/^[a-f0-9]{64}$/.test(value.document_digest)) throw new Error('导演来源回执不完整。');
      const verified = { id: target, version: value.document.version, digest: value.document_digest };
      if (pending) setCandidate({ document: value.document, pin: verified });
      else { setBase(value.document); setDraft(documentInput(value.document)); setSnapshot(verified); setScene(undefined); setShot(undefined); }
      setNotice(selectedPin && !samePin(selectedPin, verified)
        ? '来源已变化：这里是当前原文档，不能当作节点绑定的旧版本。旧图绑定保持不变，请另建明确绑定当前版本的节点／图。'
        : '已从原 Creative owner 读取当前版本与摘要；没有执行或批准内容。');
    } catch (reason) { if (owns(generation) && ticket === epoch.current) fail(reason); }
    finally { lock.current = false; if (alive.current) setWorking(false); }
  }
  function discard() {
    if (!current() || busy || lock.current || !discardConfirmed) return;
    setDraft(candidate ? documentInput(candidate.document) : base ? documentInput(base) : empty());
    if (candidate) { setBase(candidate.document); setSnapshot(candidate.pin); }
    if (blocked && !candidate) setNotice('仅放弃了本地草稿；远端保存结果仍未知。再次创建前先核对原文档目录，避免重复创建。');
    setCandidate(undefined); setBlocked(false); mark(false); setDiscardConfirmed(false); setError('');
  }
  if (!active || !isCurrent()) return null;
  if (ownerClient.current !== client) return <StatusMessage tone="warning">导演来源连接已改变，请重新打开工作区。</StatusMessage>;
  return <Panel title="画布导演总控台 · 可选">
    <p>人工编排：复用原导演文档、版本与审核。此面板可关闭；不要求其它模块先经过导演。</p>
    {!open ? <Button disabled={busy || working} onClick={() => void reveal()}>打开导演总控台</Button> : <>
      <Button disabled={pending || busy || working} onClick={() => setOpen(false)}>折叠导演总控台</Button>
      {!authorized && !working && <StatusMessage tone="warning">原 Creative owner 尚未授予导演编辑能力；仍可核对当前选中节点的来源。</StatusMessage>}
      <Button disabled={busy || working} onClick={() => void listDocuments()}>读取导演原文档目录</Button>
      <label>总控台原导演文档<select value={choice} disabled={busy || working} onChange={event => setChoice(event.target.value)}>
        <option value="">明确选择原文档</option>{documents.map(row => <option key={row.id} value={row.id}>{row.title} · v{row.version}</option>)}
      </select></label>
      <Button disabled={!choice || busy || working} onClick={() => void inspect(choice, pin?.id === choice ? pin : undefined)}>读取所选导演原文档</Button>
      <Button disabled={!pin || pending || busy || working} onClick={() => pin && void inspect(pin.id, pin)}>读取选中导演节点原文档</Button>
      <Button disabled={!base || busy || working} onClick={() => base && void inspect(base.id, pin?.id === base.id ? pin : undefined)}>核对导演原文档版本</Button>
      {pin && <p>选中节点绑定：{pin.id} · v{pin.version} · {pin.digest}</p>}
      {snapshot && <p>当前原文档：{snapshot.id} · v{snapshot.version} · {snapshot.digest}</p>}
      {pin && base?.id === pin.id && (base.version !== pin.version || snapshot && !samePin(pin, snapshot)) && <StatusMessage tone="warning">节点来源已变更，原绑定没有自动更新；请核对下游影响。</StatusMessage>}
      {notice && <StatusMessage>{notice}</StatusMessage>}{error && <StatusMessage tone="error">{error}</StatusMessage>}
      {working && <StatusMessage>正在读取或保存原导演文档…</StatusMessage>}
      <CreativeCanvas draft={draft} version={base?.version} dirty={dirty} canEdit={editing} busy={busy || working}
        selectedSceneId={scene} selectedShotId={shot} onScene={setScene} onShot={setShot} onChange={change}
        onSave={() => void save()} onNew={fresh} />
      {base && <GraphDirectorStoryboardHandoff client={client} source={base} snapshot={snapshot} active={active && authorized} canCreate={editing && !dirty && storyboardAllowed} busy={busy || working} isCurrent={isCurrent} read={read} mutate={mutate} onPending={setHandoffPending} />}
      {(dirty || blocked) && <section aria-label="导演草稿处理"><p>导演草稿尚未保存或待核对，图编辑与运行暂时锁定。内容仅保留在本次页面中，关闭页面可能丢失。</p>
        {candidate && <p>已核对服务端：{candidate.document.title} · v{candidate.document.version} · {candidate.pin.digest}</p>}
        <label><input type="checkbox" checked={discardConfirmed} disabled={busy || working} onChange={event => setDiscardConfirmed(event.target.checked)} />{blocked && !candidate ? '确认仅放弃导演本地草稿，远端结果仍未知；再次创建前先核对目录' : '确认放弃导演本地草稿'}{candidate ? '并采用已核对原版本' : ''}</label>
        <Button disabled={!discardConfirmed || busy || working} onClick={discard}>处理导演本地草稿</Button>
      </section>}
      <p>保存后，在原“导演、分镜与视觉制作节点目录”中读取文档并添加导演节点，再保存创作图。节点只保存 ID、版本与摘要；连接与执行仍走原图及人工审核。</p>
    </>}
  </Panel>;
}
