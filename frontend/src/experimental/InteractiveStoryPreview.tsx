import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { useAction } from './shared';
import type { interactiveStoryClient, InteractiveStory, StoryPlay } from './interactiveStoryClient';
import { analysisSummary, analysisWarningRows, choiceOverview, describePlayPath, endingRows, findUniqueNode, issueCodeCounts, playStatusNote, variableValueRows } from './interactiveStoryPlayback';

/** Server-authoritative play workbench. Every action sends the full choice path
 * back to the service; the client never evaluates conditions or assignments.
 * Reachable endings come only from the bounded analysis witness list. */
export function InteractiveStoryPreview({ api, story, blocked, onLocateNode }: { api: ReturnType<typeof interactiveStoryClient>; story: InteractiveStory; blocked: boolean; onLocateNode?: (nodeId: string) => void }) {
  const [receipt, setReceipt] = useState<{ owner: object; ticket: number; value: StoryPlay }>();
  const [explored, setExplored] = useState<Record<string, boolean>>({});
  const [failure, setFailure] = useState<{ code: string }>();
  const alive = useRef(true), epoch = useRef(0), actionOwner = useRef<object>(); const action = useAction();
  const values = [api, story, blocked], owner = useRef({ values, token: {} });
  if (values.some((value, index) => value !== owner.current.values[index])) owner.current = { values, token: {} };
  const token = owner.current.token, renderTicket = epoch.current;
  const live = useRef({ blocked, story }); live.current = { blocked, story };
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  useEffect(() => { setExplored({}); setFailure(undefined); }, [story.id, story.version]);
  const ownerCurrent = () => alive.current && owner.current.token === token && !live.current.blocked
    && !live.current.story.stale && !live.current.story.content_withheld && live.current.story.status !== 'ARCHIVED';
  const play = receipt && receipt.owner === token && receipt.ticket === epoch.current && ownerCurrent() ? receipt.value : undefined;
  const advance = (choices: string[]) => {
    if (!ownerCurrent() || renderTicket !== epoch.current || action.busy) return;
    actionOwner.current = token; setFailure(undefined);
    void action.run(async () => {
      if (!ownerCurrent() || renderTicket !== epoch.current) return;
      const ticket = ++epoch.current;
      try {
        const result = await api.play(story, [...choices]);
        if (ownerCurrent() && ticket === epoch.current) {
          setReceipt({ owner: token, ticket, value: result });
          // Exploration is a session-only UI record. Nothing is written back to the story.
          if (result.status === 'ENDING') setExplored(old => old[result.node.node_id] ? old : { ...old, [result.node.node_id]: true });
        }
      } catch (value) {
        if (ownerCurrent() && ticket === epoch.current) setFailure({ code: value instanceof ApiError ? value.problem.code : 'PLAYBACK_FAILED' });
        throw value;
      }
    }, '预览状态已更新。');
  };
  const analysis = story.analysis, summary = analysisSummary(analysis), endings = endingRows(analysis, explored, story.spec);
  const warnings = analysisWarningRows(story.spec, analysis), issueCounts = issueCodeCounts(analysis);
  const choices = play ? choiceOverview(story.spec, play) : [], disabledChoices = choices.filter(choice => !choice.enabled);
  const pathSteps = play ? describePlayPath(story.spec, play.path) : [], variables = play ? variableValueRows(story.spec, play) : [];
  const unavailable = blocked || story.stale || story.content_withheld || story.status === 'ARCHIVED';
  const canLocate = (nodeId: string | null | undefined) => !!onLocateNode && !!findUniqueNode(story.spec, nodeId);
  const note = play ? playStatusNote(play) : undefined;
  return <Panel title="试玩工作台与结局导航"><p>每次选择、回退与重开都由服务端按完整路径重新校验来源、变量与条件；客户端不解释条件，也不修改故事。只播放已保存的文本与选择，媒体引用暂不播放。最多 {story.spec?.max_steps ?? '—'} 步。</p>
    <div className="experimental-actions"><Badge tone={story.status === 'APPROVED' ? 'success' : 'neutral'}>{story.status} · v{story.version}</Badge>{analysis && !summary.canReview && <Badge tone="warning">路径分析未通过，导出被阻止</Badge>}<Badge tone="info">服务端权威</Badge></div>
    {blocked && <StatusMessage tone="warning">有未保存输入或操作进行中：试玩只读取已保存版本，不会把输入当成故事状态。</StatusMessage>}
    <div className="experimental-actions"><Button disabled={unavailable || action.busy} onClick={() => advance([])}>从开头试玩</Button></div>
    {analysis && <section aria-label="可达结局导航"><h3>可达结局与见证路径</h3>
      <StatusMessage tone={summary.canReview ? 'success' : 'warning'}>已检查 {summary.statesChecked} 个状态；可达结局 {summary.endings} 个；路径问题 {summary.issues} 个；提醒 {summary.warnings} 个。{summary.analysisComplete ? '有界状态搜索完成。' : '达到分析边界或步数上限，不能据此批准导出。'}</StatusMessage>
      {!endings.length && <p>没有可达结局的见证路径；请先在编辑区「路径与变量检查」修复路径问题。</p>}
      {endings.map(ending => <article className="experimental-record" key={ending.key}>
        <p><Badge tone={ending.explored ? 'success' : 'neutral'}>{ending.explored ? '已探索' : '未探索'}</Badge> 结局：{ending.ending} · {ending.choices.length} 次选择 · 节点 {ending.nodeTitle || ending.nodeId}{ending.nodeTitle ? '（' + ending.nodeId + '）' : ''}</p>
        <div className="experimental-actions"><Button disabled={unavailable || action.busy} onClick={() => advance([...ending.choices])}>从见证路径试玩结局：{ending.ending}（{ending.nodeId}）</Button>
          {canLocate(ending.nodeId) && <Button disabled={unavailable} onClick={() => onLocateNode!(ending.nodeId)}>定位结局节点 {ending.nodeId}</Button>}</div>
      </article>)}
      <p>已探索只记录在本次会话内，不写回故事。从见证路径试玩同样把整条路径交回服务端重算。</p>
    </section>}
    {!!warnings.length && <section aria-label="路径提醒"><h3>路径提醒（{warnings.length}）</h3>{warnings.map(warning => <p key={warning.key}>{warning.label}：{warning.nodeTitle ? '节点 ' + warning.nodeTitle + '（' + (warning.nodeId ?? '') + '）' : warning.nodeId ? '节点 ' + warning.nodeId : '全局'} — {warning.explanation}</p>)}</section>}
    {!!issueCounts.length && <section aria-label="路径问题概览"><h3>路径问题概览（{summary.issues}）</h3>{issueCounts.map(issue => <p key={issue.code}>{issue.label}（{issue.code}）× {issue.count}</p>)}<p>定位与修复入口在编辑区「路径与变量检查」；试玩不会绕过这些问题。</p></section>}
    {play && <section aria-label="互动故事播放" aria-live="polite"><h3>{play.node.title}</h3>
      {play.character_name && <p>角色：{play.character_name}</p>}
      <p className="interactive-story-prose">{play.node.dialogue}</p>
      <div className="experimental-actions"><Badge>{play.steps} / {play.max_steps} 步 · {play.status}</Badge><Badge tone="neutral">当前节点 {play.node.node_id}</Badge><Badge tone="info">来源 {story.status} · v{story.version}</Badge></div>
      {play.status === 'ENDING' && <StatusMessage tone="success">结局：{play.node.ending}</StatusMessage>}
      {play.status === 'STEP_CAP_REACHED' && <StatusMessage tone="warning">已到步数上限。请从开头重试或修改已保存的路径。</StatusMessage>}
      {play.status === 'NO_EXIT' && <StatusMessage tone="warning">当前变量没有可用出口，请修正条件。</StatusMessage>}
      {note && <StatusMessage tone={note.tone}>{note.text}</StatusMessage>}
      <h4>全部选项（{choices.length}）</h4>
      <div className="experimental-actions">{choices.map(choice => <Button key={choice.id} title={choice.reason} disabled={!choice.enabled || action.busy || play.status !== 'PLAYING'} onClick={() => advance([...play.path, choice.id])}>{choice.label}</Button>)}</div>
      {!!disabledChoices.length && <section aria-label="不可选选项原因"><h4>不可选选项</h4><ul>{disabledChoices.map(choice => <li key={choice.id}>{choice.label}：{choice.reason}</li>)}</ul><p>原因来自服务端判定；这里只显示作者编写的条件文本，不进行客户端求值。</p></section>}
      <h4>变量值</h4>{variables.map(variable => <p key={variable.name}><span>{variable.name} = {variable.display}</span>{variable.type ? <span> · {variable.type}{variable.initial === undefined ? '' : ' · 初始 ' + String(variable.initial)}</span> : null}</p>)}
      {play.path.length > 0 && <section aria-label="互动试玩路径"><p>已选择 {play.path.length} 步。回退会将缩短后的完整路径交回原服务，重新计算变量和条件；不恢复客户端缓存，也不修改故事。</p>
        <ol>{pathSteps.map((step, index) => <li key={index + ':' + step.choiceId}>第 {index + 1} 步 · {step.label}（{step.choiceId}）{step.targetTitle ? ' → ' + step.targetTitle : ''}{step.resolved ? '' : ' · 无法在已保存版本中解析'}</li>)}</ol>
        <Button disabled={action.busy} onClick={() => advance(play.path.slice(0, -1))}>回退一步并重新核验</Button>
      </section>}
      {canLocate(play.node.node_id) && <div className="experimental-actions"><Button disabled={unavailable} onClick={() => onLocateNode!(play.node.node_id)}>定位回编辑节点 {play.node.title}</Button></div>}
    </section>}
    {failure && <StatusMessage tone="error">试玩失败：{failure.code}。{play ? '上方仍显示上一次成功返回，不代表本次操作成功。' : '请从开头重试；客户端不会自行解释条件。'}</StatusMessage>}
    {actionOwner.current === token && action.feedback}
  </Panel>;
}
