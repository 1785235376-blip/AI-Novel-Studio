import { useEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { Field, ResourceState, useAction, useResource } from './shared';
import { multilingualEditionsClient, type AlignmentPreview, type EditionCreate, type EditionExportPreview, type EditionSegment, type LanguageEdition, type SegmentPreview, type TermInput, type TermIssue } from './multilingualEditionsClient';
import './multilingualEditions.css';
import { LanguageTranslationPanel } from './LanguageTranslationPanel';
let sequence = 0;
export function MultilingualEditionsPanel({ client }: { client: ExperimentalClient }) {
  const identity = useMemo(() => ++sequence, [client]);
  return <EditionsBody key={identity} client={client} />;
}
type EditionApi = ReturnType<typeof multilingualEditionsClient>;
function EditionsBody({ client }: { client: ExperimentalClient }) {
  const api = useMemo(() => multilingualEditionsClient(client), [client]);
  const catalog = useResource(signal => api.catalog(signal), [api]);
  const editions = useResource(signal => api.list(signal), [api]);
  const [title, setTitle] = useState(''), [sourceLanguage, setSourceLanguage] = useState('zh-Hant'), [targetLanguage, setTargetLanguage] = useState('en');
  const [direction, setDirection] = useState<EditionCreate['direction']>('auto'), [font, setFont] = useState<EditionCreate['font']>('serif'), [style, setStyle] = useState('');
  const [chapters, setChapters] = useState<string[]>([]), [selected, setSelected] = useState<LanguageEdition>();
  const [dirty, setDirty] = useState(false), [index, setIndex] = useState(0), [refresh, setRefresh] = useState<AlignmentPreview>();
  const alive = useRef(true), epoch = useRef(0); const action = useAction();
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  const updated = (value: LanguageEdition) => { if (alive.current) { epoch.current++; if (selected?.id !== value.id) setIndex(0); setSelected(value); setRefresh(undefined); editions.reload(); } };
  const perform = (operation: () => Promise<LanguageEdition>, message: string) => void action.run(async () => { const ticket = epoch.current; const value = await operation(); if (alive.current && ticket === epoch.current) updated(value); }, message);
  const choose = (value: LanguageEdition) => { epoch.current++; setSelected(value); setIndex(0); setRefresh(undefined); setDirty(false); };
  const segment = selected?.segments?.[index];
  return <section className="experimental-section" aria-label="多语言版本与术语">
    <Panel title="独立语言版本"><p>手工双语编辑、术语检查与逐段审核。译文保存在独立语言版本中，原稿和原稿历史不会改变。</p>
      <StatusMessage>模型翻译需先选择已配置本地路线并核对本段精确请求。手工编辑无需模型；不会自动重译，术语检查不证明语言质量。</StatusMessage>
      <ResourceState loading={catalog.loading} error={catalog.error} empty={!catalog.data?.chapters.length} />
      {!catalog.loading && !catalog.error && !catalog.data?.branch_sources_available && <StatusMessage tone="warning">当前分支没有独立正文读取权限。请回到具有原稿权限的范围，不会借用其他分支正文。</StatusMessage>}
      <div className="experimental-grid"><Field label="语言版本名称"><input value={title} maxLength={160} onChange={e => setTitle(e.target.value)} /></Field><Field label="原文语言代码"><input value={sourceLanguage} maxLength={64} onChange={e => setSourceLanguage(e.target.value)} /></Field><Field label="目标语言代码"><input value={targetLanguage} maxLength={64} onChange={e => setTargetLanguage(e.target.value)} /></Field>
        <Field label="目标文字方向"><select value={direction} onChange={e => setDirection(e.target.value as EditionCreate['direction'])}><option value="auto">按语言推断</option><option value="ltr">从左向右 LTR</option><option value="rtl">从右向左 RTL</option></select></Field>
        <Field label="目标字体回退"><select value={font} onChange={e => setFont(e.target.value as EditionCreate['font'])}><option value="serif">系统衬线字体</option><option value="sans-serif">系统无衬线字体</option><option value="monospace">系统等宽字体</option></select></Field></div>
      <p>例如 zh-Hant、en、ar。使用系统字体回退，未验证所有文字的字形覆盖。</p>
      <Field label="翻译风格说明"><textarea value={style} maxLength={2000} onChange={e => setStyle(e.target.value)} /></Field>
      {!catalog.loading && !catalog.error && <fieldset className="multilingual-chapters"><legend>选择原稿章节，最多 20 章 / 500 个非空段落</legend>{catalog.data?.chapters.map(c => <label className="experimental-check" key={c.id}><input type="checkbox" checked={chapters.includes(c.id)} disabled={action.busy || (!chapters.includes(c.id) && chapters.length >= 20)} onChange={e => setChapters(old => e.target.checked ? [...old, c.id] : old.filter(id => id !== c.id))} />{c.title} · v{c.version}</label>)}</fieldset>}
      <div className="experimental-actions"><Button disabled={action.busy || dirty || catalog.loading || !!catalog.error || !title.trim() || !chapters.length} onClick={() => perform(() => api.create({ title, source_language: sourceLanguage, target_language: targetLanguage, direction, font, style_note: style, chapters: chapters.map(id => ({ chapter_id: id, chapter_version: catalog.data!.chapters.find(c => c.id === id)!.version })) }), '独立语言版本已建立，原稿未修改。')}>创建语言版本</Button><Button disabled={catalog.loading || action.busy} onClick={catalog.reload}>刷新原稿章节</Button></div>
    </Panel>
    {action.feedback}
    {dirty && <StatusMessage tone="warning">译文输入尚未保存。先保存草稿或还原输入，再切换版本、段落或刷新。</StatusMessage>}
    <Panel title="语言版本记录"><Button disabled={editions.loading || action.busy || dirty} onClick={editions.reload}>刷新语言版本列表</Button><ResourceState loading={editions.loading} error={editions.error} empty={!editions.data?.items.length} />
      {!editions.loading && !editions.error && editions.data?.items.map(e => <div className="experimental-actions" key={e.id}><Button disabled={action.busy || dirty} aria-pressed={selected?.id === e.id} onClick={() => choose(e)}>{e.title || '待更新语言版本'} · {e.target_language} · v{e.version}</Button><Badge tone={e.stale ? 'warning' : 'neutral'}>{e.stale ? '来源已变化' : e.status}</Badge></div>)}
      {editions.data?.truncated && <StatusMessage>仅显示最近 50 个语言版本。</StatusMessage>}
    </Panel>
    {selected && <>
      <Panel title={selected.title || '待更新语言版本'}><div className="experimental-actions"><Badge>{selected.target_language} · {selected.direction.toUpperCase()} · v{selected.version}</Badge><Button disabled={action.busy || dirty} onClick={() => perform(() => api.get(selected), '已读取当前版本；冲突时先核对后再保存。')}>刷新当前语言版本</Button></div>
        {selected.stale ? <><StatusMessage tone="warning">原稿版本、段落或隐私已改变。旧译文保留在受保护的版本历史中，当前停止展示和采用。重新对齐后可查看归档译文，再人工复制为新草稿。不会偷偷重译。</StatusMessage>
          <Button disabled={action.busy} onClick={() => void action.run(async () => { const ticket = epoch.current; const value = await api.refreshPreview(selected); if (alive.current && ticket === epoch.current) setRefresh(value); }, '已检查当前来源，仅预览，尚未更新。')}>预览重新对齐</Button>
          {refresh && <section aria-label="重新对齐预览"><p>保留原位置且内容完全一致的 {refresh.retained_exact} 段；新增或改变 {refresh.new_or_changed} 段；旧记录归档 {refresh.archived_old} 段。全部重新审核。不会猜测移动段落的位置。</p><Button disabled={action.busy} onClick={() => perform(() => api.refresh(selected, refresh), '已重新绑定当前来源；改变的段落留空，所有译文需要再次审核。')}>确认重新对齐并重新审核</Button></section>}</> : <>
          <p>风格说明：{selected.style_note || '未指定'}</p>
          {selected.checks && <StatusMessage>段落对齐 {selected.checks.aligned ? '通过' : '待修复'}；缺失译文 {selected.checks.missing.length} 段；待批准 {selected.checks.pending.length} 段；术语问题 {selected.checks.terminology.length} 项。</StatusMessage>}
          <Field label="编辑译文段落"><select disabled={dirty || action.busy} value={index} onChange={e => setIndex(Number(e.target.value))}>{selected.segments?.map((s, i) => <option key={s.id} value={i}>第 {i + 1} 段 · 原稿 v{s.source_version} · {s.status}</option>)}</select></Field>
          {!!selected.archived_segments?.length && <details><summary>查看归档译文，仅供人工恢复（{selected.archived_segments.length} 段）</summary><p>这些译文绑定旧来源，只能人工复制到当前段落后重新保存、检查和审核。它们不参与导出。</p>{selected.archived_segments.map((old, i) => <article className="experimental-record" key={i}><p>旧源 v{old.source_version} · 段落路径 {old.path.join('.')}</p><Field label={`归档译文 ${i + 1}`}><textarea readOnly value={old.target_text} lang={selected.target_language} dir={selected.direction} /></Field>{old.note && <p>{old.note}</p>}</article>)}</details>}
          {segment && <SegmentEditor key={`${selected.id}:${segment.id}`} api={api} edition={selected} segment={segment} number={index + 1} busy={action.busy} perform={perform} onDirty={setDirty} />}
        </>}
      </Panel>
      {!selected.stale && <><Terminology api={api} edition={selected} busy={action.busy || dirty} perform={perform} /><EditionExportPanel key={selected.id} api={api} edition={selected} blocked={action.busy || dirty} /></>}
    </>}
  </section>;
}
type Performer = (operation: () => Promise<LanguageEdition>, message: string) => void;
function Issues({ issues }: { issues: TermIssue[] }) {
  const names: Record<string, string> = { TERM_REQUIRED: '缺少批准译法', TERM_FORBIDDEN: '含有禁用译法', RULE_CONFLICT: '批准规则相互冲突', TRANSLATION_MISSING: '译文缺失' };
  return <ul>{issues.map((issue, i) => <li key={i}>{names[issue.code] || issue.code}{issue.term ? `：${issue.term}` : ''}{issue.expected ? ` → ${issue.expected}` : ''}{issue.found ? `：${issue.found}` : ''}</li>)}</ul>;
}
function SegmentEditor({ api, edition, segment, number, busy, perform, onDirty }: { api: EditionApi; edition: LanguageEdition; segment: EditionSegment; number: number; busy: boolean; perform: Performer; onDirty: (dirty: boolean) => void }) {
  const [text, setText] = useState(segment.target_text), [note, setNote] = useState(segment.note), [preview, setPreview] = useState<SegmentPreview>(), [approved, setApproved] = useState(false);
  const action = useAction(); const alive = useRef(true), epoch = useRef(0);
  const saved = useRef({ text: segment.target_text, note: segment.note });
  useEffect(() => {
    if (text === saved.current.text && note === saved.current.note) { setText(segment.target_text); setNote(segment.note); }
    saved.current = { text: segment.target_text, note: segment.note };
  }, [edition.version, segment.target_text, segment.note]);
  const dirty = text !== segment.target_text || note !== segment.note;
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn); return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  useEffect(() => { epoch.current++; setPreview(undefined); setApproved(false); }, [edition.version, text, note]);
  const disabled = busy || action.busy;
  return <article className="experimental-section" aria-label={`第 ${number} 段双语编辑`}>
    <Badge>{segment.status}</Badge><p>原稿 v{segment.source_version} · 段落路径 {segment.path.join('.')} · UTF-16 位置 {segment.from_pos}–{segment.to_pos}</p>
    <div className="experimental-grid multilingual-columns"><section><h4>原文</h4><p className="multilingual-prose" lang={edition.source_language} dir="auto">{segment.source_text}</p></section><section><Field label={`第 ${number} 段译文`}><textarea className={`multilingual-prose multilingual-font-${edition.font}`} lang={edition.target_language} dir={edition.direction} value={text} maxLength={20000} disabled={disabled} onChange={e => setText(e.target.value)} /></Field></section></div>
    <Field label="本段审核说明"><textarea value={note} maxLength={1000} disabled={disabled} onChange={e => setNote(e.target.value)} /></Field>
    <div className="experimental-actions"><Button disabled={disabled || !dirty} onClick={() => perform(() => api.save(edition, segment, text, note), '译文草稿已保存，原稿未修改。')}>保存本段草稿</Button><Button disabled={disabled || !dirty} onClick={() => { setText(segment.target_text); setNote(segment.note); }}>还原未保存输入</Button>
      <Button disabled={disabled || dirty || !text.trim() || !['DRAFT', 'REJECTED'].includes(segment.status)} onClick={() => perform(() => api.review(edition, segment, 'submit'), '本段已进入待审。')}>提交本段审核</Button>
      <Button disabled={disabled || dirty || segment.status !== 'REVIEW'} onClick={() => void action.run(async () => { const ticket = ++epoch.current; const value = await api.preview(edition, segment); if (alive.current && ticket === epoch.current) { setPreview(value); setApproved(false); } }, '术语预检已完成；语言质量仍需人工审核。')}>预检本段术语与版本</Button>
      <Button disabled={disabled || dirty || segment.status !== 'REVIEW'} onClick={() => perform(() => api.review(edition, segment, 'reject'), '本段已退回，译文保留。')}>退回本段</Button>
      <Button disabled={disabled || dirty || !['ACCEPTED', 'REJECTED'].includes(segment.status)} onClick={() => perform(() => api.review(edition, segment, 'reopen'), '本段已重新打开为草稿。')}>重新打开本段</Button></div>
    {!!segment.issues.length && <Issues issues={segment.issues} />}
    {preview && <section aria-label="本段接受预览"><Issues issues={preview.issues} /><label className="experimental-check"><input type="checkbox" disabled={!preview.can_accept || disabled || dirty} checked={approved} onChange={e => setApproved(e.target.checked)} />已人工核对本段译文、术语与源版本</label><Button disabled={disabled || dirty || !approved || !preview.can_accept} onClick={() => perform(() => api.review(edition, segment, 'accept', preview), '仅本段译文已接受。原稿仍保持原样。')}>确认仅接受本段译文</Button></section>}
    <LanguageTranslationPanel key={`${edition.id}:${segment.id}:${edition.version}`} api={api} edition={edition} segment={segment} blocked={disabled || dirty} perform={perform} />
    {action.feedback}
  </article>;
}
const split = (value: string) => value.split('\n').map(t => t.trim()).filter(Boolean);
function Terminology({ api, edition, busy, perform }: { api: EditionApi; edition: LanguageEdition; busy: boolean; perform: Performer }) {
  const [source, setSource] = useState(''), [preferred, setPreferred] = useState(''), [sourceAliases, setSourceAliases] = useState(''), [targetAliases, setTargetAliases] = useState(''), [forbidden, setForbidden] = useState('');
  const [strategy, setStrategy] = useState<TermInput['strategy']>('meaning'), [category, setCategory] = useState<TermInput['category']>('term'), [match, setMatch] = useState<TermInput['match']>('substring');
  return <Panel title="批准术语与别名"><p>仅批准规则参与校验。音译 / 意译由作者指定确切译法，不自动判断语言质量。规则改变会将已接受译文退回审核。</p>
    <div className="experimental-grid"><Field label="源术语"><input value={source} maxLength={160} onChange={e => setSource(e.target.value)} /></Field><Field label="首选译法"><input value={preferred} maxLength={160} onChange={e => setPreferred(e.target.value)} /></Field>
      <Field label="术语类别"><select value={category} onChange={e => setCategory(e.target.value as TermInput['category'])}><option value="term">术语</option><option value="character">人物 / 别名</option><option value="title">称谓</option></select></Field><Field label="翻译策略"><select value={strategy} onChange={e => setStrategy(e.target.value as TermInput['strategy'])}><option value="meaning">意译</option><option value="transliteration">指定音译</option><option value="preserve">保留原词</option></select></Field>
      <Field label="术语匹配"><select value={match} onChange={e => setMatch(e.target.value as TermInput['match'])}><option value="substring">字面子串，适合中文</option><option value="word">完整词边界，区分大小写</option></select></Field></div>
    <div className="experimental-grid"><Field label="源别名，每行一个"><textarea value={sourceAliases} onChange={e => setSourceAliases(e.target.value)} maxLength={3200} /></Field><Field label="允许译名，每行一个"><textarea value={targetAliases} onChange={e => setTargetAliases(e.target.value)} maxLength={3200} /></Field><Field label="禁用译法，每行一个"><textarea value={forbidden} onChange={e => setForbidden(e.target.value)} maxLength={3200} /></Field></div>
    <Button disabled={busy || !source.trim() || !preferred.trim()} onClick={() => perform(() => api.addRule(edition, { source_term: source, preferred, source_aliases: split(sourceAliases), target_aliases: split(targetAliases), forbidden: split(forbidden), strategy, category, match, note: '' }), '术语草稿已保存，仍需批准后生效。')}>保存术语草稿</Button>
    {!edition.rules?.length && <p>尚无术语规则，可先编辑译文。</p>}
    {edition.rules?.map(rule => <article className="experimental-record" key={rule.id}><strong><bdi>{rule.source_term}</bdi> → <bdi>{rule.preferred}</bdi></strong><Badge>{rule.status} · v{rule.version} · {rule.strategy}</Badge><p>源别名：{rule.source_aliases.join('、') || '无'}；允许译名：{rule.target_aliases.join('、') || '无'}；禁用：{rule.forbidden.join('、') || '无'}</p>{rule.reviewed_by && <p>审核：{rule.reviewed_by} · {rule.reviewed_at}</p>}<div className="experimental-actions"><Button disabled={busy || rule.status !== 'DRAFT'} onClick={() => perform(() => api.ruleReview(edition, rule, 'approve'), '规则已批准，已接受译文需要重新审核。')}>批准此术语规则</Button><Button disabled={busy || rule.status !== 'APPROVED'} onClick={() => perform(() => api.ruleReview(edition, rule, 'revoke'), '规则已撤销，历史记录保留。')}>撤销此术语规则</Button></div></article>)}
  </Panel>;
}
function EditionExportPanel({ api, edition, blocked }: { api: EditionApi; edition: LanguageEdition; blocked: boolean }) {
  const [format, setFormat] = useState('txt'), [preview, setPreview] = useState<EditionExportPreview>(), [approved, setApproved] = useState(false);
  const [artifact, setArtifact] = useState<{ url: string; filename: string }>();
  const alive = useRef(true), epoch = useRef(0), url = useRef<string>(); const action = useAction();
  const clear = () => { if (url.current) URL.revokeObjectURL(url.current); url.current = undefined; setArtifact(undefined); };
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; if (url.current) URL.revokeObjectURL(url.current); }; }, []);
  useEffect(() => { epoch.current++; setPreview(undefined); setApproved(false); clear(); }, [edition.version, format, blocked]);
  return <Panel title="语言版本导出"><p>仅导出全部已批准且未过期的译文，UTF-8 编码。HTML 含语言代码、方向和字体回退；JSON 保留段落定位。下载不会发布或上传作品。</p>
    <Field label="语言版本导出格式"><select value={format} disabled={action.busy || blocked} onChange={e => setFormat(e.target.value)}><option value="txt">UTF-8 TXT</option><option value="html">UTF-8 HTML（语言与 RTL）</option><option value="json">UTF-8 JSON（段落定位）</option></select></Field>
    <Button disabled={blocked || action.busy} onClick={() => void action.run(async () => { const ticket = ++epoch.current; const result = await api.exportPreview(edition, format); if (alive.current && ticket === epoch.current) { setPreview(result); setApproved(false); } }, '导出预检完成。')}>预检语言版本导出</Button>
    {preview && <section aria-label="语言版本导出预览"><StatusMessage tone={preview.can_export ? 'success' : 'warning'}>缺译 {preview.checks.missing.length} 段；待审 {preview.checks.pending.length} 段；术语问题 {preview.checks.terminology.length} 项。</StatusMessage><label className="experimental-check"><input type="checkbox" checked={approved} disabled={blocked || action.busy || !preview.can_export} onChange={e => setApproved(e.target.checked)} />已核对全部译文，确认生成本地下载</label><Button disabled={blocked || action.busy || !approved || !preview.can_export} onClick={() => void action.run(async () => { const ticket = epoch.current; const result = await api.export(edition, preview); if (alive.current && ticket === epoch.current) { clear(); url.current = URL.createObjectURL(new Blob([result.content], { type: result.mime })); setArtifact({ url: url.current, filename: result.filename }); } }, 'UTF-8 文件已就绪，请下载。')}>生成已审核语言文件</Button></section>}
    {artifact && <a href={artifact.url} download={artifact.filename}>下载 {artifact.filename}</a>}{action.feedback}
  </Panel>;
}
