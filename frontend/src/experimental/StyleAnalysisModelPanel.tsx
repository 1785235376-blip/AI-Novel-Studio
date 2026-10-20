import { useLayoutEffect, useRef, useState } from 'react';
import type { Chapter } from '../api';
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import { ErrorMessage, Field } from './shared';
import { useReviewAction, type JudgeModelCatalog, type StyleAnalysis, type StyleReviewClient } from './styleReviewClient';
const categories = { NARRATIVE_DISTANCE: '叙事距离', EMOTIONAL_TONE: '情感语气', RHYTHM: '节奏', HUMOR: '幽默', IMAGERY: '意象' };
type Props = { api: StyleReviewClient; analysis: StyleAnalysis; chapter?: Chapter; onChanged: () => void };
export function StyleAnalysisModelPanel({ api, analysis, chapter, onChanged }: Props) {
  const [catalog, setCatalog] = useState<JudgeModelCatalog>(), [route, setRoute] = useState(analysis.model_preview?.broker.chosen?.route_id || '');
  const [reviewed, setReviewed] = useState(false), [hidden, setHidden] = useState(false), [reasons, setReasons] = useState<Record<string, string>>({});
  const action = useReviewAction(), epoch = useRef(0), chapterKey = `${chapter?.id}:${chapter?.version}`;
  const previousChapter = useRef(chapterKey);
  useLayoutEffect(() => { if (chapterKey !== previousChapter.current) { epoch.current++; setReviewed(false); setHidden(true); previousChapter.current = chapterKey; } }, [chapterKey]);
  useLayoutEffect(() => { setReviewed(false); }, [analysis.model_preview?.preview_digest]);
  const preview = !analysis.stale && !hidden ? analysis.model_preview : undefined, execution = analysis.model_execution;
  const load = () => action.run(async current => { const ticket = ++epoch.current; const value = await api.styleModelCatalog(); if (current() && ticket === epoch.current) setCatalog(value); });
  const prepare = () => action.run(async current => { const ticket = ++epoch.current; await api.previewStyleModel(analysis, route); if (current() && ticket === epoch.current) { setReviewed(false); setHidden(false); onChanged(); } });
  const send = () => action.run(async current => { const ticket = ++epoch.current; setReviewed(false); await api.dispatchStyleModel(analysis); if (current() && ticket === epoch.current) onChanged(); });
  const refresh = (cancel = false) => action.run(async current => { const ticket = ++epoch.current; await (cancel ? api.cancelStyleModel(analysis) : api.refreshStyleModel(analysis)); if (current() && ticket === epoch.current) onChanged(); });
  const review = (id: string, decision: 'review' | 'ignore' | 'reopen') => action.run(async current => { const ticket = ++epoch.current; await api.reviewStyleOpinion(analysis, id, decision, reasons[id].trim()); if (current() && ticket === epoch.current) onChanged(); }, '文风意见的审核决定已保存；确定性指标、风格档案和正文未改动。');
  return <section aria-label={`文风模型意见 ${analysis.id}`}>
    <h4>Model Opinion · 可选模型解读</h4>
    <p>只发送此报告选定的原文范围与当前风格档案。选择本地已注册模型、核对准确请求后再发送；已知零费用，禁止云端回退。模型意见单独保存，不会改写档案、指标或正文。</p>
    {!execution && <><Button disabled={action.busy || analysis.stale} onClick={() => void load()}>查看文风解读本地模型</Button>
      {catalog && <><Field label={`文风解读模型 ${analysis.id}`}><select disabled={action.busy} value={route} onChange={e => { epoch.current++; setRoute(e.target.value); setReviewed(false); setHidden(true); }}><option value="">明确选择一个本地模型</option>{catalog.routes.map(model => <option key={model.route_id} value={model.route_id} disabled={!model.available}>{model.display_name} · {model.provider_id}/{model.model_id}{model.synthetic ? ' · 合成协议测试' : ''}</option>)}</select></Field>
        {!catalog.routes.length && <EmptyState title="未配置可用的本地文风解读模型" detail="在原模型中心配置后再刷新。本页不安装模型或改用云端。" />}
        <Button disabled={action.busy || analysis.stale || !catalog.routes.some(model => model.route_id === route && model.available)} onClick={() => void prepare()}>准备准确文风模型预览</Button>
      </>}
    </>}
    {preview && <section aria-label={`准确文风模型预览 ${analysis.id}`}>
      <Badge>{preview.quality_verification === 'SYNTHETIC_PROTOCOL_ONLY' ? '合成协议测试；真实质量未验证' : 'Model-derived；真实质量未验证'}</Badge>
      <p>风格档案：{preview.style_profile.title} v{preview.style_profile.version} · 原文范围 {preview.samples.length} 个 · 不截断 · Token 数未知</p>
      <Field label={`准确文风模型请求 ${analysis.id}`}><textarea readOnly rows={10} value={JSON.stringify(preview.request, null, 2)} /></Field>
      <Field label={`文风模型身份与价格 ${analysis.id}`}><textarea readOnly rows={6} value={JSON.stringify({ actor: preview.actor, scope: preview.scope, sources: preview.sources, profile: preview.style_profile, samples: preview.samples, broker: preview.broker, budget: preview.budget }, null, 2)} /></Field>
      <p>排除：{preview.excluded.join('、')}。输出上限 {preview.max_output_bytes} 字节，时限 {preview.timeout_seconds} 秒。独立性未验证；无概率或文学评分。</p>
      {!preview.execution_available && <StatusMessage tone="warning">当前路线、价格或预算不满足已知零费用本地执行条件。请核对后重新预览。</StatusMessage>}
      {!execution && <><label className="experimental-check"><input type="checkbox" checked={reviewed} disabled={action.busy || !preview.execution_available} onChange={e => setReviewed(e.target.checked)} />已核对文风原文范围、档案、模型与零费用预占</label><Button disabled={action.busy || !reviewed || !preview.execution_available} onClick={() => void send()}>明确发送此次文风解读</Button></>}
    </section>}
    {hidden && !execution && <StatusMessage tone="warning">来源或选择已变化，旧预览不能发送。请重新预览。</StatusMessage>}
    {execution && <section aria-label={`原始文风模型任务 ${analysis.id}`}><p>原任务 {execution.job_id} · {execution.status} · {execution.receipt_state}</p>
      <p>{execution.model_called ? '已发生适配器调度，已发送的数据无法撤回。' : '尚未确认适配器调度。'}用量状态：{execution.usage_state}</p>
      {execution.failure_code && <StatusMessage tone="warning">{execution.failure_code}。无效意见不会发布。</StatusMessage>}
      {execution.receipt_state === 'UNKNOWN_NO_AUTOMATIC_REPLAY' && <StatusMessage tone="warning">原任务状态未知。只核对原任务，不自动重放、重建任务或释放未知预占。</StatusMessage>}
      <Button disabled={action.busy || analysis.stale} onClick={() => void refresh()}>查询原任务并核对文风证据</Button>
      <Button disabled={action.busy || ['COMPLETED', 'FAILED', 'CANCELLED'].includes(execution.status)} onClick={() => void refresh(true)}>取消原文风模型任务</Button>
    </section>}
    {!analysis.stale && analysis.model_opinion_state === 'ABSTAINED' && <StatusMessage>模型未提供有充分引文支持的文风意见；这不代表作品质量通过或未通过。</StatusMessage>}
    {!analysis.stale && !hidden && analysis.model_assessments?.map(opinion => <section className="experimental-record" key={opinion.id} aria-label={`文风意见 ${opinion.id}`}>
      <Badge>Model-derived · {categories[opinion.category]} · {opinion.decision}</Badge><p>{opinion.model.provider_id}/{opinion.model.model_id} · {opinion.quality_verification} · 独立性未验证</p>
      <p>{opinion.interpretation}</p><StatusMessage>判断边界：{opinion.boundary}</StatusMessage>
      {opinion.evidence.map((proof, index) => <section key={index}><p>章节 {proof.chapter_id} v{proof.chapter_version} · 原始 Markdown 段落 {proof.paragraph} · Unicode 范围 {proof.start}–{proof.end}</p><Field label={`文风意见 ${opinion.id} 引文 ${index + 1}`}><textarea readOnly value={proof.quote} /></Field></section>)}
      <Field label={`文风意见审核理由 ${opinion.id}`}><textarea maxLength={2000} disabled={action.busy} value={reasons[opinion.id] || ''} onChange={e => setReasons(values => ({ ...values, [opinion.id]: e.target.value }))} /></Field>
      <div className="experimental-actions">{opinion.decision === 'PENDING' ? <><Button disabled={action.busy || !reasons[opinion.id]?.trim()} onClick={() => void review(opinion.id, 'review')}>记录文风意见已核对</Button><Button disabled={action.busy || !reasons[opinion.id]?.trim()} onClick={() => void review(opinion.id, 'ignore')}>忽略此文风意见</Button></> : <Button disabled={action.busy || !reasons[opinion.id]?.trim()} onClick={() => void review(opinion.id, 'reopen')}>重新打开文风意见</Button>}</div>
      {!!opinion.review_history.length && <details className="experimental-details"><summary>文风意见审核历史</summary>{opinion.review_history.map((event, index) => <p key={index}>{event.action} · {event.at} · {event.reason}</p>)}</details>}
    </section>)}
    {!!action.error && <><ErrorMessage error={action.error} /><StatusMessage tone="warning">请求未确认，输入保留。刷新报告可核对已保存状态；不会自动再次发送。来源、权限、开关或路线变化必须重新核对。</StatusMessage></>}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
  </section>;
}
