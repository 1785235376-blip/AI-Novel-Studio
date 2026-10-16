import { useEffect, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { ErrorMessage } from './shared';
import { useReviewAction } from './styleReviewClient';
import type { multilingualEditionsClient, LanguageEdition, EditionSegment, TranslationMemoryCandidate, TranslationRevision } from './multilingualEditionsClient';
type Props = { api: ReturnType<typeof multilingualEditionsClient>; edition: LanguageEdition; segment: EditionSegment; blocked: boolean; perform: (operation: () => Promise<LanguageEdition>, message: string) => void };
export function TranslationMemoryPanel({ api, edition, segment, blocked, perform }: Props) {
  const action = useReviewAction(); const blockedRef = useRef(blocked); blockedRef.current = blocked;
  const [candidates, setCandidates] = useState<TranslationMemoryCandidate[]>(), [history, setHistory] = useState<TranslationRevision[]>();
  const [truncated, setTruncated] = useState(false);
  useEffect(() => { if (blocked) { setCandidates(undefined); setHistory(undefined); } }, [blocked]);
  return <Panel title="翻译记忆与本段历史">
    <p>复用本项目、当前作者、相同语言对中已接受且来源仍有效的完全相同原文。候选只复制为草稿，仍须人工审核。风格不同会单独提示。</p>
    <div className="experimental-actions"><Button disabled={blocked || action.busy} onClick={() => void action.run(async current => { setCandidates(undefined); const result = await api.memory(edition, segment); if (current() && !blockedRef.current) { setCandidates(result.items); setTruncated(result.truncated); } })}>查找完全匹配翻译记忆</Button><Button disabled={blocked || action.busy} onClick={() => void action.run(async current => { setHistory(undefined); const result = await api.segmentHistory(edition, segment); if (current() && !blockedRef.current) { setHistory(result.items); setTruncated(result.truncated); } })}>读取本段译文历史</Button></div>
    {candidates && !candidates.length && <StatusMessage>没有当前可用的已审核完全匹配译文。</StatusMessage>}
    {candidates?.map(candidate => <article className="experimental-record" key={`${candidate.source_edition_id}:${candidate.source_segment_id}`}>
      <Badge>完全匹配 · 译本 v{candidate.source_edition_version} · 原稿 v{candidate.source_version}</Badge>
      <p>来源译本：{candidate.source_edition_id}</p><p className="multilingual-prose" lang={edition.target_language} dir={edition.direction}>{candidate.target_text}</p>
      {!candidate.style_matches && <StatusMessage tone="warning">两个译本的风格说明不同，请核对后再采用。</StatusMessage>}
      {candidate.issues.map((issue, index) => <StatusMessage key={index} tone="warning">{issue.code}：{issue.expected || issue.found || issue.term}</StatusMessage>)}
      <Button disabled={blocked || action.busy || !candidate.can_adopt} onClick={() => perform(() => api.adoptMemory(edition, segment, candidate), '翻译记忆已复制为本段草稿，原译本和原稿未变。')}>采用此记忆为待审草稿</Button>
    </article>)}
    {history && !history.length && <StatusMessage>当前来源版本下尚无可恢复的本段历史。</StatusMessage>}
    {history?.map(revision => <article className="experimental-record" key={revision.version}><Badge>语言版本 v{revision.version} · {revision.status}</Badge><p className="multilingual-prose" lang={edition.target_language} dir={edition.direction}>{revision.target_text || '（空译文）'}</p><Button disabled={blocked || action.busy} onClick={() => perform(() => api.restoreSegment(edition, segment, revision), '已创建新的译文草稿版本，旧历史保留，需重新审核。')}>恢复 v{revision.version} 为新草稿</Button></article>)}
    {truncated && <StatusMessage tone="warning">仅显示 100 条匹配或历史记录；翻译记忆最多检查最近 200 个同语言版本。</StatusMessage>}{!!action.error && <ErrorMessage error={action.error} />}
  </Panel>;
}
