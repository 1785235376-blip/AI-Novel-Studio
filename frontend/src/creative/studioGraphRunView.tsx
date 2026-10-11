import { Badge, Button, StatusMessage } from '../ui/primitives';
import { GRAPH_STATUS_LABELS } from './studioGraphLabels';
import { GraphModelExecutionPanel } from './GraphModelExecutionPanel';
import { StudioGraphMediaExecutionPanel } from './StudioGraphMediaExecutionPanel';
import type { StudioGraphRunController, StudioGraphRunPanelProps } from './useStudioGraphRunController';

/** Rendering consumes the controller's grants; it never owns execution or digest checks. */
export function studioGraphRunView(controller: StudioGraphRunController, props: StudioGraphRunPanelProps) {
  const { client, graph, dirty, canMutate, canReview, modelExecutionEnabled = false } = props;
  const { preflight, reviewed, outputReviewed, runs, selected, error, notice, loading, uncertain, note,
    creationUncertain, locked, modelLocked, canReadRuns, terminal, current, inspect, listRuns, openRun, createRun,
    action, canAction, reviewPreflight, reviewOutput, changeNote, modelAction, mediaAction, modelUnavailable, readModel } = controller;
  return <section className="studio-graph-run" aria-label="创作图运行与审核">
    <h3>节点运行</h3><p>先核对保存图与节点范围。前置节点使用原工作流；模型和媒体节点分别预览、确认与执行。媒体 schema 3 核对原资产版本与内容，审核后才供下游采用。</p>
    {!graph && <p>先保存创作图，再核对选中节点的运行范围。</p>}{dirty && <StatusMessage tone="warning">创作图有未保存修改，请先保存后运行。</StatusMessage>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage>{notice}</StatusMessage>}
    <Button disabled={!graph || locked || loading} onClick={() => void inspect()}>核对运行范围</Button><Button disabled={!canReadRuns} onClick={() => void listRuns()}>读取运行记录</Button>
    {loading && <StatusMessage>正在读取原工作流信息…</StatusMessage>}
    {preflight && <section aria-label="运行预检"><p>选中范围 {preflight.selected_closure.length} 个节点；顺序：{preflight.execution_order.join(' → ') || '无可执行节点'}</p><p>未选择目标时核对整个图；不相连的组件不会被自动连线。</p>{preflight.issues.map((issue, index) => <StatusMessage key={`${issue.code}:${issue.node_id}:${index}`} tone="warning">{issue.code}{issue.node_id ? ` · ${issue.node_id}` : ''}</StatusMessage>)}<label><input type="checkbox" checked={reviewed} disabled={locked || !preflight.executable || !canMutate} onChange={event => reviewPreflight(event.target.checked)} />已核对当前图版本、节点范围与本地处理边界</label><Button disabled={locked || !reviewed || !preflight.executable || !canMutate} onClick={() => void createRun()}>{creationUncertain ? '使用同一请求重试创建运行' : '创建本地运行'}</Button></section>}
    {!!runs.length && <label>已保存运行<select aria-label="已保存运行" disabled={!canReadRuns} value={selected?.id || ''} onChange={event => { if (event.target.value) void openRun(event.target.value); }}><option value="">选择运行记录</option>{runs.map(row => <option key={row.id} value={row.id}>{row.id} · {GRAPH_STATUS_LABELS[row.status] || row.status} · v{row.version}</option>)}</select></label>}
    {selected && <section aria-label="当前创作图运行"><p>运行 {selected.id} · v{selected.version} · 图 v{selected.graph_version}</p><Badge>{GRAPH_STATUS_LABELS[selected.status] || selected.status}</Badge><p>缓存命中 {selected.cache.hits} / 未命中 {selected.cache.misses}；仅同图版本的已审核本地结果。{(selected.model_runtime || selected.media_runtime) && '模型及媒体输出不复用缓存。'}</p>{selected.media_runtime ? <p>媒体调用与结果以逐节点原任务回执为准，审核结果见下方面板。</p> : selected.model_runtime ? <p>模型调用：{selected.model_called ? '已调用' : '调用记录尚待核对'} · 云端调用：0 · 应用到正文：否</p> : <p>模型调用：无 · 外部调用：0 · 应用到正文：否</p>}<p>运行时限 {selected.timeout_seconds} 秒 · 截止 {selected.deadline_at}。暂停、恢复与审核不会重新计时。</p>
      {selected.stale && <StatusMessage tone="warning">来源图已经变化，运行输出不可继续采用，请重新核对当前图。</StatusMessage>}
      {uncertain && <StatusMessage tone="warning">版本或回执不确定。请先重新读取运行，不会自动重复动作。</StatusMessage>}
      <Button disabled={!canReadRuns} onClick={() => void openRun(selected.id)}>重新读取当前运行</Button>
      <ul>{Object.entries(selected.node_states).map(([id, state]) => <li key={id}>{id} · {GRAPH_STATUS_LABELS[state.status] || state.status}{state.error && <span> · {state.error.code}</span>}
        {state.output?.reviewed_draft && <details><summary>此节点已批准的文字输出</summary><pre>{state.output.reviewed_draft.text}</pre>{state.output.reviewed_draft.direction && <p>{state.output.reviewed_draft.direction.note}</p>}<p>这是原人工审核节点的回执。媒体输入仍须核对对应私有文字档案与原任务，不能据此认定整张图已验收。</p></details>}
      </li>)}</ul>
      <label>运行备注<input maxLength={1000} disabled={locked} value={note} onChange={event => changeNote(event.target.value)} /></label>
      {!terminal && <div className="studio-graph-actions"><Button disabled={!canAction('execute')} onClick={() => void action('execute')}>{selected.model_runtime ? '执行前置本地节点' : '执行本地节点'}</Button><Button disabled={!canAction('pause')} onClick={() => void action('pause')}>暂停运行</Button><Button disabled={!canAction('resume')} onClick={() => void action('resume')}>恢复运行</Button><Button variant="danger" disabled={!canAction('cancel')} onClick={() => void action('cancel')}>取消运行</Button></div>}
      {selected.review && !selected.stale && <section aria-label="节点输出审核"><h4>待审核输出 · {selected.review.node_id}</h4><p>来源：{selected.review.draft.origin === 'MODEL_PROPOSAL' ? '模型提案（需人工审核）' : selected.review.draft.origin === 'MANUAL' ? '手工填写' : '作者输入'}</p><pre>{selected.review.draft.text}</pre>{selected.review.draft.direction && <p>导演备注：{selected.review.draft.direction.note}</p>}{selected.review.draft.plan && <ol>{selected.review.draft.plan.map(row => <li key={row.sequence}>{row.beat}</li>)}</ol>}<label><input type="checkbox" checked={outputReviewed} disabled={locked || !canReview || uncertain} onChange={event => reviewOutput(event.target.checked)} />已阅读本次输出并核对当前审核摘要</label><Button disabled={!canAction('approve')} onClick={() => void action('approve')}>批准节点输出</Button><Button disabled={!canAction('reject')} onClick={() => void action('reject')}>驳回节点输出</Button></section>}
    </section>}
    {modelExecutionEnabled && <GraphModelExecutionPanel key={selected?.id || 'unselected'} client={client} run={selected} locked={modelLocked} canMutate={canMutate} uncertain={uncertain} isCurrent={current} read={readModel} perform={modelAction} onUnavailable={modelUnavailable} />}
    {props.mediaExecutionEnabled && selected?.media_runtime && <StudioGraphMediaExecutionPanel key={selected.id} client={client} graph={graph} run={selected} locked={modelLocked} canMutate={canMutate} canReview={canReview} uncertain={uncertain} isCurrent={current} read={readModel} perform={mediaAction} onUnavailable={modelUnavailable} onDirtyChange={props.onDirtyChange} />}
  </section>;
}
