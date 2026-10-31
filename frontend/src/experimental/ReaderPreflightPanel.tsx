import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import type { WorkspaceNavigation } from './uxClient';
import { Field, ResourceState, useAction, useResource } from './shared';
import { readerPreflightClient, type ReaderSettings, type ReadAnchor, type DraftStatus, type PreflightResult } from './readerPreflightClient';
import './readerPreflight.css';
export type ReaderPreflightProps = { client: ExperimentalClient; localDraftState?: DraftStatus[]; onNavigate?: (value: WorkspaceNavigation) => void };
let sequence = 0;
export function ReaderPreflightPanel(props: ReaderPreflightProps) {
  const identity = useMemo(() => ++sequence, [props.client]);
  return <ReaderBody key={identity} {...props} />;
}
function ReaderBody({ client, localDraftState = [], onNavigate }: ReaderPreflightProps) {
  const domId = useId();
  const api = useMemo(() => readerPreflightClient(client), [client]);
  const settings = useResource(signal => api.settings(signal), [api]);
  const reading = useResource(signal => api.read(signal), [api]);
  const proof = useResource(signal => api.proof(signal), [api]);
  const [editing, setEditing] = useState<ReaderSettings>();
  const [saved, setSaved] = useState<ReaderSettings>();
  const [width, setWidth] = useState('768'), [annotations, setAnnotations] = useState(true);
  const [anchor, setAnchor] = useState<ReadAnchor>(), [note, setNote] = useState(''), [ignore, setIgnore] = useState('');
  const [find, setFind] = useState(''), [replacement, setReplacement] = useState(''), [kind, setKind] = useState<'naming' | 'replacement'>('naming');
  const [format, setFormat] = useState('docx'), [report, setReport] = useState<PreflightResult>();
  const [reportState, setReportState] = useState('');
  const alive = useRef(true), initialized = useRef(false), epoch = useRef(0), noteEpoch = useRef(0);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  useEffect(() => { if (settings.data) { setSaved(settings.data); if (!initialized.current) { initialized.current = true; setEditing(settings.data); } } }, [settings.data]);
  const action = useAction();
  const reload = () => { epoch.current++; noteEpoch.current++; setAnchor(undefined); setReport(undefined); reading.reload(); proof.reload(); settings.reload(); };
  const setResult = (result: ReaderSettings) => { if (!alive.current) return; setSaved(result); setEditing(previous => previous ? { ...previous, version: result.version } : result); settings.reload(); };
  const open = (target: ReadAnchor) => action.run(async () => { const ticket = ++epoch.current; const result = await api.open(target); if (alive.current && ticket === epoch.current) onNavigate?.(result); }, '已核对来源并请求打开准确位置。');
  const draftKey = JSON.stringify(localDraftState);
  const stale = report && (report.source_digest !== reading.data?.source_digest || report.checked_format !== format || reportState !== draftKey);
  const busy = action.busy || settings.loading || !!settings.error;
  return <section className="experimental-section" aria-label="阅读校对与发布预检">
    <div className="experimental-actions"><h3>阅读与发布预检</h3><Badge>本地规则 · 不调用模型</Badge><Button onClick={reload} disabled={action.busy}>核对当前来源</Button></div>
    <ResourceState loading={reading.loading} error={reading.error} empty={!reading.data?.chapters.length} />
    {reading.data && !reading.data.branch_sources_available && <StatusMessage tone="warning">分支章节来源不可用，未借用主分支正文。</StatusMessage>}
    <Panel title="连贯阅读">
      <p>仅展示已保存正文。设备宽度是软件内排版模拟，未在 Word、EPUB 阅读器或 PDF 查看器验证。</p>
      <Field label="模拟阅读宽度"><select value={width} onChange={e => setWidth(e.target.value)}><option value="390">手机 390px</option><option value="768">平板 768px</option><option value="960">页面 960px</option></select></Field>
      <label><input type="checkbox" checked={annotations} onChange={e => setAnnotations(e.target.checked)} />显示个人注释层</label>
      {!reading.loading && !reading.error && <>
        <nav aria-label="阅读章节目录" className="experimental-actions">{reading.data?.chapters.map((chapter, index) => <Button key={chapter.id} onClick={() => document.getElementById(`reader-${domId}-${index}`)?.focus()}>{chapter.title}</Button>)}</nav>
        <div className="reader-simulation" style={{ maxWidth: Number(width) }}>
          {reading.data?.chapters.map((chapter, index) => <article key={chapter.id} id={`reader-${domId}-${index}`} tabIndex={-1} className="reader-chapter">
            <h3>{chapter.title} <Badge>v{chapter.version}</Badge></h3>
            {chapter.paragraphs.map(p => <section key={p.index} aria-label={`第 ${p.index + 1} 段`}>
              <p className="reader-prose">{p.text || '（空段落）'}</p>
              <div className="experimental-actions"><Button disabled={!onNavigate || action.busy} onClick={() => open({ chapter_id: chapter.id, revision: chapter.revision, offset: p.offset, quote: Array.from(p.text).slice(0, 2000).join('') })}>编辑器打开第 {p.index + 1} 段</Button><Button onClick={() => { noteEpoch.current++; setAnchor({ chapter_id: chapter.id, revision: chapter.revision, offset: p.offset, quote: Array.from(p.text).slice(0, 2000).join('') }); setNote(''); }}>注释第 {p.index + 1} 段</Button></div>
              {annotations && reading.data?.annotations.filter(a => a.chapter_id === chapter.id && a.offset === p.offset && !a.stale).map(a => <p key={a.id} className="reader-note">注释：{a.note}</p>)}
            </section>)}
          </article>)}
        </div>
        {annotations && reading.data?.annotations.filter(a => a.stale).map(a => <StatusMessage key={a.id} tone="warning">注释来源已过期，未套用到新段落：{a.note}</StatusMessage>)}
      </>}
      {anchor && <><Field label="段落注释"><textarea maxLength={2000} value={note} onChange={e => { noteEpoch.current++; setNote(e.target.value); }} /></Field><div className="experimental-actions"><Button disabled={!note.trim() || busy || !saved} onClick={() => action.run(async () => { const ticket = noteEpoch.current; setResult(await api.annotate(saved!.version, anchor, note)); if (alive.current) { if (ticket === noteEpoch.current) setAnchor(undefined); reading.reload(); } }, '注释已保存；正文未改。')}>保存注释</Button><Button onClick={() => { noteEpoch.current++; setAnchor(undefined); }}>取消注释</Button></div></>}
    </Panel>
    <Panel title="可配置校对规则与声明">
      <ResourceState loading={settings.loading} error={settings.error} />
      {editing && <>
        <label><input type="checkbox" checked={editing.rules.punctuation} onChange={e => setEditing({ ...editing, rules: { ...editing.rules, punctuation: e.target.checked } })} />检查连续标点</label>
        <label><input type="checkbox" checked={editing.rules.repeated_words} onChange={e => setEditing({ ...editing, rules: { ...editing.rules, repeated_words: e.target.checked } })} />检查连续英文重复词（中文请添加字面规则）</label>
        <div className="experimental-grid"><Field label="字面规则类型"><select value={kind} onChange={e => setKind(e.target.value as typeof kind)}><option value="naming">人物称谓</option><option value="replacement">敏感词字面替换建议</option></select></Field><Field label="查找字面文字"><input value={find} maxLength={80} onChange={e => setFind(e.target.value)} /></Field><Field label="建议替换文字"><input value={replacement} maxLength={80} onChange={e => setReplacement(e.target.value)} /></Field></div>
        <Button disabled={!find || editing.rules.literals.length >= 30} onClick={() => { setEditing({ ...editing, rules: { ...editing.rules, literals: [...editing.rules.literals, { kind, find, suggest: replacement }] } }); setFind(''); setReplacement(''); }}>添加字面规则</Button>
        {editing.rules.literals.map((rule, index) => <p key={index}>{rule.find} → {rule.suggest || '删除建议'} <Button onClick={() => setEditing({ ...editing, rules: { ...editing.rules, literals: editing.rules.literals.filter((_, i) => i !== index) } })}>移除规则 {index + 1}</Button></p>)}
        <Field label="正文与素材许可声明"><textarea maxLength={2000} value={editing.license_declaration} onChange={e => setEditing({ ...editing, license_declaration: e.target.value })} /></Field>
        <Field label="字体来源与限制声明"><textarea maxLength={1000} value={editing.font_declaration} onChange={e => setEditing({ ...editing, font_declaration: e.target.value })} /></Field>
        <div className="experimental-actions"><Button disabled={busy || !saved || editing.version !== saved.version} onClick={() => action.run(async () => { setResult(await api.save(editing)); proof.reload(); setReport(undefined); }, '规则与作者声明已保存；不会自动替换正文。')}>保存规则与声明</Button><Button disabled={settings.loading || !saved} onClick={() => setEditing(saved)}>放弃未保存规则</Button></div>
      </>}
      {editing && saved && editing.version !== saved.version && <StatusMessage tone="warning">服务器规则版本已变化。当前输入保留，但不能覆盖新版本；核对后使用“放弃未保存规则”恢复服务器版本。</StatusMessage>}
      <p>规则只是建议，最多 30 条字面匹配与 300 条结果，不支持可执行脚本或正则输入。许可声明不等同法律审核。</p>
      <ResourceState loading={proof.loading} error={proof.error} empty={!proof.data?.items.length} />
      {proof.data?.truncated && <StatusMessage tone="warning">结果达到 300 条上限，不能据此宣称完整校对。</StatusMessage>}
      <Field label="忽略建议的理由"><input maxLength={1000} value={ignore} onChange={e => setIgnore(e.target.value)} /></Field>
      {!proof.loading && !proof.error && proof.data?.items.map(f => <article key={f.id} className="experimental-record"><p>第 {f.paragraph + 1} 段：{f.quote} · {f.explanation}</p>{f.ignored_reason ? <p>已忽略：{f.ignored_reason}</p> : <Button disabled={!ignore.trim() || busy || !saved} onClick={() => action.run(async () => { setResult(await api.ignore(saved!.version, f.id, ignore)); proof.reload(); }, '已记录忽略理由。')}>忽略建议 {f.quote}</Button>}<Button disabled={!onNavigate || action.busy} onClick={() => open({ chapter_id: f.chapter_id, revision: f.revision, offset: f.offset, quote: f.quote })}>定位引用 {f.quote}</Button></article>)}
    </Panel>
    <Panel title="发布前只读检查">
      <Field label="目标导出格式"><select value={format} onChange={e => setFormat(e.target.value)}>{['docx', 'epub', 'pdf', 'markdown', 'txt'].map(f => <option key={f}>{f}</option>)}</select></Field>
      <p>只读检查不会保存正文、接受草稿、创建导出或调用模型。实际导出仍由原导出中心捕获自己的不可变快照。未覆盖来源会明确标为 UNKNOWN。</p>
      <Button disabled={action.busy || reading.loading || !!reading.error} onClick={() => action.run(async () => { const result = await api.check(format, localDraftState); if (alive.current) { setReport(result); setReportState(draftKey); } }, '只读检查已完成。请检查覆盖范围与来源版本。')}>运行发布预检</Button>
      {stale && <StatusMessage tone="warning">输入状态或已读取来源已变化，请重新预检。关闭面板后的检查结果不会继续生效。</StatusMessage>}
      {report && <><p>{report.has_integrity_blockers ? '存在文件完整性阻塞' : '已检查范围内未发现文件完整性阻塞'}。空章节、待审草稿和规则建议不强制禁止导出。</p><ul>{report.coverage.map(c => <li key={c.area}>{c.area}：{c.state}</li>)}</ul>{report.findings.map((f, index) => <article key={index} className="experimental-record"><Badge tone={f.severity === 'BLOCKER' ? 'error' : f.severity === 'WARNING' ? 'warning' : 'neutral'}>{f.severity}</Badge> {f.message}<Button disabled={!onNavigate} onClick={() => onNavigate?.(f.chapter_id ? { kind: 'chapter', id: f.chapter_id, anchor: { offset: 0, scroll: 0 } } : { kind: 'feature', id: f.feature, feature: f.feature })}>打开问题入口 {index + 1}</Button></article>)}</>}
      <Button disabled={!onNavigate} onClick={() => onNavigate?.({ kind: 'feature', id: 'exports', feature: 'exports' })}>打开原导出中心</Button>
    </Panel>
    {action.feedback}
  </section>;
}
