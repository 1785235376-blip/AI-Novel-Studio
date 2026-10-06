import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { Chapter } from '../api';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { NarrativeJudgeRevisionTaskPanel } from './NarrativeJudgeRevisionTaskPanel';
import { NarrativeJudgeModelPanel } from './NarrativeJudgeModelPanel';
import { ErrorMessage, Field, ResourceState, useResource } from './shared';
import type { WorkspaceNavigation } from './uxClient';
import { styleReviewClient, useReviewAction, type JudgeFinding, type JudgeRun, type StyleReviewClient } from './styleReviewClient';

type Props = { client: ExperimentalClient; chapter?: Chapter; onNavigate?: (target: WorkspaceNavigation) => void };
const decisions = { PENDING: '待核对', REVIEWED: '已核对', ACCEPTED: '已接受建议', IGNORED: '已忽略', INTENTIONAL: '有意安排' };
const categoryLabels: Record<string, string> = { REPETITION: '重复', PARAGRAPH: '段落', PUNCTUATION: '标点', STRUCTURE: '结构', NARRATIVE: '叙事', STYLE: '文风', CONTINUITY: '连续性', READABILITY: '可读性', CHARACTER: '人物', WORLD_CONSISTENCY: '世界一致性', PACING: '节奏', DIALOGUE: '对白', FORESHADOWING: '伏笔', SCENE_PURPOSE: '场景目的', SUBPLOT: '支线' };
const checkLabels: Record<string, string> = { EXACT_REPEATED_PARAGRAPH: '完全重复的段落', REVIEWED_WORLD_CONFLICT: '已审核世界资料的冲突' };
let scopeSequence = 0;
export function NarrativeJudgePanel(props: Props) {
  const identity = useMemo(() => ++scopeSequence, [props.client]);
  return <NarrativeJudgeBody key={identity} {...props} />;
}
function NarrativeJudgeBody({ client, chapter, onNavigate }: Props) {
  const api = useMemo(() => styleReviewClient(client), [client]);
  const catalog = useResource(signal => api.judgeCatalog(signal), [api]);
  const runs = useResource(signal => api.runs(signal), [api]);
  const [chapterIds, setChapterIds] = useState<string[]>(chapter ? [chapter.id] : []), [rubricId, setRubricId] = useState('narrative-rules-v1'), [runId, setRunId] = useState('');
  const [decision, setDecision] = useState(''), [category, setCategory] = useState('');
  const [reviewDrafts, setReviewDrafts] = useState<Record<string, { reason: string; linkRevision: boolean }>>({});
  const detail = useResource(signal => runId ? api.run(runId, signal) : Promise.resolve(undefined), [api, runId]);
  const action = useReviewAction(), epoch = useRef(0);
  useLayoutEffect(() => { epoch.current++; setReviewDrafts(drafts => Object.values(drafts).some(value => value.linkRevision) ? Object.fromEntries(Object.entries(drafts).map(([id, value]) => [id, { ...value, linkRevision: false }])) : drafts); }, [chapter?.id, chapter?.version]);
  const ready = !catalog.loading && !catalog.error && !!catalog.data;
  const rubric = catalog.data?.rubrics.find(row => row.id === rubricId);
  const selectedChapters = catalog.data?.chapters.filter(row => chapterIds.includes(row.id)) || [];
  const fresh = ready && !runs.loading && !runs.error && !detail.loading && !detail.error;
  const run = fresh && detail.data?.id === runId ? detail.data : undefined;
  const categories = [...new Set((run?.findings || []).map(row => row.category))];
  const filtered = (run?.findings || []).filter(row => (decision ? row.decision === decision : row.decision !== 'INTENTIONAL') && (!category || row.category === category));
  const refresh = () => { epoch.current++; catalog.reload(); runs.reload(); detail.reload(); };
  const start = () => action.run(async isCurrent => {
    const ticket = ++epoch.current;
    const result = await api.startRun(selectedChapters, rubric!.id);
    if (isCurrent() && ticket === epoch.current) { setRunId(result.id); setDecision(''); setCategory(''); runs.reload(); detail.reload(); }
  }, '已生成有证据范围的规则检查。请逐条核对；正文未改动。');
  return <section className="experimental-section" aria-label="叙事证据审阅">
    <div className="experimental-actions"><h3>叙事证据审阅</h3><Badge>建议需要作者判断</Badge><Button disabled={catalog.loading || runs.loading || detail.loading || action.busy} onClick={refresh}>刷新审阅与来源（保留输入）</Button></div>
    <p>先运行确定性规则检查，再按需预览并单独发送给已注册的本地模型。规则与模型意见分别标注，没有文学总分，不自动改写正文或批准 Canon。</p>
    <ResourceState loading={catalog.loading} error={catalog.error} />
    {!!catalog.error && <StatusMessage tone="warning">请核对本机会话、当前分支权限和功能开关后刷新；尚未提交的选择与审核理由保留在本页。</StatusMessage>}
    <Panel title="选择审阅范围">
      <Field label="审阅规则集"><select disabled={!ready || action.busy} value={rubricId} onChange={e => { epoch.current++; setRubricId(e.target.value); }}><option value="">请选择规则集</option>{ready && catalog.data!.rubrics.map(row => <option key={row.id} value={row.id}>{row.title} · v{row.version}</option>)}</select></Field>
      {rubric && <><h4>本次检查范围</h4><ul>{rubric.checks.map((check, index) => <li key={index}>{checkLabels[check] || check}</li>)}</ul><h4>判断边界</h4><ul>{rubric.limitations.map((limit, index) => <li key={index}>{limit}</li>)}</ul></>}
      <fieldset className="experimental-form" disabled={!ready || action.busy}><legend>已保存的章节（最多 20 章）</legend>{ready && catalog.data!.chapters.map(row => <label className="experimental-check" key={row.id}><input type="checkbox" checked={chapterIds.includes(row.id)} disabled={!chapterIds.includes(row.id) && chapterIds.length >= 20} onChange={() => { epoch.current++; setChapterIds(values => values.includes(row.id) ? values.filter(id => id !== row.id) : [...values, row.id]); }} />审阅章节：{row.title} · v{row.version}</label>)}</fieldset>
      {ready && !catalog.data!.chapters.length && <EmptyState title="没有可审阅的已保存章节" detail="先保存正文，再返回刷新；不会读取其他分支的正文作为替代。" />}
      {ready && selectedChapters.length !== chapterIds.length && <StatusMessage tone="warning">部分已选章节现在不可用。<Button disabled={action.busy} onClick={() => { epoch.current++; setChapterIds(selectedChapters.map(row => row.id)); }}>取消不可用章节的选择</Button></StatusMessage>}
      {chapter && <Button disabled={!ready || action.busy || !catalog.data!.chapters.some(row => row.id === chapter.id)} onClick={() => { epoch.current++; setChapterIds([chapter.id]); }}>仅选择当前章节 {chapter.title}</Button>}
      <Button disabled={!ready || action.busy || !rubric || !selectedChapters.length || selectedChapters.length !== chapterIds.length} onClick={() => void start()}>检查所选已保存章节</Button>
      {!!action.error && <ErrorMessage error={action.error} />}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
      {!!action.error && <StatusMessage tone="warning">选择和审核理由仍保留。若来源或权限已变化，请刷新核对后重试，不会自动重发检查。</StatusMessage>}
    </Panel>
    {run && <NarrativeJudgeModelPanel key={run.id} api={api} run={run} chapter={chapter} onChanged={() => { detail.reload(); runs.reload(); }} />}
    <Panel title="检查记录与证据">
      <ResourceState loading={runs.loading} error={runs.error} />
      {!runs.loading && !runs.error && !runs.data?.items.length && <EmptyState title="还没有审阅记录" detail="先选择章节并运行检查。打开页面不会调用模型或自动审稿。" />}
      <Field label="查看审阅记录"><select disabled={!ready || runs.loading || !!runs.error || action.busy} value={runId} onChange={e => { epoch.current++; setRunId(e.target.value); setDecision(''); setCategory(''); }}><option value="">请选择一次检查</option>{ready && !runs.loading && !runs.error && runs.data?.items.map((row, index) => <option key={row.id} value={row.id}>检查 {index + 1} · {row.created_at || row.id.slice(0, 12)}{row.stale ? ' · 来源已变化' : ''}</option>)}</select></Field>
      {runId && <ResourceState loading={detail.loading} error={detail.error} />}
      {!!detail.error && <StatusMessage tone="warning">记录不可用或权限发生变化。刷新可重新核对；不会使用旧的隐藏结果继续审核。</StatusMessage>}
      {run && <><div className="experimental-actions"><Badge tone={run.stale ? 'warning' : 'neutral'}>{run.stale ? '来源已变化' : '规则检查已完成'}</Badge><span>{run.stale ? '历史结果已隐藏' : `${run.findings.length} 条检查线索`} · {run.model_called ? '记录包含模型判断，请核对来源' : '未调用模型'}</span></div>
        {run.stale && <StatusMessage tone="warning">这是旧来源的历史检查。核对上方最新章节范围，再点击“检查所选已保存章节”创建新记录。旧记录不会被覆盖。</StatusMessage>}
        {!!run.abstentions?.length && <section aria-label="无法判断的项目"><h4>本次无法判断</h4><ul>{run.abstentions.map((text, index) => <li key={index}>{text}</li>)}</ul></section>}
        <div className="experimental-grid"><Field label="按审核决定筛选"><select value={decision} onChange={e => setDecision(e.target.value)}><option value="">全部决定（隐藏有意安排）</option>{Object.entries(decisions).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field><Field label="按问题类别筛选"><select value={category} onChange={e => setCategory(e.target.value)}><option value="">全部类别</option>{categories.map(value => <option key={value} value={value}>{categoryLabels[value] || value}</option>)}</select></Field></div>
        {!run.stale && run.findings.some(row => row.decision === 'INTENTIONAL') && !decision && <StatusMessage>有意安排的重复线索已收起。选择“有意安排”可查看或重新打开。</StatusMessage>}
        {!run.stale && !run.findings.length && <EmptyState title="规则未发现匹配线索" detail="这不代表情节、人物动机或文学质量已经通过审查；请结合上方判断边界继续阅读。" />}
        {!!run.findings.length && !filtered.length && <EmptyState title="当前筛选没有结果" detail="更改决定或类别筛选，可查看其他检查线索。" />}
        <div className="experimental-list">{run.findings.map(finding => <div key={`${run.id}:${finding.id}`} hidden={!filtered.some(row => row.id === finding.id)}><FindingReview api={api} action={action} finding={finding} run={run} chapter={chapter} onNavigate={onNavigate} draft={reviewDrafts[finding.id] || { reason: '', linkRevision: false }} onDraftChange={value => setReviewDrafts(drafts => ({ ...drafts, [finding.id]: value }))} onChanged={() => { detail.reload(); runs.reload(); }} /></div>)}</div>
      </>}
    </Panel>
  </section>;
}
function FindingReview({ api, action, finding, run, chapter, onNavigate, onChanged, draft, onDraftChange }: { api: StyleReviewClient; action: ReturnType<typeof useReviewAction>; finding: JudgeFinding; run: JudgeRun; chapter?: Chapter; onNavigate?: Props['onNavigate']; onChanged: () => void; draft: { reason: string; linkRevision: boolean }; onDraftChange: (draft: { reason: string; linkRevision: boolean }) => void }) {
  const { reason, linkRevision } = draft;
  const stale = run.stale || finding.stale;
  const canLinkRevision = !!chapter && run.findings.some(row => row.evidence.some(proof => proof.chapter_id === chapter.id));
  const review = (name: 'review' | 'accept' | 'ignore' | 'intentional' | 'reopen') => action.run(async isCurrent => {
    await api.reviewFinding(finding.id, { expected_version: finding.version, action: name, reason: reason.trim(), ...(linkRevision && canLinkRevision && chapter ? { revision_chapter_id: chapter.id, revision_version: chapter.version } : {}) });
    if (isCurrent()) onChanged();
  }, '审核决定已记录。关联修订仅记录证据，不宣称建议已自动落实。');
  if (stale) return <article className="experimental-record" aria-label={`检查线索 ${finding.id}`}><Badge tone="warning">来源已变化</Badge><StatusMessage tone="warning">旧证据与评语已隐藏。请重新检查当前章节。</StatusMessage></article>;
  return <article className="experimental-record" aria-label={`检查线索 ${finding.id}`}>
    <div className="experimental-actions"><strong>{categoryLabels[finding.category] || finding.category} · {finding.code}</strong><Badge tone={finding.severity === 'WARNING' ? 'warning' : 'info'}>{finding.severity === 'WARNING' ? '待注意' : '提示'}</Badge><Badge>{decisions[finding.decision]} · v{finding.version}</Badge><Badge>{finding.origin === 'MODEL_ASSESSMENT' ? '模型判断' : '确定性规则'}</Badge></div>
    {finding.model && <StatusMessage tone="warning">{finding.model.synthetic ? '合成协议测试，未调用真实模型' : '模型意见，文学质量未验证'} · {finding.model.provider_id} / {finding.model.model_id}。独立性未验证；相同模型不同提示不构成独立审稿。</StatusMessage>}
    <p>{finding.explanation}</p><p>建议：{finding.suggestion}</p><StatusMessage>判断边界：{finding.boundary}</StatusMessage>
    {stale && <StatusMessage tone="warning">来源已变化，此线索保留供历史核对。请重新检查最新来源，不能继续据此修改审核决定。</StatusMessage>}
    {!finding.evidence.length && <StatusMessage tone="warning">此线索没有可定位的原文证据，不能据此推断全章结论。</StatusMessage>}
    {finding.evidence.map((evidence, index) => <section key={`${evidence.chapter_id}:${index}`} aria-label={`原文证据 ${index + 1}`}><p>来源章节 {evidence.chapter_id} · v{evidence.chapter_version} · 段落 {evidence.paragraph} · 原始 Markdown 字符范围 {evidence.start}–{evidence.end}（结束位置不含）</p><Field label={`证据 ${finding.id}-${index + 1} 原文`}><textarea readOnly value={evidence.quote} /></Field><Button disabled={!onNavigate || stale || action.busy} onClick={() => onNavigate?.({ kind: 'chapter', id: evidence.chapter_id, version: evidence.chapter_version })}>打开此证据来源章节 {index + 1}</Button></section>)}
    {finding.decision === 'INTENTIONAL' && <StatusMessage>有意安排：相同原文段落、重复位置和检查依据的后续线索将继续收起。改变证据会重新提示。可在此明确重新打开；不会静默改稿。</StatusMessage>}
    {finding.intentional_reused && <p>已复用此前对此相同证据的有意安排决定。旧检查的私人理由未复制到本次来源。</p>}
    {finding.revision && <p>已关联修订：{finding.revision.chapter_id} · v{finding.revision.version}。此关联不代表已自动修正。</p>}
    {!!finding.review_history?.some(row => row.reason) && <details className="experimental-details"><summary>查看已保存的审核理由</summary>{finding.review_history.filter(row => row.reason).map((row, index) => <section key={index}><strong>{{ REVIEW: '已核对', ACCEPT: '已接受建议', IGNORE: '已忽略', INTENTIONAL: '有意安排', REOPEN: '重新打开' }[row.action] || row.action} · {row.at || '时间未提供'}</strong><p>{row.reason}</p></section>)}</details>}
    <p>接受建议只记录作者决定。创建修订任务会进入现有协作室，仍需人工处理与审核，不发起模型调用。</p>
    <p>来源位置按原始 Markdown 的 Unicode 字符计数。打开时定位到对应章节，原文范围请对照上方引文核对。</p>
    <Field label={`审核理由 ${finding.id}`}><textarea maxLength={2000} disabled={action.busy} value={reason} onChange={e => onDraftChange({ ...draft, reason: e.target.value })} placeholder="记录为什么采纳检查线索、忽略或重新打开；不会改动正文。" /></Field>
    <label className="experimental-check"><input type="checkbox" disabled={!canLinkRevision || action.busy || stale} checked={linkRevision} onChange={e => onDraftChange({ ...draft, linkRevision: e.target.checked })} />关联当前已保存修订{chapter ? `「${chapter.title}」v${chapter.version}` : '（请先选择章节）'}</label>
    {chapter && !canLinkRevision && <p>当前章节不在本次原文证据中，请打开证据来源后再关联修订。</p>}
    <div className="experimental-actions">{finding.decision === 'PENDING' ? <><Button disabled={stale || action.busy || !reason.trim()} onClick={() => void review('review')}>记录已核对</Button><Button disabled={stale || action.busy || !reason.trim()} onClick={() => void review('accept')}>接受建议（不改正文）</Button><Button disabled={stale || action.busy || !reason.trim()} onClick={() => void review('ignore')}>记录忽略理由</Button><Button disabled={stale || action.busy || !reason.trim()} onClick={() => void review('intentional')}>标为有意安排，不再重复提示</Button></> : <Button disabled={stale || action.busy || !reason.trim()} onClick={() => void review('reopen')}>重新打开核对</Button>}</div>
    {finding.decision !== 'INTENTIONAL' && <NarrativeJudgeRevisionTaskPanel key={`${finding.id}:${finding.version}`} api={api} finding={finding} disabled={action.busy} onNavigate={onNavigate} />}
  </article>;
}
