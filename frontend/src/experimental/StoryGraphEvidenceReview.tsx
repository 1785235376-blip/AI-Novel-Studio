import { useEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { type ExperimentalClient, type Row, segment } from './api';
import { ResourceState, useResource } from './shared';

export type StoryEvidence = { record_id: string; record_version: number; chapter_id: string; source_versions: Record<string, { version: number; digest: string }> };
const object = (value: unknown): value is Record<string, any> => !!value && typeof value === 'object' && !Array.isArray(value);
const text = (value: unknown, max = 160): value is string => typeof value === 'string' && !!value.trim() && value.length <= max;
const version = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) > 0;
const nodeKinds = ['CHARACTER', 'LOCATION', 'CHAPTER', 'SCENE', 'ORGANIZATION', 'EVENT', 'RULE', 'ITEM', 'OBJECT', 'SECRET', 'FORESHADOWING'];
const relations = ['LOCATED_AT', 'MEMBER_OF', 'OWNS', 'ALLIED_WITH', 'OPPOSES', 'CAUSES', 'PRECEDES', 'REVEALS', 'FORESHADOWS', 'CONTRADICTS', 'ABOUT', 'KNOWS', 'BELIEVES', 'BELONGS_TO', 'HATES', 'TRUSTS', 'RELATED_TO', 'APPEARS_IN'];
export function validStoryEvidence(value: unknown): value is StoryEvidence {
  if (!object(value) || !text(value.record_id) || !version(value.record_version) || !text(value.chapter_id) || !object(value.source_versions)) return false;
  const keys = Object.keys(value.source_versions);
  return keys.includes(value.chapter_id) && keys.length > 0 && keys.length <= 100 && keys.every(key => text(key, 512) && object(value.source_versions[key]) && version(value.source_versions[key].version) && text(value.source_versions[key].digest, 256));
}
export function matchesStoryEvidence(row: Row, evidence: StoryEvidence): boolean {
  if (!validStoryEvidence(evidence) || !object(row) || row.id !== evidence.record_id || row.version !== evidence.record_version || row.chapter_id !== evidence.chapter_id || row.stale !== false || !object(row.data) || !object(row.sources)) return false;
  if (row.kind !== 'STORY_RELATION' || !text(row.title, 240) || !text(row.data.statement, 8000) || !relations.includes(row.data.relation) || !['WORLD_FACT', 'CHARACTER_BELIEF', 'RESEARCH', 'SPECULATION'].includes(row.data.layer) || !['subject', 'object'].every(key => object(row.data[key]) && nodeKinds.includes(row.data[key].kind) && text(row.data[key].id))) return false;
  if (row.event_order !== undefined && (!Number.isSafeInteger(row.event_order) || row.event_order < 0 || row.event_order > 1000000)) return false;
  if (['world_time', 'valid_from', 'valid_to'].some(key => row.data[key] !== undefined && row.data[key] !== null && !Number.isSafeInteger(row.data[key]))) return false;
  if (typeof row.data.valid_from === 'number' && typeof row.data.valid_to === 'number' && row.data.valid_to <= row.data.valid_from) return false;
  if (row.data.calendar !== undefined && !text(row.data.calendar, 80)) return false;
  if (['scene_id', 'until_chapter_id', 'observer_id'].some(key => row.data[key] !== undefined && row.data[key] !== null && (typeof row.data[key] !== 'string' || row.data[key].length > 160))) return false;
  if (row.data.layer === 'CHARACTER_BELIEF' && !text(row.data.observer_id)) return false;
  if (!['APPROVED', 'REVIEW', 'REJECTED', 'ARCHIVED'].includes(row.status || '') || row.data.evidence !== undefined && (!Array.isArray(row.data.evidence) || row.data.evidence.length > 20 || !row.data.evidence.every((quote: unknown) => object(quote) && text(quote.chapter_id) && Object.hasOwn(evidence.source_versions, quote.chapter_id) && text(quote.quote, 4000) && Number.isSafeInteger(quote.start) && quote.start >= 0))) return false;
  const keys = Object.keys(evidence.source_versions);
  return keys.length === Object.keys(row.sources).length && keys.every(key => {
    const a = evidence.source_versions[key], b = row.sources[key];
    return object(b) && a.version === b.version && a.digest === b.digest;
  });
}
type ReviewProps = { client: ExperimentalClient; evidence: StoryEvidence; blocked: boolean; onEdit: (row: Row, copy: boolean) => void };
export function StoryGraphEvidenceReview(props: ReviewProps) {
  return validStoryEvidence(props.evidence) ? <OriginalEvidenceReview key={JSON.stringify(props.evidence)} {...props} /> : <StatusMessage tone="warning">查询证据标识、版本或摘要不完整，不能读取或载入原记录。</StatusMessage>;
}
function OriginalEvidenceReview({ client, evidence, blocked, onEdit }: ReviewProps) {
  const resource = useResource(signal => client.get<Row>(`/story-graph/records/${segment(evidence.record_id)}`, signal), [client, evidence]);
  const live = useRef({ active: true, blocked, evidence, client, consumed: false });
  live.current.blocked = blocked;
  if (live.current.evidence !== evidence || live.current.client !== client) live.current = { active: true, blocked, evidence, client, consumed: false };
  useEffect(() => { live.current.active = true; return () => { live.current.active = false; }; }, []);
  const [consumed, setConsumed] = useState(false);
  useEffect(() => { setConsumed(false); }, [evidence]);
  const row = resource.data;
  const exact = !resource.loading && !resource.error && row && matchesStoryEvidence(row, evidence) ? row : undefined;
  const quotes = exact && Array.isArray(exact.data.evidence) ? exact.data.evidence : [];
  return <section className="experimental-section" aria-label="原语义记录证据核对"><h3>原语义记录证据核对</h3>
    <p>记录 {evidence.record_id} · 查询时 v{evidence.record_version}</p><ResourceState loading={resource.loading} error={resource.error} />
    {!resource.loading && !resource.error && !exact && <StatusMessage tone="warning">原记录版本或来源摘要已变化、失效或不完整。不能按旧查询载入编辑；请重新查询。</StatusMessage>}
    {exact && <><p>{exact.title} · {exact.status} · v{exact.version}</p><p>原资料性质：{exact.data.layer || exact.kind}。人物信念、研究与推测不能当作作者事实。</p>
      <h4>记录的来源快照</h4>{Object.entries(evidence.source_versions).map(([id, pin]) => <p key={id}>{id} · v{pin.version} · 摘要 {pin.digest}</p>)}
      <StatusMessage>原服务已读取当前记录；此处只核对查询与记录的版本及来源摘要，没有重新计算正文摘要。章节入口显示当前正文，不提供历史原文回放。</StatusMessage>
      <h4>作者记录中的原文证据</h4>{quotes.length ? quotes.filter(object).slice(0, 20).map((quote: any, index: number) => <article className="experimental-record" key={index}><p>章节 {typeof quote.chapter_id === 'string' ? quote.chapter_id : '未知'} · 起始字符 {Number.isSafeInteger(quote.start) ? quote.start : '未知'}</p><p>{typeof quote.quote === 'string' ? quote.quote : '原文未提供'}</p></article>) : <p>没有记录原文引文；关系声明不是自动推理证明。</p>}
      <Button disabled={blocked || consumed || !['APPROVED', 'REVIEW', 'REJECTED', 'ARCHIVED'].includes(exact.status || '')} onClick={() => { if (live.current.active && live.current.evidence === evidence && live.current.client === client && !live.current.blocked && !live.current.consumed) { live.current.consumed = true; setConsumed(true); onEdit(exact, exact.status === 'APPROVED'); } }}>{exact.status === 'APPROVED' ? '将原关系复制到待审表单' : '在原表单编辑此记录'}</Button>
      {blocked && <StatusMessage tone="warning">原表单有未保存输入或正在保存。请先保存或明确取消，再载入证据记录。</StatusMessage>}
      {consumed && <StatusMessage>已载入原表单；请人工编辑并保存。没有自动批准或合并事实。</StatusMessage>}
    </>}
  </section>;
}
