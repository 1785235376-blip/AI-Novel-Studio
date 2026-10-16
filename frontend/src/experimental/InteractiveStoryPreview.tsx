import { useEffect, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { useAction } from './shared';
import type { interactiveStoryClient, InteractiveStory, StoryPlay } from './interactiveStoryClient';
export function InteractiveStoryPreview({ api, story, blocked }: { api: ReturnType<typeof interactiveStoryClient>; story: InteractiveStory; blocked: boolean }) {
  const [play, setPlay] = useState<StoryPlay>(); const alive = useRef(true), epoch = useRef(0); const action = useAction();
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  useEffect(() => { epoch.current++; setPlay(undefined); }, [story.id, story.version, blocked]);
  const advance = (choices: string[]) => void action.run(async () => { const ticket = ++epoch.current; const result = await api.play(story, choices); if (alive.current && ticket === epoch.current) setPlay(result); }, '预览状态已更新。');
  return <Panel title="有限互动预览"><p>每次选择由服务端重新校验来源和完整路径。最多 {story.spec?.max_steps} 步；只播放已保存的文本与选择，媒体引用暂不播放。</p>
    <Button disabled={blocked || action.busy || story.status === 'ARCHIVED'} onClick={() => advance([])}>从开头试玩</Button>
    {play && !blocked && <section aria-label="互动故事播放" aria-live="polite"><h3>{play.node.title}</h3>{play.character_name && <p>{play.character_name}</p>}<p className="interactive-story-prose">{play.node.dialogue}</p><Badge>{play.steps} / {play.max_steps} 步 · {play.status}</Badge>
      {play.status === 'ENDING' && <StatusMessage tone="success">结局：{play.node.ending}</StatusMessage>}
      {play.status === 'STEP_CAP_REACHED' && <StatusMessage tone="warning">已到步数上限。请从开头重试或修改已保存的路径。</StatusMessage>}
      {play.status === 'NO_EXIT' && <StatusMessage tone="warning">当前变量没有可用出口，请修正条件。</StatusMessage>}
      <div className="experimental-actions">{play.choices.map(c => <Button key={c.id} disabled={action.busy || !c.enabled || play.status !== 'PLAYING'} onClick={() => advance([...play.path, c.id])}>{c.label}</Button>)}</div>
      {Object.entries(play.variables).map(([name, value]) => <p key={name}>{name} = {String(value)}</p>)}
    </section>}{action.feedback}
  </Panel>;
}
