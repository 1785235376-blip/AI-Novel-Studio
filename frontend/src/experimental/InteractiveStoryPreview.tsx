import { useLayoutEffect, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { useAction } from './shared';
import type { interactiveStoryClient, InteractiveStory, StoryPlay } from './interactiveStoryClient';
export function InteractiveStoryPreview({ api, story, blocked }: { api: ReturnType<typeof interactiveStoryClient>; story: InteractiveStory; blocked: boolean }) {
  const [receipt, setReceipt] = useState<{ owner:object; ticket:number; value:StoryPlay }>();
  const alive = useRef(true), epoch = useRef(0), actionOwner = useRef<object>(); const action = useAction();
  const values=[api,story,blocked], owner=useRef({values,token:{}});
  if(values.some((value,index)=>value!==owner.current.values[index]))owner.current={values,token:{}};
  const token=owner.current.token,renderTicket=epoch.current;
  const live=useRef({blocked,story});live.current={blocked,story};
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  const ownerCurrent=()=>alive.current&&owner.current.token===token&&!live.current.blocked
    &&!live.current.story.stale&&!live.current.story.content_withheld&&live.current.story.status!=='ARCHIVED';
  const play=receipt&&receipt.owner===token&&receipt.ticket===epoch.current&&ownerCurrent()?receipt.value:undefined;
  const advance = (choices: string[]) => {
    if(!ownerCurrent()||renderTicket!==epoch.current||action.busy)return;
    actionOwner.current = token;
    void action.run(async () => {
      if(!ownerCurrent()||renderTicket!==epoch.current)return;
      const ticket = ++epoch.current;
      const result = await api.play(story, [...choices]);
      if (ownerCurrent() && ticket === epoch.current) setReceipt({owner:token,ticket,value:result});
    }, '预览状态已更新。');
  };
  const unavailable=blocked||story.stale||story.content_withheld||story.status==='ARCHIVED';
  return <Panel title="有限互动预览"><p>每次选择由服务端重新校验来源和完整路径。最多 {story.spec?.max_steps} 步；只播放已保存的文本与选择，媒体引用暂不播放。</p>
    <Button disabled={unavailable || action.busy} onClick={() => advance([])}>从开头试玩</Button>
    {play && <section aria-label="互动故事播放" aria-live="polite"><h3>{play.node.title}</h3>{play.character_name && <p>{play.character_name}</p>}<p className="interactive-story-prose">{play.node.dialogue}</p><Badge>{play.steps} / {play.max_steps} 步 · {play.status}</Badge>
      {play.status === 'ENDING' && <StatusMessage tone="success">结局：{play.node.ending}</StatusMessage>}
      {play.status === 'STEP_CAP_REACHED' && <StatusMessage tone="warning">已到步数上限。请从开头重试或修改已保存的路径。</StatusMessage>}
      {play.status === 'NO_EXIT' && <StatusMessage tone="warning">当前变量没有可用出口，请修正条件。</StatusMessage>}
      <div className="experimental-actions">{play.choices.map(c => <Button key={c.id} disabled={action.busy || !c.enabled || play.status !== 'PLAYING'} onClick={() => advance([...play.path, c.id])}>{c.label}</Button>)}</div>
      {play.path.length>0&&<section aria-label="互动试玩路径"><p>已选择 {play.path.length} 步。回退会将缩短后的完整路径交回原服务，重新计算变量和条件；不恢复客户端缓存，也不修改故事。</p>
        <ol>{play.path.map((id,index)=><li key={`${index}:${id}`}>第 {index+1} 步 · {id}</li>)}</ol>
        <Button disabled={action.busy} onClick={()=>advance(play.path.slice(0,-1))}>回退一步并重新核验</Button>
      </section>}
      {Object.entries(play.variables).map(([name, value]) => <p key={name}>{name} = {String(value)}</p>)}
    </section>}{actionOwner.current===token&&action.feedback}
  </Panel>;
}
