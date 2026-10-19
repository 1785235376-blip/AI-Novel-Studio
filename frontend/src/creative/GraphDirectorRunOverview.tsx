import { useLayoutEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { Button, StatusMessage } from '../ui/primitives';
import type { StudioGraphClient } from './studioGraphClient';
import type { StudioGraphDefinition, StudioGraphRecord } from './studioGraphTypes';
import { GRAPH_NODE_LABELS, GRAPH_STATUS_LABELS } from './studioGraphLabels';
import { directorRunBranch, directorRunChoice, directorRunMatches, projectDirectorRun, type DirectorRunChoice } from './directorRunOverview';

export type DirectorRunReader = Partial<Pick<StudioGraphClient, 'runs' | 'getRun'>>;
type Props = { client: DirectorRunReader; definition: StudioGraphDefinition; base?: StudioGraphRecord; nodeId: string;
  identity: string; active: boolean; busy?: boolean; isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T>;
  onLocate?: (nodeId: string, graph: StudioGraphRecord) => boolean };
const labels: Record<string, string> = { ...GRAPH_STATUS_LABELS, PENDING: '待处理', WORKING: '处理中', SKIPPED: '已跳过' };
export function GraphDirectorRunOverview(props: Props) {
  const [choices, setChoices] = useState<{ token: object; rows: DirectorRunChoice[] }>(), [choice, setChoice] = useState('');
  const [preview, setPreview] = useState<{ token: object; revision: number; run: ReturnType<typeof projectDirectorRun> }>();
  const [working, setWorking] = useState(false), [error, setError] = useState(''), [denied, setDenied] = useState(false);
  const live = useRef(props); live.current = props;
  const alive = useRef(true), retired = useRef(false), request = useRef<AbortController>(), revision = useRef(0);
  const values = [props.client, props.definition, props.base, props.nodeId, props.identity, props.active, props.busy, props.isCurrent()];
  const authority = useRef({ values, token: {} });
  if (values.some((value, index) => !Object.is(value, authority.current.values[index]))) authority.current = { values, token: {} };
  const token = authority.current.token, renderedRevision = revision.current;
  const current = () => alive.current && !retired.current && token === authority.current.token && live.current.active && live.current.isCurrent() && !live.current.busy;
  const graph = props.base;
  const ready = !!graph && JSON.stringify(props.definition) === JSON.stringify(graph.definition) && directorRunBranch(graph.definition, props.nodeId).length > 0;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; request.current?.abort(); }; }, []);
  useLayoutEffect(() => {
    setChoices(undefined); setChoice(''); setPreview(undefined); setError(''); setWorking(false);
    return () => { request.current?.abort(); request.current = undefined; };
  }, [token]);
  const rows = choices?.token === token ? choices.rows : [];
  const visible = preview?.token === token && preview.revision === revision.current ? preview.run : undefined;
  async function inspect(list: boolean) {
    const source = props.client, selected = rows.find(row => row.id === choice);
    if (!current() || !ready || !graph || request.current || renderedRevision !== revision.current || !source.runs || !source.getRun || !list && !selected) return;
    const controller = new AbortController(), intent = ++revision.current;
    request.current = controller; setWorking(true); setError(''); setPreview(undefined);
    if (list) { setChoices(undefined); setChoice(''); }
    const valid = () => current() && request.current === controller && !controller.signal.aborted && intent === revision.current;
    try {
      if (list) {
        const result = await props.read(() => source.runs!(graph.id, controller.signal));
        if (valid()) setChoices({ token, rows: result.items.filter(run => directorRunMatches(run, graph)).map(directorRunChoice) });
      } else {
        const result = await props.read(() => source.getRun!(selected!.id, controller.signal));
        if (!valid()) return;
        if (result.id !== selected!.id || result.version < selected!.version) throw new Error('运行回执与明确选择不一致，未采用状态。');
        setChoices(previous => previous?.token === token ? { token, rows: previous.rows.map(row => row.id === result.id ? directorRunChoice(result) : row) } : previous);
        setPreview({ token, revision: intent, run: projectDirectorRun(result, graph, props.nodeId) });
      }
    } catch (reason) {
      if (!valid()) return;
      setChoices(undefined); setPreview(undefined); setChoice('');
      if (reason instanceof ApiError && [401, 403, 404].includes(reason.status)) { retired.current = true; setDenied(true); }
      setError(apiErrorView(reason, '导演分支运行读取失败，请到原运行面板核对。').message);
    } finally { if (request.current === controller) { request.current = undefined; if (alive.current) setWorking(false); } }
  }
  if (!props.active || !props.isCurrent()) return null;
  if (denied) return <StatusMessage tone="warning">导演分支运行当前不可读取，先前状态已关闭。请重新核对权限与原运行。</StatusMessage>;
  return <section aria-label={`导演分支运行 ${props.nodeId}`}>
    <h4>已保存导演分支运行 · 只读</h4>
    <p>按已保存图追踪导演及其下游，包含共享／禁用节点；结构连接不证明内容派生或审核。读取和定位不保存、不执行或重试任务。</p>
    {!ready && <StatusMessage>请先保存或处理当前图草稿，再核对该导演分支的已保存版本。</StatusMessage>}
    {!props.client.runs || !props.client.getRun ? <StatusMessage>当前入口未提供原运行查询。</StatusMessage> : <>
      <Button disabled={!ready || props.busy || working} onClick={() => void inspect(true)}>读取导演分支运行目录</Button>
      <label>导演分支运行记录<select aria-label={`导演分支运行记录 ${props.nodeId}`} disabled={!ready || props.busy || working} value={choice} onChange={event => {
        if (!current() || request.current || renderedRevision !== revision.current) return;
        revision.current++; setChoice(event.target.value); setPreview(undefined); setError('');
      }}><option value="">明确选择运行</option>{rows.map(row => <option key={row.id} value={row.id}>{row.id} · {labels[row.status]} · 回执 v{row.version}</option>)}</select></label>
      <Button disabled={!ready || props.busy || working || !rows.some(row => row.id === choice)} onClick={() => void inspect(false)}>读取／刷新所选导演分支运行</Button>
    </>}
    {choices?.token === token && <p>本次原目录中匹配图 {graph?.id} · v{graph?.version} 的运行 {rows.length} 条；目录不代表完整历史，未自动选择或读取任一运行。</p>}
    {working && <StatusMessage>正在读取原运行状态…</StatusMessage>}{error && <StatusMessage tone="error">{error}</StatusMessage>}
    {visible && <>
      <p>运行 {visible.id} · 回执 v{visible.version} · {labels[visible.status]}；最近回执 {visible.updatedAt}。状态来自本次读取，不自动轮询。</p>
      {visible.stale && <StatusMessage tone="warning">原运行标记来源已过期。下方仅为记录状态，不代表当前可以执行。</StatusMessage>}
      <p>本分支返回状态 {visible.rows.filter(row => row.status).length} / {visible.rows.length}；成功 {visible.rows.filter(row => row.status === 'SUCCEEDED').length}，失败 {visible.rows.filter(row => row.status === 'FAILED').length}。未返回状态不视为完成。</p>
      <ul>{visible.rows.map(row => <li key={row.id}>{GRAPH_NODE_LABELS[row.kind]} · {row.id} · {row.status ? labels[row.status] : '未返回状态'}{!row.enabled && ' · 图中已禁用'}{row.id === visible.currentNode && ' · 原运行当前节点'}
        {props.onLocate && <Button disabled={!ready || props.busy || working} aria-label={`定位导演分支节点 ${row.id}`} onClick={() => {
          if (current() && !request.current && ready && preview?.token === token && preview.revision === revision.current && visible.rows.some(node => node.id === row.id) && graph) live.current.onLocate?.(row.id, graph);
        }}>定位节点</Button>}</li>)}</ul>
    </>}
  </section>;
}
