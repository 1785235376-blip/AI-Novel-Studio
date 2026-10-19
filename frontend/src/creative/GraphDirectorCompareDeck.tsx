import { useLayoutEffect, useRef, useState } from 'react';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { StudioGraphDirectorConsole } from './StudioGraphDirectorConsole';
import { GraphDirectorRunOverview, type DirectorRunReader } from './GraphDirectorRunOverview';
import type { StudioGraphClient } from './studioGraphClient';
import type { StudioGraphDefinition, StudioGraphRecord } from './studioGraphTypes';
type Props = { definition: StudioGraphDefinition; base?: StudioGraphRecord; identity: string; active: boolean;
  client: Pick<StudioGraphClient, 'readDirectorWorkspace'> & DirectorRunReader; busy?: boolean;
  onLocate?: (nodeId: string, graph: StudioGraphRecord) => boolean; isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T> };
export function GraphDirectorCompareDeck(props: Props) {
  const nodes = props.definition.nodes.filter(node => node.definition_id === 'director_plan');
  const key = JSON.stringify([props.identity, props.base?.id, props.base?.version,
    nodes.map(node => [node.id, node.parameters.document_snapshot]), props.base?.reference_states]);
  const authority = useRef({ key, client: props.client, generation: 0 });
  if (authority.current.key !== key || authority.current.client !== props.client) authority.current = { key, client: props.client, generation: authority.current.generation + 1 };
  if (!props.active || !props.isCurrent() || !nodes.length) return null;
  return <DirectorCompareSession key={authority.current.generation} {...props} />;
}
function DirectorCompareSession(props: Props) {
  const [chosen, setChosen] = useState<string[]>([]);
  const alive = useRef(true), live = useRef(props); live.current = props;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const current = () => alive.current && live.current.active && live.current.isCurrent();
  const nodes = props.definition.nodes.filter(node => node.definition_id === 'director_plan');
  const states = new Map(props.base?.reference_states.map(row => [row.node_id, row.state]) ?? []);
  function toggle(id: string, checked: boolean) {
    if (!current() || !nodes.some(node => node.id === id)) return;
    setChosen(previous => checked ? previous.includes(id) || previous.length >= 3 ? previous : [...previous, id] : previous.filter(value => value !== id));
  }
  return <Panel title="导演节点对照"><p>可同时保留最多三个原导演节点控制台。选择后分别展开核对来源；不会创建导演文档或执行任务。各窗口的镜头语言草稿仅属于本次查看，关闭或切换图版本后清空。</p>
    <div className="creative-actions">{nodes.map(node => <label key={node.id}><input type="checkbox" checked={chosen.includes(node.id)} disabled={!chosen.includes(node.id) && chosen.length >= 3} onChange={event => toggle(node.id,event.target.checked)} />对照 {node.id} · {node.parameters.document_snapshot?.id || '来源不可用'}</label>)}
      <Button disabled={!chosen.length} onClick={() => { if (current()) setChosen([]); }}>关闭全部导演对照</Button></div>
    {chosen.length === 3 && <StatusMessage>已达到三个对照窗口上限，可先关闭其中一个。</StatusMessage>}
    <div className="creative-form-grid">{nodes.filter(node => chosen.includes(node.id)).map(node => <section key={node.id} aria-label={`导演对照 ${node.id}`}><h4>{node.id} · v{node.parameters.document_snapshot?.version ?? '?'}</h4>
      <StudioGraphDirectorConsole client={props.client} nodeId={node.id} snapshot={node.parameters.document_snapshot}
        identity={props.identity} active={props.active} referenceState={states.get(node.id)} isCurrent={props.isCurrent} read={props.read} />
      <GraphDirectorRunOverview {...props} nodeId={node.id} />
    </section>)}</div>
  </Panel>;
}
