import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { ApiError } from '../api';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { ErrorMessage, Field, ResourceState, useResource } from './shared';
import { useReviewAction } from './styleReviewClient';
import { researchLibraryClient, readResearchFile, type Citation, type Evidence, type ResearchMeta, type Source, type Note } from './researchLibraryClient';


const recoveryHints: Record<string, string> = {
  RESEARCH_PDF_PARSER_NOT_CONFIGURED: 'PDF 解析依赖未安装。可先导入 UTF-8 TXT/MD，或请管理员核对应用依赖后重试。',
  RESEARCH_PDF_PARSE_FAILED: 'PDF 受损、加密或超出解析资源限制。请在原软件导出未加密的较小文件后重试。',
  RESEARCH_WEB_UNAVAILABLE: '网页未能安全读取，可能是网络、访问限制或不支持的内容。请保留网址，稍后重试或导入你有权保存的本地文本。',
  RESEARCH_WEB_TIMEOUT: '网页读取超时，未写入来源。可以稍后重试；已有离线资料仍可使用。',
  RESEARCH_STORAGE_LIMIT: '当前资料范围达到存储上限。原有资料仍保留，请拆分到另一个项目后导入。',
  RESEARCH_REVISION_LIMIT: '此资料已保留 20 个历史版本。请导出后作为新来源导入；旧版本不会静默丢弃。',
  RESEARCH_SOURCE_LIMIT: '当前范围达到资料数量上限（包含保留的删除记录）。请拆分项目，原有资料不会被覆盖。',
  RESEARCH_UTF8_REQUIRED: '请将文本保存为 UTF-8 编码后重新导入。表单内容已保留。',
  RESEARCH_ORIGINAL_SETTING_REQUIRED: '设定不能直接照搬所选完整原文。请先写出你自己的虚构设定，再核对引用。',
  RESEARCH_REQUEST_LIMIT: '请求超过大小限制。请选取 4 MiB 以内的文件后重试。',
  RESEARCH_FILE_LIMIT: '请选取 4 MiB 以内的非空文件。',
  RESEARCH_EXTRACT_LIMIT: '提取文字超过本次安全限制，请拆分资料后导入。',
};

const emptyMeta = (): ResearchMeta => ({ title: '', author: '', source: '', source_version: '', usage_notes: '', access: 'PRIVATE' });
const citeKey = (c: Citation) => `${c.source_id}:${c.source_version}:${c.paragraph}:${c.page || 0}`;
export function ResearchLibraryPanel({ client }: { client: ExperimentalClient }) {
  const api = useMemo(() => researchLibraryClient(client), [client]);
  const currentApi = useRef(api);
  const isScopeCurrent = (alive: () => boolean) => alive() && currentApi.current === api;
  const sources = useResource(signal => api.sources(signal), [api]);
  const notes = useResource(signal => api.notes(signal), [api]);
  const repairs = useResource(signal => api.noteRepairs(signal), [api]);
  const drafts = useResource(signal => api.drafts(signal), [api]);
  const [selected, setSelected] = useState('');
  const [paragraphPage, setParagraphPage] = useState(0);
  const detail = useResource(signal => selected ? api.source(selected, signal) : Promise.resolve(undefined), [api, selected]);
  const [metadata, setMetadata] = useState(emptyMeta);
  const [editing, setEditing] = useState<Source>();
  const [history, setHistory] = useState<{ row: Source; items: Source[] }>();
  const [archive, setArchive] = useState<Source[]>();
  const [restoreConfirmed, setRestoreConfirmed] = useState(false);
  const [noteEditing, setNoteEditing] = useState<Note>();
  const [noteHistory, setNoteHistory] = useState<Note[]>();
  const [file, setFile] = useState<File>();
  const [url, setUrl] = useState(''), [webConfirmed, setWebConfirmed] = useState(false);
  const [query, setQuery] = useState(''), [results, setResults] = useState<Evidence[]>();
  const [citations, setCitations] = useState<Citation[]>([]), [evidence, setEvidence] = useState<Evidence>();
  const [preview, setPreview] = useState<Evidence[]>();
  const [noteTitle, setNoteTitle] = useState(''), [noteText, setNoteText] = useState('');
  const [settingTitle, setSettingTitle] = useState(''), [settingText, setSettingText] = useState(''), [original, setOriginal] = useState(false);
  const [removeConfirmed, setRemoveConfirmed] = useState(false), [backrefs, setBackrefs] = useState<{ title: string; kind: string; id: string }[]>();
  const epoch = useRef(0), action = useReviewAction();
  useLayoutEffect(() => {
    currentApi.current = api; epoch.current++; setSelected(''); setParagraphPage(0);
    setResults(undefined); setPreview(undefined); setEvidence(undefined); setBackrefs(undefined); setCitations([]);
    setMetadata(emptyMeta()); setEditing(undefined); setFile(undefined); setUrl(''); setWebConfirmed(false);
    setHistory(undefined); setArchive(undefined); setNoteEditing(undefined); setNoteHistory(undefined); setRestoreConfirmed(false);
    setNoteTitle(''); setNoteText(''); setSettingTitle(''); setSettingText(''); setOriginal(false); setRemoveConfirmed(false);
  }, [api]);
  const restricted = [action.error, detail.error, notes.error, drafts.error, repairs.error].some(error => error instanceof ApiError && [401, 403, 404].includes(error.problem.status));
  const available = currentApi.current === api && !sources.loading && !sources.error && !!sources.data && !restricted;
  const current = available && !detail.loading && !detail.error ? detail.data : undefined;
  const conflict = action.error instanceof ApiError && action.error.problem.status === 409;
  const invalidate = () => { epoch.current++; setResults(undefined); setPreview(undefined); setEvidence(undefined); setBackrefs(undefined); setCitations([]); setRemoveConfirmed(false); setHistory(undefined); setArchive(undefined); setNoteHistory(undefined); setRestoreConfirmed(false); };
  const refresh = () => { invalidate(); action.clear(); sources.reload(); detail.reload(); notes.reload(); drafts.reload(); repairs.reload(); };
  const select = (id: string) => { invalidate(); setSelected(id); setParagraphPage(0); };
  const toggleCitation = (ref: Citation) => { epoch.current++; setPreview(undefined); setCitations(values => values.some(c => citeKey(c) === citeKey(ref)) ? values.filter(c => citeKey(c) !== citeKey(ref)) : [...values, ref].slice(0, 20)); };
  const showCitation = (ref: Citation) => action.run(async alive => { const ticket = epoch.current; const value = await api.citation(ref); if (isScopeCurrent(alive) && ticket === epoch.current) setEvidence(value); });
  const lookup = () => action.run(async alive => { const ticket = ++epoch.current; setResults(undefined); setPreview(undefined); const value = await api.search(query); if (isScopeCurrent(alive) && ticket === epoch.current) setResults(value.items); });
  const pendingEdit = editing && sources.data?.items.find(row => row.id === editing.id);
  const changedEdit = !!editing && (!pendingEdit || pendingEdit.version !== editing.version);
  return <section className="experimental-section" aria-label="分层研究资料库">
    <div className="experimental-actions"><h3>研究资料库</h3><Badge>本地检索 · 独立来源层</Badge><Button disabled={action.busy || sources.loading} onClick={refresh}>刷新资料与权限（保留输入）</Button></div>
    <p>Research 保存现实参考；Canon 记录已审核的虚构事实；Draft 保存原创设定草稿；人物知识由独立的角色记录管理。资料不会自动进入正文、Canon 或人物上下文。</p>
    <ResourceState loading={sources.loading} error={sources.error} />
    {!!action.error && <ErrorMessage error={action.error} />}{action.error instanceof ApiError && recoveryHints[action.error.problem.code] && <StatusMessage tone="warning">{recoveryHints[action.error.problem.code]}</StatusMessage>}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
    {(!available && !sources.loading) && <StatusMessage tone="warning">资料暂不可用。请核对会话、项目、分支权限与开关后刷新。你的表单输入仍保留。</StatusMessage>}
    {conflict && <StatusMessage tone="warning">版本或引用已变化。输入已保留，请刷新当前来源后重新选择引用并审核。</StatusMessage>}
    <Panel title="导入明确选择的资料">
      <form className="experimental-form" onSubmit={event => { event.preventDefault(); if (!available || action.busy || !metadata.title.trim()) return; void action.run(async alive => {
        if (editing) { if (file) { const encoded = await readResearchFile(file); if (!isScopeCurrent(alive)) return; await api.replaceFile(editing, metadata, file.name, encoded); } else await api.edit(editing, metadata); if (isScopeCurrent(alive)) { setEditing(undefined); setFile(undefined); refresh(); } }
        else if (file) { const encoded = await readResearchFile(file); if (!isScopeCurrent(alive)) return; await api.importFile(metadata, file.name, encoded); if (isScopeCurrent(alive)) refresh(); }
      }, editing ? file ? '资料新文件版本已保存，旧引用需要重新核对。' : '资料元数据已更新，旧引用需要重新核对。' : '资料已导入本地库。'); }}>
        <fieldset className="experimental-form" disabled={action.busy}>
          <legend>{editing ? '修改所选来源元数据' : '来源与使用说明'}</legend>
          <Field label="资料标题"><input required maxLength={240} value={metadata.title} onChange={e => setMetadata({ ...metadata, title: e.target.value })} /></Field>
          <Field label="资料作者"><input maxLength={160} value={metadata.author} onChange={e => setMetadata({ ...metadata, author: e.target.value })} /></Field>
          <Field label="资料来源或出版信息"><input maxLength={2000} value={metadata.source} onChange={e => setMetadata({ ...metadata, source: e.target.value })} /></Field>
          <Field label="来源版本或版次"><input maxLength={160} value={metadata.source_version} onChange={e => setMetadata({ ...metadata, source_version: e.target.value })} /></Field>
          <Field label="资料使用说明"><textarea maxLength={4000} value={metadata.usage_notes} onChange={e => setMetadata({ ...metadata, usage_notes: e.target.value })} /></Field>
          <Field label="资料可见范围"><select value={metadata.access} onChange={e => setMetadata({ ...metadata, access: e.target.value as ResearchMeta['access'] })}><option value="PRIVATE">仅导入者</option><option value="PROJECT">当前项目与分支中有作者权限的人</option></select></Field>
          {<Field label="选择本地资料文件"><input key={editing?.id || 'new-import'} type="file" accept=".txt,.md,.docx,.pdf,.png,.jpg,.jpeg,.webp" onChange={e => setFile(e.target.files?.[0])} /></Field>}
        </fieldset>
        <p>单文件最多 4 MiB。TXT/MD 使用 UTF-8；DOCX 引用按段落，PDF 按页面和段落。图片或扫描页没有 OCR/视觉适配器时只保存来源，不声称理解内容。</p>
        {editing && <p>不选择新文件时只修改元数据；选择新文件会保留旧版并替换当前内容，旧引用需要重新核对。</p>}
        {changedEdit && <StatusMessage tone="warning">服务器版本已不同，当前输入已保留。{pendingEdit ? <>当前版本 v{pendingEdit.version}：{pendingEdit.title}；作者：{pendingEdit.author || '未填写'}；来源：{pendingEdit.source}；使用说明：{pendingEdit.usage_notes}<Button type="button" disabled={action.busy} onClick={() => setEditing(pendingEdit)}>已核对当前版本，保留输入继续编辑</Button></> : <>原来源已不可用。请核对权限，或退出编辑后另存为新资料。</>}</StatusMessage>}
        <div className="experimental-actions"><Button type="submit" disabled={!available || action.busy || !metadata.title.trim() || (!editing && (!file || file.size > 4 * 1024 * 1024 || file.size === 0)) || changedEdit}>{editing ? file ? '保存资料新文件版本' : '保存资料元数据' : '导入所选本地文件'}</Button>{editing && <Button type="button" disabled={action.busy} onClick={() => setEditing(undefined)}>保留输入并退出元数据编辑</Button>}</div>
      </form>
      {!editing && <><Field label="明确选择的网页网址"><input type="url" value={url} onChange={e => { setUrl(e.target.value); setWebConfirmed(false); }} /></Field><label className="experimental-check"><input type="checkbox" checked={webConfirmed} onChange={e => setWebConfirmed(e.target.checked)} />我允许本次访问此公开网页；不发送登录信息或绕过访问限制</label><Button disabled={!available || action.busy || !webConfirmed || !/^https?:\/\//.test(url) || !metadata.title.trim()} onClick={() => void action.run(async alive => { await api.fetchWeb(metadata, url); if (isScopeCurrent(alive)) { setWebConfirmed(false); refresh(); } }, '所选公开网页的纯文本已保存。')}>抓取这个网页一次</Button><p>打开资料库不会抓取网页。每次抓取限制时长、大小、类型与重定向，并阻断内网地址。远程图片、脚本与插件不会加载。</p></>}
    </Panel>
    <Panel title="已保存来源">
      {available && !sources.data!.items.length && <EmptyState title="还没有可见资料" detail="选择本地文件后导入，或记录并抓取一个明确选择的公开网页。" />}
      {available && <div className="experimental-list">{sources.data!.items.map(row => <article className="experimental-record" key={row.id}><strong>{row.title}</strong><p>{row.author || '未填写作者'} · v{row.version} · {row.format} · {row.paragraph_count} 段</p><Badge>{row.extraction_status === 'OCR_NOT_CONFIGURED' ? 'OCR / 视觉：未配置' : row.extraction_status === 'TEXT_EXTRACTED' ? '本地可检索文本' : '无可检索文本'}</Badge><Button disabled={action.busy} onClick={() => select(row.id)}>打开来源 {row.title}</Button></article>)}</div>}
      {!!selected && available && <ResourceState loading={detail.loading} error={detail.error} />}
      {current && <article className="experimental-record" aria-label="当前研究来源"><h4>{current.title}</h4><p>访问时间：{current.accessed_at} · 来源版本：{current.source_version || '未填写'} · {current.source}</p><p>{current.usage_notes}</p>{current.warnings.map((text, i) => <StatusMessage key={i} tone="warning">{text}</StatusMessage>)}<div className="experimental-actions"><Button disabled={action.busy} onClick={() => void action.run(async alive => { const ticket = epoch.current; const result = await api.backrefs(current.id); if (isScopeCurrent(alive) && ticket === epoch.current) setBackrefs(result.items); })}>查看当前来源反向引用</Button>{current.origin === 'LOCAL_IMPORT' && <Button disabled={action.busy} onClick={() => void action.run(async alive => { const blob = await api.original(current.id); if (!isScopeCurrent(alive)) return; const href = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = href; link.download = current.filename; link.click(); setTimeout(() => URL.revokeObjectURL(href), 1000); })}>下载所选原始文件</Button>}{current.origin !== 'LEGACY_LIVE' && <Button disabled={action.busy || !!editing} onClick={() => { setEditing(current); setFile(undefined); setMetadata({ title: current.title, author: current.author, source: current.source, source_version: current.source_version, usage_notes: current.usage_notes, access: current.access }); }}>编辑来源元数据</Button>}{current.origin !== 'LEGACY_LIVE' && <Button disabled={action.busy} onClick={() => void action.run(async alive => { const ticket = epoch.current; const result = await api.sourceHistory(current.id); if (isScopeCurrent(alive) && ticket === epoch.current) { setHistory({ row: current, items: result.items }); setRestoreConfirmed(false); } })}>核对来源历史版本</Button>}</div>
        {backrefs && <div aria-label="来源反向引用">{backrefs.length ? backrefs.map(row => <p key={row.id}>{row.kind === 'NOTE' ? '研究笔记' : '设定草稿'}：{row.title}</p>) : <p>没有当前可用的反向引用。</p>}</div>}
        {current.origin === 'LEGACY_LIVE' ? <p>沿用原研究记录，修改或删除请使用现有研究编辑入口。不会抓取它保存的网址。</p> : <><label className="experimental-check"><input type="checkbox" checked={removeConfirmed} onChange={e => setRemoveConfirmed(e.target.checked)} />我知道撤销或删除会使关联检索、笔记、上下文和设定引用失效</label><div className="experimental-actions">{(['revoke', 'delete'] as const).map(kind => <Button key={kind} disabled={action.busy || !removeConfirmed} onClick={() => void action.run(async alive => { await api.remove(current, kind); if (isScopeCurrent(alive)) { select(''); refresh(); } }, '来源已停用，派生引用已失效。')}>{kind === 'revoke' ? '撤销来源访问' : '删除资料来源'}</Button>)}</div></>}
        {current.page_citations?.map(ref => <section className="experimental-record" key={citeKey(ref)}><label className="experimental-check"><input type="checkbox" checked={citations.some(c => citeKey(c) === citeKey(ref))} disabled={action.busy} onChange={() => toggleCitation(ref)} />选择仅页面引用：第 {ref.page} 页（未解析内容）</label><Button disabled={action.busy} onClick={() => void showCitation(ref)}>核对页面引用 {ref.page}</Button></section>)}{(current.paragraphs?.length || 0) > 20 && <div className="experimental-actions"><Button disabled={paragraphPage === 0 || action.busy} onClick={() => setParagraphPage(value => value - 1)}>上一组段落</Button><span>第 {paragraphPage + 1} / {Math.ceil(current.paragraphs!.length / 20)} 组</span><Button disabled={(paragraphPage + 1) * 20 >= current.paragraphs!.length || action.busy} onClick={() => setParagraphPage(value => value + 1)}>下一组段落</Button></div>}{current.paragraphs?.slice(paragraphPage * 20, (paragraphPage + 1) * 20).map(paragraph => <section className="experimental-record" key={paragraph.paragraph}><label className="experimental-check"><input type="checkbox" checked={citations.some(c => citeKey(c) === citeKey(paragraph.citation))} disabled={action.busy || (citations.length >= 20 && !citations.some(c => citeKey(c) === citeKey(paragraph.citation)))} onChange={() => toggleCitation(paragraph.citation)} />选择引用：{paragraph.page ? `第 ${paragraph.page} 页 · ` : ''}第 {paragraph.paragraph} 段</label><p>{paragraph.text}</p><Button disabled={action.busy} onClick={() => void showCitation(paragraph.citation)}>核对原段落 {paragraph.paragraph}</Button></section>)}
      </article>}
    </Panel>
    <Panel title="资料版本与恢复"><p>替换文件或编辑元数据会保存完整历史版本，并使旧引用失效。恢复创建一个新版本，默认仅导入者可见；旧引用不会自动复活。</p><Button disabled={!available || action.busy} onClick={() => void action.run(async alive => { const ticket = epoch.current; const result = await api.archive(); if (isScopeCurrent(alive) && ticket === epoch.current) setArchive(result.items); })}>查看我停用的资料</Button>{available && archive?.map(row => <article className="experimental-record" key={row.id}><strong>{row.title} · {row.status} · v{row.version}</strong><Button disabled={action.busy} onClick={() => void action.run(async alive => { const ticket = epoch.current; const result = await api.sourceHistory(row.id); if (isScopeCurrent(alive) && ticket === epoch.current) { setHistory({ row, items: result.items }); setRestoreConfirmed(false); } })}>查看可恢复版本 {row.title}</Button></article>)}{available && history && <section aria-label="研究来源历史"><h4>{history.row.title} · 当前 v{history.row.version}</h4><label className="experimental-check"><input type="checkbox" checked={restoreConfirmed} onChange={e => setRestoreConfirmed(e.target.checked)} />已核对版本，恢复为新的私有来源版本并使旧引用失效</label>{history.items.map(row => <article className="experimental-record" key={row.version}><p>v{row.version} · {row.title} · {row.status} · {row.source_version}</p><p>Digest：{row.content_sha256} · 原导入时间：{row.accessed_at}</p><Button disabled={action.busy || !restoreConfirmed || row.status !== 'ACTIVE' || row.version === history.row.version} onClick={() => void action.run(async alive => { const value = await api.restoreSource(history.row, row.version); if (isScopeCurrent(alive)) { setSelected(value.id); refresh(); } }, '已恢复为新的私有来源版本。请重新选择引用。')}>恢复来源版本 {row.version}</Button>{row.origin === 'LOCAL_IMPORT' && <Button disabled={action.busy} onClick={() => void action.run(async alive => { const blob = await api.historicalOriginal(row.id, row.version); if (!isScopeCurrent(alive)) return; const href = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = href; link.download = row.filename; link.click(); setTimeout(() => URL.revokeObjectURL(href), 1000); })}>导出来源版本 {row.version}</Button>}</article>)}</section>}</Panel>
    <Panel title="本地检索与可追溯引用"><form className="experimental-form" onSubmit={e => { e.preventDefault(); if (available && query.trim()) void lookup(); }}><Field label="资料检索词"><input maxLength={200} value={query} onChange={e => { epoch.current++; setResults(undefined); setQuery(e.target.value); }} /></Field><Button type="submit" disabled={!available || action.busy || !query.trim()}>检索已保存资料</Button></form><p>使用本地字面匹配。向量、OCR 与视觉解析当前未配置；离线仍可检索已保存的文字。</p>{available && results && <div>{!results.length && <p>未找到可见的匹配段落。</p>}{results.map(row => <article className="experimental-record" key={citeKey(row.citation)}><strong>{row.title}</strong><p>{row.text}</p><label className="experimental-check"><input type="checkbox" checked={citations.some(c => citeKey(c) === citeKey(row.citation))} disabled={action.busy} onChange={() => toggleCitation(row.citation)} />选用第 {row.paragraph} 段引用</label><Button disabled={action.busy} onClick={() => void showCitation(row.citation)}>追溯 {row.title} 第 {row.paragraph} 段</Button></article>)}</div>}{available && evidence && <section aria-label="引用原文"><h4>{evidence.title} · {evidence.page ? `第 ${evidence.page} 页 · ` : ''}第 {evidence.paragraph} 段</h4><p>{evidence.not_understood ? '仅原始页面引用。OCR 与视觉理解未配置，没有提取或理解这页内容。' : evidence.text}</p><p>来源 v{evidence.citation.source_version} · {evidence.source}</p></section>}
      <p>已选择 {available ? citations.length : 0} 段引用。</p><Button disabled={!available || action.busy || !citations.length} onClick={() => void action.run(async alive => { const ticket = epoch.current; const result = await api.preview(citations); if (isScopeCurrent(alive) && ticket === epoch.current) setPreview(result.items); })}>预览所选研究上下文</Button>{available && preview && <section aria-label="研究上下文预览"><p>以下为不可信研究数据，仅供作者核对。没有自动注入或调用模型。</p>{preview.map(row => <p key={citeKey(row.citation)}>{row.title} · {row.not_understood ? `第 ${row.page} 页（未解析）` : `第 ${row.paragraph} 段`}：{row.text}</p>)}</section>}
    </Panel>
    <Panel title="研究笔记与原创设定草稿"><Field label="研究笔记标题"><input maxLength={240} value={noteTitle} onChange={e => setNoteTitle(e.target.value)} /></Field><Field label="研究笔记内容"><textarea maxLength={8000} value={noteText} onChange={e => setNoteText(e.target.value)} /></Field><Button disabled={!available || action.busy || !citations.length || !noteTitle.trim() || !noteText.trim()} onClick={() => void action.run(async alive => { if (noteEditing) await api.editNote(noteEditing, noteTitle, noteText, citations); else await api.note(noteTitle, noteText, citations); if (isScopeCurrent(alive)) { setNoteEditing(undefined); notes.reload(); repairs.reload(); } }, '研究笔记与原段落引用已保存。')}>{noteEditing ? '保存研究笔记新版本' : '保存带引用的研究笔记'}</Button>{noteEditing && <Button disabled={action.busy} onClick={() => { setNoteEditing(undefined); setNoteTitle(''); setNoteText(''); setCitations([]); }}>放弃研究笔记编辑</Button>}<ResourceState loading={notes.loading} error={notes.error} />{available && !notes.loading && !notes.error && notes.data?.items.map(row => <article className="experimental-record" key={row.id}><strong>{row.title}</strong><p>{row.text}</p><div className="experimental-actions"><Button disabled={action.busy} onClick={() => { setNoteEditing(row); setNoteTitle(row.title); setNoteText(row.text); setCitations(row.citations); setPreview(undefined); }}>编辑研究笔记 {row.title}</Button><Button disabled={action.busy} onClick={() => void action.run(async alive => { await api.deleteNote(row); if (isScopeCurrent(alive)) { setNoteEditing(undefined); notes.reload(); repairs.reload(); } }, '笔记已移到删除状态，引用来源保持原样。')}>删除研究笔记 {row.title}</Button><Button disabled={action.busy} onClick={() => void action.run(async alive => { const ticket = epoch.current; const result = await api.noteHistory(row.id); if (isScopeCurrent(alive) && ticket === epoch.current) setNoteHistory(result.items); })}>查看笔记历史 {row.title}</Button></div>{row.citations.map(ref => <Button key={citeKey(ref)} disabled={action.busy} onClick={() => void showCitation(ref)}>追溯笔记引用 第 {ref.paragraph} 段</Button>)}</article>)}
      {available && repairs.data?.items.map(row => <article key={row.id} className="experimental-record"><strong>引用待修复：{row.title}</strong><p>{row.text}</p><p>只恢复引用本人当前可见来源的原创笔记；不会自动绑定新版本。请重新选择当前来源段落。</p><Button disabled={action.busy} onClick={() => { setNoteEditing(row); setNoteTitle(row.title); setNoteText(row.text); setCitations([]); setPreview(undefined); }}>修复笔记引用 {row.title}</Button></article>)}
      {available && noteHistory && <section aria-label="研究笔记历史">{noteHistory.map(row => <p key={row.version}>v{row.version} · {row.title}：{row.text}</p>)}<p>当前不可访问或版本失效的来源对应历史不会展示。</p></section>}
      <Field label="原创设定草稿标题"><input maxLength={240} value={settingTitle} onChange={e => { setSettingTitle(e.target.value); setOriginal(false); }} /></Field><Field label="原创设定内容"><textarea maxLength={8000} value={settingText} onChange={e => { setSettingText(e.target.value); setOriginal(false); }} /></Field><label className="experimental-check"><input type="checkbox" checked={original} onChange={e => setOriginal(e.target.checked)} />已写成原创虚构设定，并核对所选参考引用</label><Button disabled={!available || action.busy || !citations.length || !settingTitle.trim() || !settingText.trim() || !original} onClick={() => void action.run(async alive => { await api.adopt(settingTitle, settingText, citations); if (isScopeCurrent(alive)) drafts.reload(); }, '原创设定已保存到现有世界记录的待审草稿。')}>采用为原创设定草稿</Button><p>在此审核只确认设定草稿。不会批准为 Canon，不会新增人物已知事实。</p><ResourceState loading={drafts.loading} error={drafts.error} />{available && !drafts.loading && !drafts.error && drafts.data?.items.map(row => <article className="experimental-record" key={row.id}><strong>{row.title}</strong><Badge>{row.status === 'RESEARCH_REVIEWED' ? '已核对的设定草稿' : '待核对设定草稿'} · v{row.version}</Badge><p>{row.data.description}</p><Button disabled={action.busy} onClick={() => void action.run(async alive => { await api.review(row, row.status === 'RESEARCH_REVIEWED' ? 'reopen' : 'review'); if (isScopeCurrent(alive)) drafts.reload(); }, '设定草稿审核状态已更新，Canon 未改变。')}>{row.status === 'RESEARCH_REVIEWED' ? '重新核对设定草稿' : '审核这个设定草稿'}</Button></article>)}
    </Panel>
  </section>;
}
