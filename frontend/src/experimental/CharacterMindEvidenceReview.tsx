import { useMemo, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { type ExperimentalClient, type Row, segment } from './api';
import { ResourceState, useResource } from './shared';
import { matchesCharacterMindEvidence, validCharacterMindEvidence, type CharacterMindEvidence } from './characterMindEvidence';

type Props = { client: ExperimentalClient; pin: CharacterMindEvidence; blocked: boolean; onCopy: (row: Row) => void };
let reviewSequence = 0;
export function CharacterMindEvidenceReview(props: Props) {
  const identity = useMemo(() => ++reviewSequence, [props.client, props.pin]);
  return validCharacterMindEvidence(props.pin) ? <OriginalMindEvidence key={identity} {...props} /> : <StatusMessage tone="warning">人物事件证据不完整，请返回人物视图重新查询。</StatusMessage>;
}
function OriginalMindEvidence({ client, pin, blocked, onCopy }: Props) {
  const resource = useResource(signal => client.get<Row>(`/story-graph/records/${segment(pin.evidence.record_id)}`, signal), [client, pin]);
  const [consumed, setConsumed] = useState(false);
  const consumedRef = useRef(false);
  const exact = !resource.loading && !resource.error && resource.data && matchesCharacterMindEvidence(resource.data, pin) ? resource.data : undefined;
  return <section className="experimental-section" aria-label="人物事件原始证据核对"><h3>人物事件原始证据核对</h3>
    <StatusMessage>已退出人物可知视图。以下是需要作者写作权限的原始事件；不会附加到人物生成请求。</StatusMessage>
    <p>人物 {pin.characterId} · {pin.category} · 事件 {pin.evidence.record_id} · 查询版本 v{pin.evidence.record_version}</p>
    <p>查询时人物认知：{pin.text}</p>
    <ResourceState loading={resource.loading} error={resource.error} />
    {!resource.loading && !resource.error && !exact && <StatusMessage tone="warning">原事件版本、人物、类别、来源摘要或审核状态已变化，不能载入旧证据。请返回人物视图重新查询。</StatusMessage>}
    {exact && <><p>{exact.title} · APPROVED · v{exact.version}</p>
      <p>事件 {exact.data.operation} · 状态标识 {exact.data.state_key} · 章内顺序 {exact.event_order} · 场景 {exact.data.scene_id || '章末 / 未知'}</p>
      <p>世界时间 {exact.data.world_time ?? '未知'} · 历法 {exact.data.calendar} · 有效范围 {exact.data.valid_from ?? '未知'} 至 {exact.data.valid_to ?? '未知'}</p>
      <p>动机证据：{exact.data.evidence_status === 'HYPOTHESIS' ? '假设 / 无法推导' : '作者明确指定'}。人物信念不等于作者事实。</p>
      <h4>事件保存的状态值</h4><p>{exact.data.value || '此事件从关联的已审核关系读取事实文本；这里不额外读取关系内容。'}</p>
      <h4>原始事件来源</h4>{Object.entries(pin.evidence.source_versions).map(([id, source]) => <p key={id}>{id} · v{source.version} · 摘要 {source.digest}</p>)}
      <StatusMessage>仅核对当前原事件与查询快照；不重新计算章节摘要，不提供历史正文回放。复制后仍需人工保存、审核，不会自动修改已批准事件或 Canon。</StatusMessage>
      <h4>作者记录中的原文证据</h4>{exact.data.evidence.length ? exact.data.evidence.map((quote: {chapter_id: string; start: number; quote: string}, index: number) => <article className="experimental-record" key={index}><p>{quote.chapter_id} · 起始字符 {quote.start}</p><p>{quote.quote}</p></article>) : <p>没有记录原文引文。</p>}
      <Button disabled={blocked || consumed} onClick={() => { if (!blocked && !consumedRef.current) { consumedRef.current = true; setConsumed(true); onCopy(exact); } }}>将原人物事件复制到待审表单</Button>
      {blocked && <StatusMessage tone="warning">请先保存或取消原表单输入，再载入事件。</StatusMessage>}
      {consumed && <StatusMessage>已载入原表单；请人工检查事件时点、状态值与来源后保存。</StatusMessage>}
    </>}
  </section>;
}
