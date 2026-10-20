import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { Chapter } from '../api';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { audienceReviewClient, type AudienceComparison, type AudienceFinding, type AudienceInput, type AudienceProfile, type AudienceReviewClient, type AudienceRun } from './audienceReviewClient';
import { ErrorMessage, Field, ResourceState, useResource } from './shared';
import type { JudgeReviewInput } from './styleReviewClient';
import type { WorkspaceNavigation } from './uxClient';

type Props = { client: ExperimentalClient; chapter?: Chapter; onNavigate?: (target: WorkspaceNavigation) => void };
type NoteDraft = { paragraph: string; observation: string; suggestion: string };
type ProfileDraft = Omit<AudienceProfile, 'reading_speed'> & { reading_speed: string };
type Draft = { profiles: [ProfileDraft, ProfileDraft]; notes: [NoteDraft, NoteDraft]; comparison: AudienceComparison };
const experiences = { NOVICE: '初次接触此类型', FAMILIAR: '熟悉此类型', EXPERIENCED: '经常阅读此类型' };
const ages = { GENERAL: '一般读者', CHILDREN: '儿童向内容', TEENS: '青少年向内容', ADULTS: '成人向内容' };
const comparisons = { DIFFERENT_ADVICE: '存在不同建议', AGREEMENT: '建议一致', NOT_ASSESSED: '尚未比较建议' };
const decisions = { PENDING: '待核对', REVIEWED: '已核对', ACCEPTED: '已接受建议', IGNORED: '已忽略', INTENTIONAL: '有意安排' };
const emptyDraft = (): Draft => ({ profiles: [
  { name: '读者设定 A', genre_experience: 'NOVICE', target_age_group: 'GENERAL', language_habit: '', reading_speed: '250' },
  { name: '读者设定 B', genre_experience: 'EXPERIENCED', target_age_group: 'GENERAL', language_habit: '', reading_speed: '400' },
], notes: [{ paragraph: '', observation: '', suggestion: '' }, { paragraph: '', observation: '', suggestion: '' }], comparison: 'NOT_ASSESSED' });
let scopeSequence = 0;
export function AudienceReviewPanel(props: Props) {
  const identity = useMemo(() => ++scopeSequence, [props.client]);
  return <AudienceReviewBody key={identity} {...props} />;
}
function AudienceReviewBody({ client, chapter, onNavigate }: Props) {
  const api = useMemo(() => audienceReviewClient(client), [client]);
  const contextKey = `${chapter?.id || ''}:${chapter?.version || ''}`;
  const catalog = useResource(async signal => ({ ...(await api.catalog(signal)), contextKey }), [api, contextKey]);
  const history = useResource(async signal => ({ ...(await api.comparisons(signal)), contextKey }), [api, contextKey]);
  const [chapterId, setChapterId] = useState(chapter?.id || '');
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [runId, setRunId] = useState('');
  const [reviewDrafts, setReviewDrafts] = useState<Record<string, string>>({});
  const epoch = useRef(0);
  useLayoutEffect(() => { epoch.current++; setChapterId(chapter?.id || ''); action.clear(); }, [contextKey]);
  const ready = !catalog.loading && !catalog.error && catalog.data?.contextKey === contextKey;
  const selected = ready ? catalog.data?.chapters.find(row => row.id === chapterId) : undefined;
  const currentVersion = selected && (selected.id !== chapter?.id || selected.version === chapter.version);
  const versionKey = selected ? `${selected.id}:${selected.version}` : '';
  const source = useResource(signal => currentVersion && selected ? api.source(selected.id, selected.version, signal) : Promise.resolve(undefined), [api, versionKey, currentVersion, contextKey]);
  const safeSource = ready && currentVersion && !source.loading && !source.error && source.data?.chapter_id === selected?.id && source.data?.chapter_version === selected?.version && /^[a-f0-9]{64}$/.test(source.data?.source_digest || '') ? source.data : undefined;
  const sourceKey = `${versionKey}:${safeSource?.source_digest || ''}`;
  const action = useAudienceAction(`${contextKey}:${chapterId}:${sourceKey}`);
  const draft = drafts[sourceKey] || emptyDraft();
  const update = (change: (value: Draft) => Draft) => { epoch.current++; action.clear(); setDrafts(values => ({ ...values, [sourceKey]: change(values[sourceKey] || emptyDraft()) })); };
  const editProfile = (index: 0 | 1, patch: Partial<ProfileDraft>) => update(value => ({ ...value, profiles: value.profiles.map((profile, offset) => offset === index ? { ...profile, ...patch } : profile) as Draft['profiles'] }));
  const editNote = (index: 0 | 1, patch: Partial<NoteDraft>) => update(value => ({ ...value, notes: value.notes.map((note, offset) => offset === index ? { ...note, ...patch } : note) as Draft['notes'] }));
  const validProfiles = draft.profiles.every(profile => profile.name.trim() && profile.language_habit.trim() && Number.isInteger(Number(profile.reading_speed)) && Number(profile.reading_speed) >= 1 && Number(profile.reading_speed) <= 10000);
  const normalizedProfiles = draft.profiles.map(profile => ({ ...profile, name: profile.name.trim(), language_habit: profile.language_habit.trim(), reading_speed: Number(profile.reading_speed) }));
  const distinctProfiles = JSON.stringify(normalizedProfiles[0]) !== JSON.stringify(normalizedProfiles[1]);
  const notesValid = draft.notes.every(note => !note.paragraph && !note.observation.trim() && !note.suggestion.trim() || Boolean(safeSource?.paragraphs.some(row => String(row.paragraph) === note.paragraph) && note.observation.trim() && note.suggestion.trim()));
  const comparisonValid = draft.comparison === 'NOT_ASSESSED' || draft.notes.every(note => note.observation.trim() && note.suggestion.trim());
  const canCreate = !!safeSource && validProfiles && distinctProfiles && notesValid && comparisonValid && !action.busy;
  const historyReady = ready && !history.loading && !history.error && history.data?.contextKey === contextKey;
  const run = historyReady ? history.data?.items.find(row => row.id === runId) : undefined;
  const runSource = run && catalog.data?.chapters.find(row => row.id === run.audience?.chapter_id);
  const stale = !!run && (run.stale || !run.audience || !runSource || runSource.version !== run.audience.chapter_version || chapter?.id === run.audience.chapter_id && chapter.version !== run.audience.chapter_version);
  const refresh = () => { epoch.current++; action.clear(); catalog.reload(); source.reload(); history.reload(); };
  const create = () => {
    if (!canCreate || !safeSource || !selected) return;
    const body: AudienceInput = {
      chapter_id: selected.id, expected_version: selected.version, expected_source_digest: safeSource.source_digest,
      profiles: normalizedProfiles as AudienceInput['profiles'],
      comparison: draft.comparison,
      observations: draft.notes.flatMap((note, index) => {
        if (!note.observation.trim()) return [];
        const paragraph = safeSource.paragraphs.find(row => String(row.paragraph) === note.paragraph)!;
        return [{ profile_index: index as 0 | 1, evidence: { ...paragraph, chapter_id: safeSource.chapter_id, chapter_version: safeSource.chapter_version }, observation: note.observation.trim(), suggestion: note.suggestion.trim() }];
      }),
    };
    const ticket = ++epoch.current;
    void action.run(async isCurrent => {
      const saved = await api.create(body);
      if (isCurrent() && ticket === epoch.current) { setRunId(saved.id); history.reload(); }
    }, '读者设定比较已保存。作者记录与阅读时长估算未修改正文。');
  };
  return <section className="experimental-section" aria-label="目标读者比较">
    <div className="experimental-actions"><h3>目标读者比较</h3><Badge>作者填写 · 不调用模型</Badge><Button disabled={catalog.loading || source.loading || history.loading || action.busy} onClick={refresh}>刷新读者比较与来源（保留输入）</Button></div>
    <p>用两个假设读者设定检查同一份已保存章节，记录你自己的观察和建议。这里不模拟真实读者，也没有读者测试结果或文学评分。</p>
    <StatusMessage>年龄组选项仅表示目标内容类别，不代表真实未成年人资料。类型经验和语言习惯由作者设定，不用于推断某类人群的能力。</StatusMessage>
    <ResourceState loading={catalog.loading} error={catalog.error} />
    {!!catalog.error && <StatusMessage tone="warning">当前来源或权限不可用。旧来源已隐藏，输入保留；请刷新后核对。</StatusMessage>}
    {!!action.error && <><ErrorMessage error={action.error} /><StatusMessage tone="warning">输入和审核理由已保留。请刷新核对来源与记录版本后重试；不会自动重复提交。</StatusMessage></>}
    {action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
    <Panel title="两个读者设定与同章证据">
      <Field label="读者比较章节"><select disabled={!ready || action.busy} value={chapterId} onChange={event => { epoch.current++; action.clear(); setChapterId(event.target.value); }}><option value="">请选择已保存章节</option>{ready && catalog.data!.chapters.map(row => <option key={row.id} value={row.id}>{row.title} · v{row.version}</option>)}</select></Field>
      {ready && !catalog.data!.chapters.length && <EmptyState title="没有可比较的已保存章节" detail="先保存正文，再刷新来源。" />}
      {chapterId && <ResourceState loading={source.loading} error={source.error} />}
      {selected && !currentVersion && <StatusMessage tone="warning">当前章节版本已变化，请刷新来源。旧引文和旧版本输入不会用于新版本。</StatusMessage>}
      {selected && currentVersion && !source.loading && !source.error && !safeSource && <StatusMessage tone="warning">来源回执与当前章节版本或完整性摘要不一致，已隐藏引文。请刷新核对。</StatusMessage>}
      {selected && currentVersion && <Button disabled={action.busy || source.loading} onClick={() => void action.run(async isCurrent => { await api.prepareSource(selected.id, selected.version); if (isCurrent()) source.reload(); }, '读者比较来源已准备，正在重新核对。')}>准备当前章节的读者比较来源</Button>}
      {!!source.error && <StatusMessage tone="warning">请核对来源版本、权限与功能状态。首次使用可明确准备此来源；不会自动初始化或修改正文。</StatusMessage>}
      {safeSource && <>
        <p>来源：{selected!.title} · v{safeSource.chapter_version}。引文位置由服务器按原始 Markdown 的 Unicode 码点提供，结束位置不含在内。</p>
        <p>阅读速度单位：非空白 Unicode 字符／分钟（1–10000）。阅读时长只是按字数和设定速度计算的估算，不代表实际测试。</p>
        <div className="experimental-grid">{([0, 1] as const).map(index => <fieldset className="experimental-form" disabled={action.busy} key={index}><legend>读者设定 {index === 0 ? 'A' : 'B'}</legend>
          <Field label={`设定 ${index + 1} 名称`}><input maxLength={120} value={draft.profiles[index].name} onChange={event => editProfile(index, { name: event.target.value })} /></Field>
          <Field label={`设定 ${index + 1} 类型经验`}><select value={draft.profiles[index].genre_experience} onChange={event => editProfile(index, { genre_experience: event.target.value as AudienceProfile['genre_experience'] })}>{Object.entries(experiences).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
          <Field label={`设定 ${index + 1} 目标内容年龄组`}><select value={draft.profiles[index].target_age_group} onChange={event => editProfile(index, { target_age_group: event.target.value as AudienceProfile['target_age_group'] })}>{Object.entries(ages).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
          <Field label={`设定 ${index + 1} 语言习惯`}><textarea maxLength={240} value={draft.profiles[index].language_habit} onChange={event => editProfile(index, { language_habit: event.target.value })} placeholder="例如：习惯现代中文，较少阅读古典用语。" /></Field>
          <Field label={`设定 ${index + 1} 阅读速度（非空白字符／分钟）`}><input type="number" min={1} max={10000} step={1} value={draft.profiles[index].reading_speed} onChange={event => editProfile(index, { reading_speed: event.target.value })} /></Field>
          <Field label={`设定 ${index + 1} 证据段落`}><select value={draft.notes[index].paragraph} onChange={event => editNote(index, { paragraph: event.target.value })}><option value="">暂不记录观察</option>{safeSource.paragraphs.map(paragraph => <option key={paragraph.paragraph} value={paragraph.paragraph}>段落 {paragraph.paragraph} · 字符 {paragraph.start}–{paragraph.end}</option>)}</select></Field>
          {safeSource.paragraphs.filter(paragraph => String(paragraph.paragraph) === draft.notes[index].paragraph).map(paragraph => <Field key={paragraph.paragraph} label={`设定 ${index + 1} 准确原文`}><textarea readOnly value={paragraph.quote} /></Field>)}
          <Field label={`设定 ${index + 1} 作者观察`}><textarea maxLength={2000} value={draft.notes[index].observation} onChange={event => editNote(index, { observation: event.target.value })} placeholder="仅记录你对这段证据的观察，不冒充读者反馈。" /></Field>
          <Field label={`设定 ${index + 1} 作者建议`}><textarea maxLength={2000} value={draft.notes[index].suggestion} onChange={event => editNote(index, { suggestion: event.target.value })} /></Field>
        </fieldset>)}</div>
        {!!safeSource.unsupported_paragraphs && <StatusMessage tone="warning">{safeSource.unsupported_paragraphs} 个段落超过 2000 字证据上限，不能在此引用；未截断原文冒充完整证据。</StatusMessage>}
        {!safeSource.paragraphs.length && <StatusMessage>此版本没有可引用段落。可保存阅读时长估算，但不能添加无证据的观察。</StatusMessage>}
        <Field label="作者对两组建议的比较"><select disabled={action.busy} value={draft.comparison} onChange={event => update(value => ({ ...value, comparison: event.target.value as AudienceComparison }))}>{Object.entries(comparisons).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
        <p>没有观察时选择“尚未比较建议”。声明一致或不同前，两组都需填写准确原文、观察和建议；结论仅代表作者判断。</p>
        <Button disabled={!canCreate} onClick={create}>保存两个设定的比较（不改正文）</Button>
      </>}
    </Panel>
    <Panel title="读者比较记录与作者决定">
      <ResourceState loading={history.loading} error={history.error} />
      {historyReady && !history.data?.items.length && <EmptyState title="还没有读者比较记录" detail="填写两个设定并明确保存；打开此页不会生成评价。" />}
      <Field label="查看读者比较记录"><select disabled={!historyReady || action.busy} value={runId} onChange={event => { epoch.current++; action.clear(); setRunId(event.target.value); }}><option value="">请选择一次比较</option>{historyReady && history.data!.items.map((row, index) => <option key={row.id} value={row.id}>比较 {index + 1} · {row.created_at || row.id}{row.stale ? ' · 来源已变化' : ''}</option>)}</select></Field>
      {run && (stale ? <StatusMessage tone="warning">比较来源已变化或不可用，旧设定、测量和观察已隐藏。请选择当前保存版本重新比较；原记录不会被覆盖。</StatusMessage> : run.audience && <>
        <p>来源 {run.audience.chapter_id} · v{run.audience.chapter_version}</p><Badge>{comparisons[run.audience.comparison]} · 作者判断</Badge>
        <div className="experimental-grid">{run.audience.profiles.map((profile, index) => <section className="experimental-record" key={index} aria-label={`已保存读者设定 ${index + 1}`}><h4>{profile.name}</h4><p>{experiences[profile.genre_experience]} · {ages[profile.target_age_group]}</p><p>语言习惯：{profile.language_habit}</p><p>设定速度：{profile.reading_speed} 非空白字符／分钟</p><p>设定版本：{profile.schema_version} · 摘要 {profile.digest}</p>{run.audience?.measurements.filter(row => row.profile_index === index).map(row => <p key={row.profile_index}>确定性测量：{row.nonspace_characters} 个非空白字符；估算 {row.estimated_seconds.toFixed(2)} 秒。不是实际读者测试。</p>)}</section>)}</div>
        {!run.findings.length && <StatusMessage>本次未填写有证据的作者观察；阅读时长估算不构成阅读理解或内容适龄结论。</StatusMessage>}
        <div className="experimental-list">{run.findings.map(finding => <AudienceFindingReview key={`${run.id}:${finding.id}`} api={api} action={action} finding={finding} run={run} reason={reviewDrafts[`${run.id}:${finding.id}`] || ''} onReason={value => setReviewDrafts(drafts => ({ ...drafts, [`${run.id}:${finding.id}`]: value }))} onChanged={history.reload} onNavigate={onNavigate} />)}</div>
      </>)}
    </Panel>
  </section>;
}
function AudienceFindingReview({ api, action, finding, run, reason, onReason, onChanged, onNavigate }: { api: AudienceReviewClient; action: ReturnType<typeof useAudienceAction>; finding: AudienceFinding; run: AudienceRun; reason: string; onReason: (value: string) => void; onChanged: () => void; onNavigate?: Props['onNavigate'] }) {
  if (finding.stale || finding.origin !== 'AUTHOR_ENTERED') return <StatusMessage tone="warning">旧来源或不支持的观察已隐藏，请重新核对来源。</StatusMessage>;
  const review = (name: JudgeReviewInput['action']) => action.run(async isCurrent => {
    await api.review(finding.id, { expected_version: finding.version, action: name, reason: reason.trim() });
    if (isCurrent()) onChanged();
  }, '作者决定已保存。接受建议仅记录决定，不会修改正文。');
  return <article className="experimental-record" aria-label={`读者观察 ${finding.id}`}>
    <div className="experimental-actions"><strong>{run.audience?.profiles[finding.audience_profile_index]?.name || '未知设定'}</strong><Badge>AUTHOR_ENTERED · 作者填写</Badge><Badge>{decisions[finding.decision]} · v{finding.version}</Badge></div>
    <p>作者观察：{finding.explanation}</p><p>作者建议：{finding.suggestion}</p><StatusMessage>{finding.boundary}</StatusMessage>
    {finding.evidence.map((evidence, index) => <section key={index} aria-label={`读者观察原文 ${finding.id}-${index + 1}`}><p>{evidence.chapter_id} · v{evidence.chapter_version} · 段落 {evidence.paragraph} · Unicode 字符 {evidence.start}–{evidence.end}（结束位置不含）</p><Field label={`读者观察证据 ${finding.id}-${index + 1}`}><textarea readOnly value={evidence.quote} /></Field><Button disabled={!onNavigate || action.busy} onClick={() => onNavigate?.({ kind: 'chapter', id: evidence.chapter_id, version: evidence.chapter_version })}>打开读者观察来源 {index + 1}</Button></section>)}
    {!!finding.review_history?.some(row => row.reason) && <details className="experimental-details"><summary>查看已保存的作者决定理由</summary>{finding.review_history.filter(row => row.reason).map((row, index) => <section key={index}><strong>{{ REVIEW: '已核对', ACCEPT: '已接受建议', IGNORE: '已忽略', INTENTIONAL: '有意安排', REOPEN: '重新打开' }[row.action] || row.action} · {row.at || '时间未提供'}</strong><p>{row.reason}</p></section>)}</details>}
    <Field label={`读者观察审核理由 ${finding.id}`}><textarea maxLength={2000} disabled={action.busy} value={reason} onChange={event => onReason(event.target.value)} /></Field>
    <div className="experimental-actions">{finding.decision === 'PENDING' ? <>{([['review', '记录已核对'], ['accept', '接受作者建议（不改正文）'], ['ignore', '记录忽略理由']] as const).map(([name, label]) => <Button key={name} disabled={action.busy || !reason.trim() || !finding.evidence.length} onClick={() => void review(name)}>{label}</Button>)}</> : <Button disabled={action.busy || !reason.trim() || !finding.evidence.length} onClick={() => void review('reopen')}>重新打开读者观察</Button>}</div>
  </article>;
}

// This panel changes saved-source scopes without unmounting its drafts. Shared
// useReviewAction only guards lifetime, so requests also need a source epoch.
function useAudienceAction(scope: string) {
  const [busy, setBusy] = useState(false), [error, setError] = useState<unknown>(), [notice, setNotice] = useState('');
  const sequence = useRef(0), running = useRef(false), alive = useRef(true), currentScope = useRef(scope);
  currentScope.current = scope;
  const clear = () => { sequence.current++; running.current = false; setBusy(false); setError(undefined); setNotice(''); };
  useLayoutEffect(() => { clear(); }, [scope]);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; sequence.current++; }; }, []);
  const run = async (operation: (isCurrent: () => boolean) => Promise<void>, message = '') => {
    if (running.current || !alive.current) return;
    running.current = true; setBusy(true); setError(undefined); setNotice('');
    const ticket = ++sequence.current;
    const isCurrent = () => alive.current && currentScope.current === scope && ticket === sequence.current;
    try { await operation(isCurrent); if (isCurrent()) setNotice(message); }
    catch (value) { if (isCurrent()) setError(value); }
    finally { if (isCurrent()) { running.current = false; setBusy(false); } }
  };
  return { busy, error, notice, run, clear };
}
