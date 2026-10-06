import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { ApiError, type Chapter } from '../api';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { Details, ErrorMessage, Field, ResourceState, useResource } from './shared';
import type { WorkspaceNavigation } from './uxClient';
import { styleOperationLabels, styleReviewClient, useReviewAction, type StyleProfile, type StyleProfileInput, type StylePreview, type StyleOperation, type StyleAnalysis } from './styleReviewClient';

type Props = { client: ExperimentalClient; chapter?: Chapter; onNavigate?: (target: WorkspaceNavigation) => void; onUseStyle?: (id: string) => void };
const emptyProfile = (): StyleProfileInput => ({ title: '', instructions: '', rules: [], chapter_ids: [], character_ids: [] });
const statusLabel = { DRAFT: '待审核草稿', APPROVED: '已审核', ARCHIVED: '已归档' };
const toggle = (values: string[], id: string) => values.includes(id) ? values.filter(value => value !== id) : [...values, id];
let scopeSequence = 0;
export function StyleAnalysisPanel(props: Props) {
  const identity = useMemo(() => ++scopeSequence, [props.client]);
  return <StyleAnalysisBody key={identity} {...props} />;
}
function StyleAnalysisBody({ client, chapter, onNavigate, onUseStyle }: Props) {
  const api = useMemo(() => styleReviewClient(client), [client]);
  const catalog = useResource(signal => api.styleCatalog(signal), [api]);
  const analyses = useResource(signal => api.analyses(signal), [api]);
  const [draft, setDraft] = useState<StyleProfileInput>(emptyProfile), [rulesText, setRulesText] = useState(''), [editing, setEditing] = useState<StyleProfile>();
  const [selectedId, setSelectedId] = useState(''), [sampleIds, setSampleIds] = useState<string[]>([]), [ranges, setRanges] = useState<Record<string, { start: string; end: string }>>({});
  const [language, setLanguage] = useState<'zh' | 'en'>('zh'), [compare, setCompare] = useState(false), [operations, setOperations] = useState<StyleOperation[]>(['continue']);
  const [operation, setOperation] = useState<StyleOperation>('continue'), [characterId, setCharacterId] = useState(''), [preview, setPreview] = useState<StylePreview>(), [reviewed, setReviewed] = useState(false), [used, setUsed] = useState(false);
  const action = useReviewAction(), epoch = useRef(0);
  useLayoutEffect(() => () => { epoch.current++; }, []);
  const invalidate = () => { epoch.current++; setPreview(undefined); setReviewed(false); setUsed(false); };
  useLayoutEffect(() => { invalidate(); }, [chapter?.id, chapter?.version]);
  const selected = catalog.data?.styles.find(row => row.id === selectedId);
  const available = !catalog.loading && !catalog.error && !!catalog.data;
  const safePreview = available && preview && selected && preview.style_id === selected.id && preview.style_version === selected.version && preview.operation === operation && preview.character_id === (characterId || null) && preview.context_injection === 'INSTRUCTIONS_ONLY' && preview.rules_usage === 'REFERENCE_ONLY' && !preview.model_called && !!preview.preview_digest && selected.status === 'APPROVED' && !selected.stale ? preview : undefined;
  const changeDraft = (patch: Partial<StyleProfileInput>) => { invalidate(); setDraft(value => ({ ...value, ...patch })); };
  const refresh = () => { invalidate(); catalog.reload(); analyses.reload(); };
  const edit = (row: StyleProfile) => { invalidate(); setEditing(row); setDraft({ title: row.title, instructions: row.instructions, rules: row.rules, chapter_ids: row.chapter_ids, character_ids: row.character_ids }); setRulesText(row.rules.join('\n')); };
  const editCurrent = editing && catalog.data?.styles.find(row => row.id === editing.id);
  const outdatedEdit = Boolean(editing && editCurrent && editing.version !== editCurrent.version);
  const missingEdit = Boolean(editing && available && !editCurrent);
  const conflict = action.error instanceof ApiError && action.error.problem.status === 409;
  const samples = sampleIds.map(id => {
    const source = catalog.data?.chapters.find(row => row.id === id);
    const range = ranges[id] || { start: '0', end: '' };
    return { chapter_id: id, expected_version: source?.version || 0, start: Number(range.start), end: range.end === '' ? null : Number(range.end) };
  });
  const validSamples = samples.length > 0 && samples.every(row => row.expected_version > 0 && selected?.chapter_ids.includes(row.chapter_id) && Number.isInteger(row.start) && row.start >= 0 && (row.end === null || Number.isInteger(row.end) && row.end > row.start));
  const parsedRules = rulesText.split('\n').map(value => value.trim()).filter(Boolean);
  const validRules = parsedRules.length <= 50 && parsedRules.every(value => Array.from(value).length <= 4000);
  const save = () => action.run(async isCurrent => {
    const input = { ...draft, rules: parsedRules };
    const saved = editing ? await api.updateProfile(editing.id, editing.version, input) : await api.createProfile(input);
    if (isCurrent()) { setEditing(saved); setDraft(input); invalidate(); catalog.reload(); }
  }, '风格草稿已保存，请核对后审核。尚未用于生成。');
  return <section className="experimental-section" aria-label="文风分析与档案">
    <div className="experimental-actions"><h3>文风分析</h3><Badge>本地确定性统计 · 不调用模型</Badge><Button disabled={catalog.loading || analyses.loading || action.busy} onClick={refresh}>刷新风格与来源（保留输入）</Button></div>
    <ResourceState loading={catalog.loading} error={catalog.error} />
    {!!catalog.error && <StatusMessage tone="warning">请核对本机会话、项目与分支权限或功能开关后刷新。未保存的表单仍保留。</StatusMessage>}
    {!!action.error && <ErrorMessage error={action.error} />}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
    {conflict && <StatusMessage tone="warning">版本冲突：输入已保留。刷新来源并核对服务器版本，再明确决定是否继续保存或重新预览。</StatusMessage>}
    <Panel title="可复用风格档案">
      <p>风格指令沿用创作方案的版本化档案。审核后还须预览并明确选择，才会成为写作输入。</p>
      {editing && <StatusMessage>正在编辑「{editing.title}」v{editing.version}。保存会成为新的待审核草稿。</StatusMessage>}
      <form className="experimental-form" onSubmit={e => { e.preventDefault(); if (available && !outdatedEdit && !missingEdit && validRules && draft.title.trim() && draft.instructions.trim()) void save(); }}>
        <fieldset className="experimental-form" disabled={action.busy}>
          <legend>风格内容与适用范围</legend>
          <Field label="风格档案标题"><input required maxLength={200} value={draft.title} onChange={e => changeDraft({ title: e.target.value })} /></Field>
          <Field label="可复用风格指令（最多 120 字）"><textarea required maxLength={120} value={draft.instructions} onChange={e => changeDraft({ instructions: e.target.value })} /></Field>
          <Field label="参考规则（每行一条，不注入生成请求）"><textarea value={rulesText} onChange={e => { invalidate(); setRulesText(e.target.value); }} /></Field>
          <div className="experimental-grid"><section><h4>样本来源章节（最多 20 章）</h4>{available && catalog.data!.chapters.map(row => <label className="experimental-check" key={row.id}><input type="checkbox" checked={draft.chapter_ids.includes(row.id)} disabled={!draft.chapter_ids.includes(row.id) && draft.chapter_ids.length >= 20} onChange={() => changeDraft({ chapter_ids: toggle(draft.chapter_ids, row.id) })} />档案来源：{row.title} · v{row.version}</label>)}{available && !catalog.data!.chapters.length && <p>暂无可用章节，请先保存正文后刷新。</p>}</section><section><h4>关联人物（可选）</h4>{available && catalog.data!.characters.map(row => <label className="experimental-check" key={row.id}><input type="checkbox" checked={draft.character_ids.includes(row.id)} onChange={() => changeDraft({ character_ids: toggle(draft.character_ids, row.id) })} />关联人物：{row.name}</label>)}{available && !catalog.data!.characters.length && <p>暂无人物，可保留为通用风格。</p>}</section></div>
        </fieldset>
        {available && draft.chapter_ids.some(id => !catalog.data!.chapters.some(row => row.id === id)) && <StatusMessage tone="warning">部分章节关联已不可用。<Button type="button" disabled={action.busy} onClick={() => changeDraft({ chapter_ids: draft.chapter_ids.filter(id => catalog.data!.chapters.some(row => row.id === id)) })}>移除不可用的章节关联</Button></StatusMessage>}
        {available && draft.character_ids.some(id => !catalog.data!.characters.some(row => row.id === id)) && <StatusMessage tone="warning">部分人物关联已不可用。<Button type="button" disabled={action.busy} onClick={() => changeDraft({ character_ids: draft.character_ids.filter(id => catalog.data!.characters.some(row => row.id === id)) })}>移除不可用的人物关联</Button></StatusMessage>}
        {missingEdit && <StatusMessage tone="warning">原档案已不可用。输入仍保留，请恢复权限后刷新。<Button type="button" disabled={action.busy} onClick={() => { invalidate(); setEditing(undefined); }}>保留输入并另存为新档案</Button></StatusMessage>}
        {!validRules && <StatusMessage tone="warning">参考规则最多 50 条，每条不超过 4,000 个字符。请缩短后保存。</StatusMessage>}
        {outdatedEdit && <StatusMessage tone="warning">服务器已有 v{editCurrent!.version}。你的输入未覆盖；请先核对当前内容。<Details value={{ instructions: editCurrent!.instructions, rules: editCurrent!.rules, chapter_ids: editCurrent!.chapter_ids, character_ids: editCurrent!.character_ids }} label="核对服务器当前风格" /><Button type="button" disabled={action.busy || !available} onClick={() => { invalidate(); setEditing(editCurrent); action.clear(); }}>已核对，以服务器版本继续编辑（保留输入）</Button></StatusMessage>}
        <div className="experimental-actions"><Button type="submit" disabled={action.busy || !available || outdatedEdit || missingEdit || !validRules || draft.chapter_ids.length > 20 || !draft.title.trim() || !draft.instructions.trim()}>{editing ? '保存风格新草稿版本' : '保存风格草稿'}</Button>{editing && <Button type="button" disabled={action.busy} onClick={() => { invalidate(); setEditing(undefined); setDraft(emptyProfile()); setRulesText(''); }}>另建风格档案</Button>}</div>
      </form>
      {available && !catalog.data!.styles.length && <EmptyState title="还没有风格档案" detail="填写风格指令与样本来源，保存后再审核、分析或预览。" />}
      {available && <div className="experimental-list">{catalog.data!.styles.map(row => <article className="experimental-record" key={row.id}><div className="experimental-actions"><strong>{row.title}</strong><Badge>{statusLabel[row.status]} · v{row.version}</Badge>{row.stale && <Badge tone="warning">来源已变化</Badge>}</div><p>{row.instructions}</p><div className="experimental-actions"><Button disabled={action.busy} onClick={() => edit(row)}>编辑风格 {row.title}</Button>{row.status === 'DRAFT' && <Button disabled={action.busy || row.stale} onClick={() => void action.run(async isCurrent => { await api.transitionProfile(row, 'approve'); if (isCurrent()) refresh(); }, '风格已审核。使用前请检查准确注入内容。')}>审核风格 {row.title}</Button>}{row.status !== 'ARCHIVED' && <Button disabled={action.busy} onClick={() => void action.run(async isCurrent => { await api.transitionProfile(row, 'archive'); if (isCurrent()) refresh(); }, '风格已归档，版本历史仍由创作方案保留。')}>归档风格 {row.title}</Button>}</div></article>)}</div>}
    </Panel>
    <Panel title="选择样本并分析">
      <Field label="分析与预览的风格档案"><select disabled={!available || action.busy} value={selectedId} onChange={e => { invalidate(); setSelectedId(e.target.value); setSampleIds([]); setRanges({}); setCharacterId(''); }}><option value="">请明确选择一个档案</option>{available && catalog.data!.styles.filter(row => row.status !== 'ARCHIVED').map(row => <option key={row.id} value={row.id}>{row.title} · v{row.version} · {statusLabel[row.status]}</option>)}</select></Field>
      {selected && <><Field label="分析语言"><select disabled={action.busy} value={language} onChange={e => { invalidate(); setLanguage(e.target.value as 'zh' | 'en'); }}><option value="zh">中文（按字符统计）</option><option value="en">英文（按词统计）</option></select></Field><p>仅分析已保存正文中的明确范围；位置按原始 Markdown 的 Unicode 字符计数，从 0 开始，结束位置不包含在样本内。留空表示章末。</p>
        {available && catalog.data!.chapters.filter(row => selected.chapter_ids.includes(row.id)).map(row => <section className="experimental-record" key={row.id}><label className="experimental-check"><input type="checkbox" disabled={action.busy} checked={sampleIds.includes(row.id)} onChange={() => { invalidate(); setSampleIds(values => toggle(values, row.id)); }} />分析样本：{row.title} · v{row.version}</label>{sampleIds.includes(row.id) && <div className="experimental-grid"><Field label={`${row.title} 样本起始字符`}><input type="number" min={0} step={1} disabled={action.busy} value={ranges[row.id]?.start ?? '0'} onChange={e => { invalidate(); setRanges(values => ({ ...values, [row.id]: { start: e.target.value, end: values[row.id]?.end ?? '' } })); }} /></Field><Field label={`${row.title} 样本结束字符（留空至章末）`}><input type="number" min={1} step={1} disabled={action.busy} value={ranges[row.id]?.end ?? ''} onChange={e => { invalidate(); setRanges(values => ({ ...values, [row.id]: { start: values[row.id]?.start ?? '0', end: e.target.value } })); }} /></Field></div>}</section>)}
        {available && !catalog.data!.chapters.some(row => selected.chapter_ids.includes(row.id)) && <StatusMessage>此档案没有当前可用的样本来源。请先编辑档案，核对并关联已保存章节。</StatusMessage>}
        <fieldset className="experimental-form" disabled={action.busy}><legend>记录本次参考用途</legend>{(catalog.data?.operations || []).map(value => <label className="experimental-check" key={value}><input type="checkbox" checked={operations.includes(value)} onChange={() => { invalidate(); setOperations(values => toggle(values, value) as StyleOperation[]); }} />{styleOperationLabels[value]}</label>)}</fieldset>
        <label className="experimental-check"><input type="checkbox" disabled={!chapter || action.busy} checked={compare} onChange={e => { invalidate(); setCompare(e.target.checked); }} />与当前已保存章节比较{chapter ? `「${chapter.title}」v${chapter.version}` : '（请先选择章节）'}</label>
        <Button disabled={action.busy || !available || !validSamples || !operations.length || (compare && !chapter)} onClick={() => void action.run(async isCurrent => { await api.analyze({ style_id: selected.id, expected_style_version: selected.version, language, samples, operations, ...(compare && chapter ? { comparison: { chapter_id: chapter.id, expected_version: chapter.version, language } } : {}) }); if (isCurrent()) analyses.reload(); }, '分析已保存。统计仅描述这些样本，不代表文学质量。')}>分析所选已保存样本</Button>
      </>}
      <ResourceState loading={analyses.loading} error={analyses.error} />
      {!!analyses.error && <Button disabled={analyses.loading || action.busy} onClick={analyses.reload}>重新读取分析报告</Button>}
      {!analyses.loading && !analyses.error && !analyses.data?.items.length && <EmptyState title="还没有文风统计" detail="选定档案、样本与用途后，主动运行一次分析。页面打开时不会分析正文。" />}
      {available && !analyses.loading && !analyses.error && analyses.data?.items.filter(row => !selectedId || row.style_id === selectedId).map(row => <AnalysisReport key={row.id} row={row} title={catalog.data!.styles.find(style => style.id === row.style_id)?.title} onNavigate={onNavigate} />)}
    </Panel>
    <Panel title="核对准确风格输入">
      <p>此处仅预览已有写作服务实际接收的风格指令。参考规则保留在档案中，不会注入请求；生成仍需在写作区单独发起。</p>
      {selected?.status !== 'APPROVED' && <StatusMessage>请先选择已审核的风格档案。</StatusMessage>}
      <div className="experimental-grid"><Field label="预览写作用途"><select disabled={action.busy} value={operation} onChange={e => { invalidate(); setOperation(e.target.value as StyleOperation); }}>{(catalog.data?.operations || ['continue']).map(value => <option key={value} value={value}>{styleOperationLabels[value]}</option>)}</select></Field><Field label="预览关联人物（可选）"><select disabled={action.busy} value={characterId} onChange={e => { invalidate(); setCharacterId(e.target.value); }}><option value="">{selected?.character_ids.length ? '请选择档案关联人物' : '通用风格'}</option>{available && catalog.data!.characters.filter(row => selected?.character_ids.includes(row.id)).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field></div>
      <Button disabled={action.busy || !available || selected?.status !== 'APPROVED' || selected.stale || (!!selected.character_ids.length && !characterId)} onClick={() => void action.run(async isCurrent => { invalidate(); const ticket = epoch.current; const result = await api.previewStyle(selected!, operation, characterId || null); if (isCurrent() && ticket === epoch.current) setPreview(result); }, '准确风格输入已读取，请核对后再选择使用。')}>预览风格注入内容</Button>
      {safePreview && <section className="experimental-record" aria-label="准确风格输入预览"><Badge>{safePreview.privacy_level} · 档案 v{safePreview.style_version}</Badge><Field label="将进入请求的风格指令"><textarea readOnly value={safePreview.instructions} /></Field>{safePreview.rules.length > 0 && <><h4>仅供参考的规则</h4><ul>{safePreview.rules.map((rule, index) => <li key={index}>{rule}</li>)}</ul></>}<p>用途：{styleOperationLabels[safePreview.operation]} · 未调用模型</p><label className="experimental-check"><input type="checkbox" disabled={action.busy || used} checked={reviewed} onChange={e => setReviewed(e.target.checked)} />已核对风格指令、用途与版本</label><Button disabled={!onUseStyle || !reviewed || action.busy || used} onClick={() => void action.run(async isCurrent => { const ticket = epoch.current; const expected = safePreview; try { const current = await api.previewStyle(selected!, operation, characterId || null); if (!isCurrent() || ticket !== epoch.current) return; if (current.preview_digest !== expected.preview_digest || current.style_id !== expected.style_id || current.style_version !== expected.style_version || current.operation !== expected.operation || current.character_id !== expected.character_id || current.instructions !== expected.instructions || current.context_injection !== expected.context_injection || current.rules_usage !== expected.rules_usage || current.model_called) { invalidate(); throw new Error('风格输入已变化，请重新预览。'); } setUsed(true); onUseStyle?.(current.style_id); } catch (error) { if (isCurrent()) invalidate(); throw error; } }, '已将此风格交给写作区。发起生成前仍会核对来源与权限。')}>明确使用此风格准备写作</Button>{!onUseStyle && <StatusMessage>当前宿主未接入风格选择，仍可核对预览。</StatusMessage>}</section>}
    </Panel>
  </section>;
}
function AnalysisReport({ row, title, onNavigate }: { row: StyleAnalysis; title?: string; onNavigate?: Props['onNavigate'] }) {
  if (row.stale) return <article className="experimental-record" aria-label={`文风报告 ${row.id}`}><strong>{title || '风格档案'} · 历史报告</strong><Badge tone="warning">来源已变化</Badge><StatusMessage tone="warning">旧来源的派生指标已隐藏。核对最新章节与档案版本，再重新选择样本创建报告。</StatusMessage>{row.limitations?.map((text, index) => <p key={index}>{text}</p>)}</article>;
  const labels: Record<string, string> = { sentence_count: '句子数', paragraph_count: '段落数', unit_count: row.language === 'zh' ? '汉字数（非分词）' : '英文词单元数', dialogue_characters: '对话字符数', characters: '字符数' };
  return <article className="experimental-record" aria-label={`文风报告 ${row.id}`}><div className="experimental-actions"><strong>{title || '风格档案'} · 样本统计</strong><Badge tone={row.stale ? 'warning' : 'neutral'}>{row.stale ? '来源已变化，请重新分析' : '已完成'}</Badge></div><p>档案 v{row.style_version} · 方法 {row.method_version} · {row.language === 'zh' ? '中文' : '英文'}</p><dl className="experimental-meta">{Object.entries(labels).filter(([key]) => typeof row.metrics[key] === 'number').map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{String(row.metrics[key])}</dd></div>)}</dl>{row.limitations?.length > 0 && <ul>{row.limitations.map((text, index) => <li key={index}>{text}</li>)}</ul>}{row.stale && <StatusMessage tone="warning">旧统计仅供历史参考。核对最新章节与档案版本后重新选择样本，创建新报告。</StatusMessage>}<Details value={{ metrics: row.metrics, samples: row.samples, comparison: row.comparison }} label="核对原始计数、范围与比较数据" />{onNavigate && <div className="experimental-actions">{row.samples.map((sample, index) => <Button key={`${sample.chapter_id}:${index}`} disabled={row.stale} onClick={() => onNavigate({ kind: 'chapter', id: sample.chapter_id, version: sample.expected_version })}>打开样本来源 {index + 1}</Button>)}</div>}</article>;
}
