import { useEffect, useMemo, useRef, useState } from 'react';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { createStoryFactClient, purposes, type FactPurpose, type FactTarget, type FactUse, type StoryFact } from './storyFactClient';
import './storyFactUsage.css';
import { StoryFactDownstreamImpact } from './StoryFactDownstreamImpact';

type Props = { projectId: string; identity: string; target: FactTarget | null; transport: StudioGraphTransport;
  enabled: boolean; writable: boolean; busy: boolean; isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>; mutate: <T>(work: () => Promise<T>) => Promise<T> };
export function StoryFactUsagePanel(props: Props) {
  const key = JSON.stringify([props.identity, props.projectId, props.target, props.enabled, props.writable, props.isCurrent()]);
  const lifetime = useRef({ key, transport: props.transport, generation: 0 });
  if (lifetime.current.key !== key || lifetime.current.transport !== props.transport) {
    lifetime.current = { key, transport: props.transport, generation: lifetime.current.generation + 1 };
  }
  const generation = lifetime.current.generation;
  return <FactSession key={generation} {...props} isCurrent={() => lifetime.current.generation === generation && props.isCurrent()} />;
}
function FactSession(props: Props) {
  const client = useMemo(() => createStoryFactClient(props.projectId, props.transport), [props.projectId, props.transport]);
  const [facts, setFacts] = useState<StoryFact[]>([]), [uses, setUses] = useState<FactUse[] | null>(null);
  const [selected, setSelected] = useState(''), [purpose, setPurpose] = useState<FactPurpose>('CAUSAL_CONTEXT');
  const [rationale, setRationale] = useState(''), [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(false), [problem, setProblem] = useState(''), [notice, setNotice] = useState('');
  const alive = useRef(true), running = useRef(false), latest = useRef(props); latest.current = props;
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const current = () => alive.current && latest.current.enabled && latest.current.isCurrent();
  const available = props.enabled && props.target !== null && props.isCurrent();
  const fact = facts.find(row => row.id === selected);
  const load = async () => {
    if (!current() || !props.target || props.busy || running.current) return;
    running.current = true; setLoading(true); setProblem(''); setNotice(''); setConfirmed(false); setSelected(''); setFacts([]); setUses(null);
    try {
      const found = await props.read(() => client.impact(props.target!.document_id));
      if (!current()) return;
      setUses(found);
      const sources = await props.read(() => client.facts());
      if (current()) setFacts(sources);
    } catch (error) { if (current()) { setFacts([]); setUses(null); setProblem(error instanceof Error ? error.message : '读取失败，请重试。'); } }
    finally { running.current = false; if (alive.current) setLoading(false); }
  };
  const save = async () => {
    if (!current() || !props.target || !props.writable || props.busy || running.current || !fact || !confirmed || !rationale.trim()) return;
    running.current = true; setLoading(true); setConfirmed(false); setProblem(''); setNotice('');
    try {
      const savedBinding = await props.mutate(() => client.confirm(props.target!, fact, purpose, rationale));
      if (!current()) return;
      const rows = await props.read(() => client.impact(props.target!.document_id));
      if (!current()) return;
      setUses(rows);
      const saved = rows.some(row => row.id === savedBinding.id && row.version === savedBinding.version && row.fact.id === fact.id && row.fact.version === fact.version && row.fact.digest === fact.digest
        && row.target.shot_id === props.target!.shot_id && row.target.shot_digest === props.target!.shot_digest
        && row.target.document_digest === props.target!.document_digest
        && row.target.document_version === props.target!.document_version && row.target.shot_version === props.target!.shot_version
        && row.target.scene_id === props.target!.scene_id && row.purpose === purpose && row.rationale === rationale);
      if (!saved) throw new Error('写入结果尚未回读确认，请重新读取依赖后核对。');
      setNotice('已回读确认事实使用记录；未批准来源或素材，未调用模型。');
    } catch (error) { if (current()) setProblem(error instanceof Error ? error.message : '保存结果未确认，请重新读取。'); }
    finally { running.current = false; if (alive.current) setLoading(false); }
  };
  return <Panel title="故事事实使用与影响（有限覆盖）" className="story-fact-usage">
    <p>仅覆盖明确确认的事实使用与当前镜头素材绑定。未记录的依赖未知；不自动重生成。</p>
    <p>这里只接受在当前原项目世代中新建并明确批准的事实。旧版或未绑定的记录仍可在原 Story Graph 阅读；请在那里复制或新建候选并审核批准，不会静默迁移。</p>
    <p>本阶段未评估时间推理、语义因果或 Export 影响；成本未知。Graph / Timeline 可对单个正式素材明确检查已保存直接引用。</p>
    <Button disabled={!available || props.busy || loading} onClick={() => void load()} loading={loading}>读取事实依赖</Button>
    {!available && <StatusMessage tone="warning">请在可用的原分镜入口选择已保存镜头。</StatusMessage>}
    {problem && <StatusMessage tone="error">{problem}</StatusMessage>}
    {notice && <StatusMessage tone="success">{notice}</StatusMessage>}
    {uses !== null && <>
      {uses.length === 0 && <p>当前可读范围内没有显式事实使用记录；不能据此认定没有影响。</p>}
      {uses.map(row => <section key={row.id} aria-label={`事实使用 ${row.id}`}>
        <p>{row.current_fact.title} · {row.state} · 记录 {row.id} v{row.version}</p>
        <p>固定事实 {row.fact.id} v{row.fact.version} · {row.fact.digest}</p>
        <p>当前事实 {row.current_fact.id} v{row.current_fact.version} · {row.current_fact.digest} · {row.current_fact.status}</p>
        <p>文档 {row.target.document_id} v{row.target.document_version} · {row.target.document_digest}</p>
        <p>场景 {row.target.scene_id} · 镜头 {row.target.shot_id} v{row.target.shot_version} · {row.target.shot_digest}</p>
        <p>{row.purpose}：{row.rationale}</p>
        {row.blockers.length > 0 && <StatusMessage tone="warning">阻塞：{row.blockers.join('、')}</StatusMessage>}
        {row.assets.map(a => <p key={a.asset_id}>{a.kind} 素材 {a.asset_id} v{a.version} · {a.digest}</p>)}
        {row.assets.length === 0 && <p>未显示可核实的当前镜头素材绑定。</p>}
      </section>)}
      {props.target && <StoryFactDownstreamImpact {...props} target={props.target} uses={uses} enabled={available} />}
      <label>已批准事实<select value={selected} disabled={loading || !props.writable} onChange={e => { setSelected(e.target.value); setConfirmed(false); }}>
        <option value="">选择事实</option>{facts.map(f => <option key={f.id} value={f.id}>{f.title} · {f.id} v{f.version}</option>)}
      </select></label>
      {facts.length === 0 && <p>当前没有可选择的已批准世界事实关系。</p>}
      {fact && <p>待固定事实 {fact.id} v{fact.version} · {fact.digest}</p>}
      {props.target && <p>目标 {props.target.document_id} v{props.target.document_version} · {props.target.document_digest} · 场景 {props.target.scene_id} · 镜头 {props.target.shot_id} v{props.target.shot_version} · {props.target.shot_digest}</p>}
      <label>使用目的<select value={purpose} disabled={loading || !props.writable} onChange={e => { setPurpose(e.target.value as FactPurpose); setConfirmed(false); }}>{purposes.map(p => <option key={p}>{p}</option>)}</select></label>
      <label>使用理由<textarea maxLength={1000} value={rationale} disabled={loading || !props.writable} onChange={e => { setRationale(e.target.value); setConfirmed(false); }} /></label>
      <label><input type="checkbox" checked={confirmed} disabled={!fact || loading || !props.writable} onChange={e => setConfirmed(e.target.checked)} />我确认此固定事实用于所选镜头；这不会批准来源或素材。</label>
      {!props.writable && <p>原入口未开放写入；事实使用登记需要作者写入与审核权限。</p>}
      <Button disabled={!available || !props.writable || props.busy || loading || !fact || !confirmed || !rationale.trim()} onClick={() => void save()}>确认事实使用</Button>
    </>}
  </Panel>;
}
