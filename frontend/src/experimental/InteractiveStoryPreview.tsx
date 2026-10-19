import { useEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { useAction } from './shared';
import type { interactiveStoryClient, InteractiveStory, StoryPlay } from './interactiveStoryClient';
import { deriveStoryPath, type StoryPathIssue, type StoryPathStep, type StoryPathView } from './interactiveStoryPath';
export function InteractiveStoryPreview({ api, story, blocked }: { api: ReturnType<typeof interactiveStoryClient>; story: InteractiveStory; blocked: boolean }) {
  const [play, setPlay] = useState<StoryPlay>(); const alive = useRef(true), epoch = useRef(0); const action = useAction();
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  useEffect(() => { epoch.current++; setPlay(undefined); }, [story.id, story.version, blocked]);
  const advance = (choices: string[]) => void action.run(async () => { const ticket = ++epoch.current; const result = await api.play(story, choices); if (alive.current && ticket === epoch.current) setPlay(result); }, '预览状态已更新。');
  const path = useMemo(() => deriveStoryPath(story.spec, play), [story.spec, play]);
  return <Panel title="有限互动预览"><p>每次选择由服务端重新校验来源和完整路径。最多 {story.spec?.max_steps} 步；只播放已保存的文本与选择，媒体引用暂不播放。</p>
    <Button disabled={blocked || action.busy || story.status === 'ARCHIVED'} onClick={() => advance([])}>从开头试玩</Button>
    {play && !blocked && <section aria-label="互动故事播放" aria-live="polite"><h3>{play.node.title}</h3>{play.character_name && <p>{play.character_name}</p>}<p className="interactive-story-prose">{play.node.dialogue}</p><Badge>{play.steps} / {play.max_steps} 步 · {play.status}</Badge>
      {play.status === 'ENDING' && <StatusMessage tone="success">结局：{play.node.ending}</StatusMessage>}
      {play.status === 'STEP_CAP_REACHED' && <StatusMessage tone="warning">已到步数上限。请从开头重试或修改已保存的路径。</StatusMessage>}
      {play.status === 'NO_EXIT' && <StatusMessage tone="warning">当前变量没有可用出口，请修正条件。</StatusMessage>}
      <div className="experimental-actions">{play.choices.map(c => <Button key={c.id} disabled={action.busy || !c.enabled || play.status !== 'PLAYING'} onClick={() => advance([...play.path, c.id])}>{c.label}</Button>)}</div>
      {Object.entries(play.variables).map(([name, value]) => <p key={name}>{name} = {String(value)}</p>)}
    </section>}
    {!blocked && story.spec && <StoryPathSection path={path} play={play} />}
    {action.feedback}
  </Panel>;
}
function StoryPathSection({ path, play }: { path: StoryPathView; play?: StoryPlay }) {
  return <section aria-label="互动故事步骤路径"><h3>步骤路径</h3>
    <p>只读展示已保存的入口节点与现有播放选择记录；不重新计算变量或条件，也不推进故事。</p>
    {path.steps.length > 0 && <ol>{path.steps.map(step => <li key={step.step}><StoryPathStepView step={step} /></li>)}</ol>}
    {path.issues.map((issue, index) => <StatusMessage key={issue.code + ':' + index} tone={issue.code === 'NODE_TITLE_MISSING' || issue.code === 'CHOICE_LABEL_MISSING' ? 'info' : 'warning'}>{issue.message}</StatusMessage>)}
    <PathRunState path={path} play={play} />
  </section>;
}
function StoryPathStepView({ step }: { step: StoryPathStep }) {
  return <article className="experimental-record" aria-label={'路径步骤 ' + step.step}>
    <strong>步骤 {step.step}：{step.title ?? '未知节点标题'}</strong>
    <p>节点 ID：{step.nodeId || '（节点 ID 缺失）'}</p>
    {step.choice ? <><p>选择文案：{step.choice.label ?? '未知选择文案'}</p><p>Choice ID：{step.choice.id}</p></> : <p>选择：入口步骤（无前序选择）</p>}
    {step.issues.map((issue: StoryPathIssue, index: number) => <StatusMessage key={issue.code + ':' + index} tone="info">{issue.message}</StatusMessage>)}
  </article>;
}
function PathRunState({ path, play }: { path: StoryPathView; play?: StoryPlay }) {
  if (!play) return <StatusMessage>尚未开始试玩：从已保存入口节点开始展示，尚无已记录选择。</StatusMessage>;
  if (path.stoppedBy !== 'NONE') return null;
  if (play.status === 'ENDING') return <StatusMessage tone="success">路径已正常结束（故事结局）。</StatusMessage>;
  if (play.status === 'STEP_CAP_REACHED') return <StatusMessage tone="warning">已到达步数上限，路径在已记录选择处结束。</StatusMessage>;
  if (play.status === 'NO_EXIT') return <StatusMessage tone="warning">当前节点没有可用出口；这是现有播放状态，不是路径解析失败。</StatusMessage>;
  return <StatusMessage>{play.path.length > 0 ? '等待选择：当前节点正在等待下一次选择。' : '等待选择：当前路径尚未记录选择。'}</StatusMessage>;
}
