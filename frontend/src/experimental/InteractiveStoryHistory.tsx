import { useEffect, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { Details, ErrorMessage } from './shared';
import { useReviewAction } from './styleReviewClient';
import type { interactiveStoryClient, InteractiveStory, StoryRevision } from './interactiveStoryClient';
export function InteractiveStoryHistory({ api, story, blocked, perform }: { api: ReturnType<typeof interactiveStoryClient>; story: InteractiveStory; blocked: boolean; perform: (fn: () => Promise<InteractiveStory>, message: string) => void }) {
  const action = useReviewAction(); const [rows, setRows] = useState<StoryRevision[]>(); const [truncated, setTruncated] = useState(false);
  const blockedRef = useRef(blocked); blockedRef.current = blocked;
  useEffect(() => { if (blocked) setRows(undefined); }, [blocked]);
  return <Panel title="互动改编版本历史"><p>仅显示来源仍可访问、版本绑定仍有效的历史。恢复创建新的待审草稿，不修改原规划、正文或 Canon。</p><Button disabled={blocked || action.busy} onClick={() => void action.run(async current => { setRows(undefined); const result = await api.history(story); if (current() && !blockedRef.current) { setRows(result.items); setTruncated(result.truncated); } })}>读取互动改编历史</Button>
    {rows && !rows.length && <StatusMessage>当前来源下没有可恢复的历史版本。</StatusMessage>}{rows?.map(row => <article className="experimental-record" key={row.version}><Badge>v{row.version} · {row.status}</Badge><Details label={`互动历史 v${row.version}`} value={row.spec} /><Button disabled={blocked || action.busy || story.status === 'ARCHIVED'} onClick={() => perform(() => api.restoreRevision(story, row), '已创建历史内容的新待审版本。需要重新检查路径并批准。')}>恢复互动 v{row.version} 为待审草稿</Button></article>)}
    {truncated && <StatusMessage tone="warning">仅展示最近 100 条当前可访问的历史。</StatusMessage>}{!!action.error && <ErrorMessage error={action.error} />}
  </Panel>;
}
