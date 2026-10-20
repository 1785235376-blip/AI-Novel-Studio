import { useEffect, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { Details, ErrorMessage } from './shared';
import { useReviewAction } from './styleReviewClient';
import { diffStorySpecs, describeStoryDiffRow, diffKindLabel, summarizeStoryDiff } from './interactiveStoryDiff';
import type { StoryDiffKind } from './interactiveStoryDiff';
import type { interactiveStoryClient, InteractiveStory, StoryRevision } from './interactiveStoryClient';

function diffTone(kind: StoryDiffKind): 'neutral' | 'info' | 'warning' | 'success' {
  if (kind === 'NODE_ADDED' || kind === 'CHOICE_ADDED' || kind === 'VARIABLE_ADDED') return 'info';
  if (kind === 'NODE_REMOVED' || kind === 'CHOICE_REMOVED' || kind === 'VARIABLE_REMOVED') return 'warning';
  if (kind === 'TITLE' || kind === 'ENTRY_NODE' || kind === 'MAX_STEPS' || kind === 'GRAPH_RECORDS') return 'info';
  return 'neutral';
}

/** History stays read-only until an explicit restore. The comparison is a pure
 * spec diff against the current saved revision and never interprets conditions. */
export function InteractiveStoryHistory({ api, story, blocked, perform }: { api: ReturnType<typeof interactiveStoryClient>; story: InteractiveStory; blocked: boolean; perform: (fn: () => Promise<InteractiveStory>, message: string) => void }) {
  const action = useReviewAction(); const [rows, setRows] = useState<StoryRevision[]>(); const [truncated, setTruncated] = useState(false);
  const [compareVersion, setCompareVersion] = useState<number>();
  const blockedRef = useRef(blocked); blockedRef.current = blocked;
  const storyRef = useRef(story); storyRef.current = story;
  useEffect(() => { setRows(undefined); setTruncated(false); setCompareVersion(undefined); }, [story.id, story.version]);
  useEffect(() => { if (blocked) { setRows(undefined); setCompareVersion(undefined); } }, [blocked]);
  const current = story.spec;
  const compared = compareVersion === undefined ? undefined : rows?.find(row => row.version === compareVersion);
  const diffRows = compared && current ? diffStorySpecs(compared.spec, current) : [];
  const summary = summarizeStoryDiff(diffRows);
  const load = () => {
    const requestedVersion = story.version;
    void action.run(async isCurrent => {
      setRows(undefined); setCompareVersion(undefined);
      const result = await api.history(story);
      if (isCurrent() && !blockedRef.current && storyRef.current.version === requestedVersion) {
        setRows(result.items); setTruncated(result.truncated);
      }
    });
  };
  return <Panel title="互动改编版本历史"><p>仅显示来源仍可访问、版本绑定仍有效的历史。恢复创建新的待审草稿，不修改原规划、正文或 Canon。历史比较是已保存版本之间的纯内容差异，不运行时条件解释。</p>
    <div className="experimental-actions"><Button disabled={blocked || action.busy} onClick={load}>读取互动改编历史</Button>{rows && <Button disabled={action.busy} onClick={load}>刷新互动历史</Button>}</div>
    {rows && !rows.length && <StatusMessage>当前来源下没有可恢复的历史版本。</StatusMessage>}
    {rows?.map(row => <article className="experimental-record" key={row.version}><Badge>v{row.version} · {row.status}</Badge><Details label={`互动历史 v${row.version}`} value={row.spec} />
      <div className="experimental-actions"><Button disabled={blocked || action.busy || !current} onClick={() => setCompareVersion(row.version)} aria-pressed={compareVersion === row.version}>比较互动 v{row.version} 与当前</Button>
        <Button disabled={blocked || action.busy || story.status === 'ARCHIVED'} onClick={() => perform(() => api.restoreRevision(story, row), '已创建历史内容的新待审版本。需要重新检查路径并批准。')}>恢复互动 v{row.version} 为待审草稿</Button></div>
    </article>)}
    {compared && <section aria-label={`历史 v${compared.version} 与当前版本差异`}><h3>历史 v{compared.version} → 当前 v{story.version}</h3>
      {!current ? <StatusMessage tone="warning">当前版本内容不可用，无法比较。</StatusMessage> : <>
        <StatusMessage tone={summary.identical ? 'success' : 'info'}>{summary.identical ? '内容与当前已保存版本一致；可能只有审核状态或版本号不同。' : `共 ${summary.total} 处内容差异：故事级 ${summary.story} · 节点 ${summary.nodes} · 选择 ${summary.choices} · 变量 ${summary.variables}。`}</StatusMessage>
        {!summary.identical && <ul className="interactive-story-diff">{diffRows.map(row => <li key={row.key}><Badge tone={diffTone(row.kind)}>{diffKindLabel(row.kind)}</Badge><span>{describeStoryDiffRow(row)}</span></li>)}</ul>}
        <p>差异只比较已保存的历史版本与当前已保存版本，不包含编辑区未保存输入。恢复前不会写入任何内容。</p>
        <Button onClick={() => setCompareVersion(undefined)}>关闭历史比较</Button>
      </>}
    </section>}
    {truncated && <StatusMessage tone="warning">仅展示最近 100 条当前可访问的历史。</StatusMessage>}{!!action.error && <ErrorMessage error={action.error} />}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
  </Panel>;
}
