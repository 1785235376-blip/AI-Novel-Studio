import { useState } from 'react';
import type { Chapter } from '../api';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { type ExperimentalClient, type Row, type Rows, segment } from './api';
import { Details, Field, Form, RecordStatus, Refresh, ResourceState, useAction, useResource } from './shared';

export function TeamsPanel({ client, chapter }: { client: ExperimentalClient; chapter?: Chapter }) {
  const resource = useResource(async signal => { const [catalog, runs] = await Promise.all([client.get('/teams/catalog', signal), client.get<Rows>('/teams/runs', signal)]); return { ...catalog, runs: runs.items }; }, [client]);
  const action = useAction(resource.reload);
  const [recipe, setRecipe] = useState('outline_chapter_editor'), [instruction, setInstruction] = useState(''), [includeChapter, setIncludeChapter] = useState(!!chapter), [history, setHistory] = useState<any>();
  const transition = (row: Row, operation: string) => action.run(() => client.post(`/teams/runs/${segment(row.id)}/${operation}`, { expected_version: row.version }), '团队任务已更新');
  const busy = action.busy || resource.loading;
  return <Panel title="创作团队与工作流 Recipe" actions={<Refresh reload={resource.reload} busy={busy} />}>
    <StatusMessage>本地确定性工作流验证。输出保留为 Proposal / Artifact，Human Approve 不会自动覆盖正文或 Canon。</StatusMessage>{action.feedback}<ResourceState loading={resource.loading} error={resource.error} />
    <Details label="八类角色模板与权限" value={resource.data?.roles} />
    <Form onSubmit={() => action.run(() => client.post('/teams/runs', { recipe_id: recipe, instruction, chapter_ids: includeChapter && chapter ? [chapter.id] : [] }), '团队任务已创建')}>
      <Field label="团队 Recipe"><select value={recipe} onChange={event => setRecipe(event.target.value)}>{resource.data?.recipes?.map((row: Row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field>
      <Field label="团队任务指令"><textarea required={!includeChapter || !chapter} value={instruction} onChange={event => setInstruction(event.target.value)} /></Field>
      {chapter && <label className="experimental-check"><input type="checkbox" checked={includeChapter} onChange={event => setIncludeChapter(event.target.checked)} />使用当前章节及其来源版本</label>}
      <Button type="submit" disabled={busy || (!instruction.trim() && !(includeChapter && chapter))}>创建团队任务</Button>
    </Form>
    <div className="experimental-list">{resource.data?.runs?.map((row: Row) => <article className="experimental-record" key={row.id} aria-label={`团队任务 ${row.recipe_id}`}><h3>{row.definition_snapshot?.name || row.recipe_id}</h3><RecordStatus row={row} /><Details label="DAG 节点与审核产物" value={{ node_states: row.node_states, artifacts: row.artifacts, scope: row.scope, sources: row.sources }} /><div className="experimental-actions">
      {['RUNNING', 'QUEUED'].includes(row.status || '') && <Button disabled={busy || row.stale} onClick={() => transition(row, 'execute')}>执行本地 Recipe</Button>}{['RUNNING', 'WAITING_APPROVAL'].includes(row.status || '') && <Button disabled={busy} onClick={() => transition(row, 'pause')}>暂停团队任务</Button>}{row.status === 'PAUSED' && <Button disabled={busy || row.stale} onClick={() => transition(row, 'resume')}>恢复团队任务</Button>}{!['SUCCEEDED', 'FAILED', 'CANCELLED', 'REJECTED'].includes(row.status || '') && <Button disabled={busy} onClick={() => transition(row, 'cancel')}>取消团队任务</Button>}{['FAILED', 'CANCELLED'].includes(row.status || '') && <Button disabled={busy || row.stale} onClick={() => transition(row, 'retry')}>重试团队任务</Button>}{row.status === 'RUNNING' && <Button disabled={busy} onClick={() => transition(row, 'recover')}>检查团队中断恢复</Button>}
      {row.status === 'WAITING_APPROVAL' && <><Button disabled={busy || row.stale} onClick={() => transition(row, 'review/approve')}>人工批准团队产物</Button><Button disabled={busy} onClick={() => transition(row, 'review/reject')}>驳回团队产物</Button></>}{['REJECTED', 'SUCCEEDED'].includes(row.status || '') && <Button disabled={busy} onClick={() => transition(row, 'review/reopen')}>重开团队审核</Button>}<Button disabled={busy} onClick={() => action.run(async () => setHistory(await client.get(`/teams/runs/${segment(row.id)}/history`)), '团队历史已读取')}>团队执行历史</Button>
    </div></article>)}</div>{history && <Details label="团队执行历史记录" value={history} />}
  </Panel>;
}
