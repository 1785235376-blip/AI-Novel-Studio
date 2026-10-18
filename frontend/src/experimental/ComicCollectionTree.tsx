import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { ErrorMessage, Field, ResourceState, useResource } from './shared';
import { comicLayoutsClient, type ComicBook, type ComicBookDocument, type ComicChapter, type ComicRecord } from './comicLayoutsClient';
import { ComicPublicationPanel } from './ComicPublicationPanel';

type Props = {
  client: ExperimentalClient;
  records: ComicRecord[];
  recordsReady: boolean;
  pageDirty: boolean;
  externalBusy: boolean;
  selectedPageId?: string;
  isOwnerCurrent?: () => boolean;
  getOwnerRevision: () => number;
  onActiveChange: (active: boolean) => void;
  onDirtyChange: (dirty: boolean) => void;
  onBusyChange: (busy: boolean) => void;
  onOpenPage: (page: ComicRecord) => void;
  onPageCreated: (page: ComicRecord) => void;
};
const MAX_CHAPTERS = 20, MAX_PAGES = 100;
function visibleBook(book?: ComicBook): book is ComicBook & ComicBookDocument {
  return !!book && !book.stale && typeof book.title === 'string' && Array.isArray(book.chapters);
}
const countPages = (draft: ComicBookDocument) => draft.chapters.reduce((total, chapter) => total + chapter.pages.length, 0);
function move<T>(values: T[], from: number, to: number): T[] {
  const result = [...values]; const [value] = result.splice(from, 1); result.splice(to, 0, value); return result;
}

/** Collection revisions own membership only. Page contents retain the existing editor/review contract. */
export function ComicCollectionTree(props: Props) {
  const api = useMemo(() => comicLayoutsClient(props.client), [props.client]);
  const books = useResource(signal => api.books(signal), [api]);
  const [book, setBook] = useState<ComicBook>();
  const [draft, setDraft] = useState<ComicBookDocument>();
  const [dirty, setDirty] = useState(false), [busy, setBusy] = useState(false);
  const [publicationBusy, setPublicationBusy] = useState(false);
  const publicationPending = useRef(false);
  const [error, setError] = useState<unknown>(), [notice, setNotice] = useState('');
  const [newTitle, setNewTitle] = useState(''), [restoreVersion, setRestoreVersion] = useState('');
  const [attach, setAttach] = useState<Record<string, string>>({});
  const alive = useRef(true), pending = useRef(false), generation = useRef(0), composing = useRef(false);
  const live = useRef(props); live.current = props;
  const dependencies = [props.client, props.records, props.recordsReady, props.pageDirty, props.externalBusy];
  const scope = useRef(dependencies);
  if (dependencies.some((value, index) => value !== scope.current[index])) { scope.current = dependencies; generation.current++; }
  const renderedGeneration = generation.current, ownerRevision = props.getOwnerRevision();
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; generation.current++; }; }, []);
  const recordsSeen = useRef(props.records);
  useEffect(() => { if (recordsSeen.current !== props.records) { recordsSeen.current = props.records; books.reload(); } }, [props.records, books.reload]);
  const ready = !books.loading && !books.error && !!books.data && Array.isArray(books.data.items);
  const latestBook = ready ? books.data!.items.find(item => item.id === book?.id) : undefined;
  const usable = ready && props.recordsReady && !props.externalBusy && !props.pageDirty && !busy && !publicationBusy;
  const pageRows = new Map(props.records.filter(row => !row.stale && row.document?.source_mode === 'INDEPENDENT').map(row => [row.id, row]));
  const pageIds = draft?.chapters.flatMap(chapter => chapter.pages) || [];
  const allReferencesAvailable = props.recordsReady && pageIds.every(id => pageRows.has(id));
  const projectableBook = (value?: ComicBook): value is ComicBook & ComicBookDocument => visibleBook(value) && props.recordsReady && value.chapters.every(chapter => chapter.pages.every(id => pageRows.has(id)));
  const selectedCurrent = projectableBook(book) && projectableBook(latestBook) && book.version === latestBook.version && allReferencesAvailable;
  const navigationBlocked = dirty || props.pageDirty;
  const current = () => alive.current && (live.current.isOwnerCurrent?.() ?? true) && renderedGeneration === generation.current && ownerRevision === live.current.getOwnerRevision() && !pending.current && !publicationPending.current && !live.current.externalBusy;
  const changeDirty = (value: boolean) => { setDirty(value); props.onDirtyChange(value); };
  const consume = () => { generation.current++; setNotice(''); setError(undefined); };
  const edit = (next: ComicBookDocument) => {
    if (!current() || !usable || !selectedCurrent) return;
    consume(); setDraft(next); changeDirty(true);
  };
  const commit = (next: ComicBook) => {
    props.onActiveChange(true); setBook(next); setDraft(visibleBook(next) ? { title: next.title, chapters: next.chapters } : undefined);
    changeDirty(false); setAttach({}); setRestoreVersion('');
  };
  const run = async (operation: () => Promise<ComicBook>, message: string, after?: () => void) => {
    if (!current() || !usable || composing.current) return;
    const ticket = ++generation.current; pending.current = true; setBusy(true); props.onBusyChange(true); setError(undefined); setNotice('');
    const actionOwnerRevision = live.current.getOwnerRevision();
    const accepted = () => alive.current && ticket === generation.current && actionOwnerRevision === live.current.getOwnerRevision() && (live.current.isOwnerCurrent?.() ?? true) && !live.current.externalBusy;
    try {
      const result = await operation();
      if (accepted()) { commit(result); books.reload(); setNotice(message); after?.(); }
    } catch (reason) { if (accepted()) setError(reason); }
    finally {
      pending.current = false;
      if (alive.current) { setBusy(false); if (live.current.isOwnerCurrent?.() ?? true) live.current.onBusyChange(false); }
    }
  };
  const save = () => {
    if (!book || !draft || !selectedCurrent || !allReferencesAvailable || !draft.title.trim() || draft.chapters.some(chapter => !chapter.title.trim())) return;
    void run(() => api.saveBook(book, draft, Object.fromEntries(pageIds.map(id => [id, pageRows.get(id)!.version]))), '漫画书结构已保存。页面内容和审核状态保持独立。');
  };
  const addPage = (chapter: ComicChapter, source?: ComicRecord) => {
    if (!book || !draft || !selectedCurrent || navigationBlocked || countPages(draft) >= MAX_PAGES || (source && !pageRows.has(source.id))) return;
    let page: ComicRecord | undefined;
    void run(async () => { const result = await api.createBookPage(book, chapter.id, source); page = result.page; return result.book; }, source ? '已复制为新的待审页面，原页面保持不变。' : '已在章节中创建空白待审页面。', () => { if (page) props.onPageCreated(page); });
  };
  const patchChapter = (id: string, patch: Partial<ComicChapter>) => draft && edit({ ...draft, chapters: draft.chapters.map(chapter => chapter.id === id ? { ...chapter, ...patch } : chapter) });
  return <Panel title="漫画书 · 章节 · 页面">
    <div onCompositionStartCapture={() => { composing.current = true; }} onCompositionEndCapture={() => { composing.current = false; }}>
      <p>手工组织独立漫画页。最多 20 本书，每本书最多 20 章、100 页；结构恢复只恢复章节与页面归属，不恢复页面内容。移除章节或页面不会删除已保存布局。同一页面可被多本书引用，编辑会影响所有引用它的书；复制页面会创建独立副本。</p>
      <ResourceState loading={books.loading} error={books.error} />
      {!!error && <ErrorMessage error={error} />}{notice && <StatusMessage tone="success">{notice}</StatusMessage>}
      {navigationBlocked && <StatusMessage tone="warning">有未保存的{dirty && props.pageDirty ? '书结构和页面' : dirty ? '书结构' : '页面'}。请先保存或明确放弃对应草稿，再切换书或页面、新建页面、复制页面或恢复结构。</StatusMessage>}
      <div className="experimental-actions"><Button disabled={busy || publicationBusy || props.externalBusy || navigationBlocked || books.loading} onClick={() => { if (!current() || navigationBlocked || composing.current) return; consume(); books.reload(); }}>刷新漫画书</Button></div>
      <Field label="新漫画书名称"><input maxLength={240} value={newTitle} disabled={!usable || navigationBlocked} onChange={event => { if (!current()) return; consume(); setNewTitle(event.target.value); }} /></Field>
      <Button disabled={!usable || navigationBlocked || !newTitle.trim() || (books.data?.items.length || 0) >= 20} onClick={() => { if (navigationBlocked || !newTitle.trim() || (books.data?.items.length || 0) >= 20) return; void run(() => api.createBook(newTitle.trim()), '已创建空漫画书，可以添加章节。', () => setNewTitle('')); }}>创建漫画书</Button>
      {ready && !books.data!.items.length && <EmptyState title="还没有漫画书" detail="创建书后添加章节，再新建、复制或附加已保存的独立页面。" />}
      <nav aria-label="漫画书列表"><ul>{ready && books.data!.items.map(item => <li key={item.id}>{projectableBook(item)
        ? <Button disabled={!usable || navigationBlocked} aria-pressed={item.id === book?.id} onClick={() => { if (!current() || navigationBlocked || composing.current) return; consume(); commit(item); }}>打开漫画书 {item.title}</Button>
        : <StatusMessage tone="warning">漫画书或引用页面不可用，标题与结构已隐藏。</StatusMessage>}</li>)}</ul></nav>
      {book && ready && !selectedCurrent && <StatusMessage tone="warning">当前书版本已变化或不可用，旧结构已隐藏。若有本地修改，请明确放弃后重新打开当前版本。</StatusMessage>}
      {dirty && <Button disabled={busy || props.externalBusy} onClick={() => { if (!current() || composing.current) return; consume(); if (projectableBook(latestBook)) commit(latestBook); else { props.onActiveChange(false); setBook(undefined); setDraft(undefined); changeDirty(false); } }}>放弃书结构修改</Button>}
      {draft && selectedCurrent && <>
        <Badge>{dirty ? '未保存结构' : '已保存结构'} · v{book!.version} · {countPages(draft)} / {MAX_PAGES} 页</Badge>
        <fieldset className="experimental-form" disabled={!usable}>
          <Field label="漫画书名称"><input maxLength={240} value={draft.title} onChange={event => edit({ ...draft, title: event.target.value })} /></Field>
          <Button disabled={draft.chapters.length >= MAX_CHAPTERS} onClick={() => { if (!current() || composing.current || draft.chapters.length >= MAX_CHAPTERS) return; edit({ ...draft, chapters: [...draft.chapters, { id: globalThis.crypto.randomUUID(), title: `第 ${draft.chapters.length + 1} 章`, pages: [] }] }); }}>添加漫画章节</Button>
          {!draft.chapters.length && <EmptyState title="这本书还没有章节" detail="添加章节并保存结构后，可以在章节中新建或复制页面。" />}
          <ol aria-label="漫画章节与页面">{draft.chapters.map((chapter, chapterIndex) => <li key={chapter.id}>
            <Field label={`章节 ${chapterIndex + 1} 名称`}><input maxLength={240} value={chapter.title} onChange={event => patchChapter(chapter.id, { title: event.target.value })} /></Field>
            <div className="experimental-actions">
              <Button disabled={chapterIndex === 0} onClick={() => chapterIndex > 0 && edit({ ...draft, chapters: move(draft.chapters, chapterIndex, chapterIndex - 1) })}>上移章节 {chapterIndex + 1}</Button>
              <Button disabled={chapterIndex === draft.chapters.length - 1} onClick={() => chapterIndex < draft.chapters.length - 1 && edit({ ...draft, chapters: move(draft.chapters, chapterIndex, chapterIndex + 1) })}>下移章节 {chapterIndex + 1}</Button>
              <Button onClick={() => edit({ ...draft, chapters: draft.chapters.filter(item => item.id !== chapter.id) })}>移除章节 {chapterIndex + 1}（保留页面）</Button>
            </div>
            <ol aria-label={`章节 ${chapterIndex + 1} 页面`}>{chapter.pages.map((id, pageIndex) => {
              const page = pageRows.get(id);
              return <li key={id}>
                {page ? <Button aria-pressed={props.selectedPageId === id} disabled={navigationBlocked} onClick={() => { if (!current() || navigationBlocked || composing.current) return; consume(); props.onOpenPage(page); }}>打开页面 {chapterIndex + 1}.{pageIndex + 1} · {page.document!.title}</Button> : <StatusMessage tone="warning">页面不可用，内容已隐藏。</StatusMessage>}
                <div className="experimental-actions">
                  <Button disabled={pageIndex === 0} onClick={() => pageIndex > 0 && patchChapter(chapter.id, { pages: move(chapter.pages, pageIndex, pageIndex - 1) })}>上移页面 {chapterIndex + 1}.{pageIndex + 1}</Button>
                  <Button disabled={pageIndex === chapter.pages.length - 1} onClick={() => pageIndex < chapter.pages.length - 1 && patchChapter(chapter.id, { pages: move(chapter.pages, pageIndex, pageIndex + 1) })}>下移页面 {chapterIndex + 1}.{pageIndex + 1}</Button>
                  <Button onClick={() => patchChapter(chapter.id, { pages: chapter.pages.filter(value => value !== id) })}>移出页面 {chapterIndex + 1}.{pageIndex + 1}（保留布局）</Button>
                  <Button disabled={navigationBlocked || !page || countPages(draft) >= MAX_PAGES} onClick={() => page && addPage(chapter, page)}>复制页面 {chapterIndex + 1}.{pageIndex + 1}</Button>
                </div>
                <Field label={`页面 ${chapterIndex + 1}.${pageIndex + 1} 所属章节`}><select value={chapter.id} onChange={event => {
                  const target = event.target.value;
                  if (!draft.chapters.some(item => item.id === target) || target === chapter.id) return;
                  edit({ ...draft, chapters: draft.chapters.map(item => ({ ...item, pages: item.id === chapter.id ? item.pages.filter(value => value !== id) : item.id === target ? [...item.pages, id] : item.pages })) });
                }}>{draft.chapters.map((item, index) => <option key={item.id} value={item.id}>{index + 1}. {item.title}</option>)}</select></Field>
              </li>;
            })}</ol>
            <Field label={`章节 ${chapterIndex + 1} 附加独立页面`}><select value={attach[chapter.id] || ''} disabled={countPages(draft) >= MAX_PAGES} onChange={event => { if (!current()) return; consume(); setAttach({ ...attach, [chapter.id]: event.target.value }); }}><option value="">选择已保存的独立页面</option>{[...pageRows.values()].filter(page => !pageIds.includes(page.id)).map(page => <option key={page.id} value={page.id}>{page.document!.title} · v{page.version}</option>)}</select></Field>
            <Button disabled={!attach[chapter.id] || countPages(draft) >= MAX_PAGES} onClick={() => { const id = attach[chapter.id]; if (!current() || !id || !pageRows.has(id) || pageIds.includes(id) || countPages(draft) >= MAX_PAGES) return; patchChapter(chapter.id, { pages: [...chapter.pages, id] }); setAttach({ ...attach, [chapter.id]: '' }); }}>附加到章节 {chapterIndex + 1}</Button>
            <Button disabled={navigationBlocked || countPages(draft) >= MAX_PAGES} onClick={() => addPage(chapter)}>在章节 {chapterIndex + 1} 新建空白页</Button>
          </li>)}</ol>
        </fieldset>
        <Button disabled={!usable || !dirty || !allReferencesAvailable || !draft.title.trim() || draft.chapters.some(chapter => !chapter.title.trim())} onClick={save}>保存漫画书结构</Button>
        <Field label="恢复漫画书结构版本"><select disabled={!usable || navigationBlocked} value={restoreVersion} onChange={event => { if (!current()) return; consume(); setRestoreVersion(event.target.value); }}><option value="">选择历史结构版本</option>{book!.history_versions?.slice(-100).map(version => <option key={version} value={version}>v{version}</option>)}</select></Field>
        <p>恢复会新建结构版本，恢复旧章节顺序和页面归属；页面文字、格框、图片及审核状态不回滚。</p>
        <Button disabled={!usable || navigationBlocked || !restoreVersion} onClick={() => { if (!book || navigationBlocked || !book.history_versions?.includes(Number(restoreVersion))) return; void run(() => api.restoreBook(book, Number(restoreVersion)), '已新增恢复后的结构版本，页面内容未回滚。'); }}>恢复为新的漫画书结构版本</Button>
        <ComicPublicationPanel key={book!.id} client={props.client} book={book! as ComicBook & ComicBookDocument} records={props.records}
          disabled={dirty || props.pageDirty || props.externalBusy || busy} collectionRevision={generation.current} getCollectionRevision={() => generation.current}
          isOwnerCurrent={() => alive.current && (live.current.isOwnerCurrent?.() ?? true)} getOwnerRevision={() => live.current.getOwnerRevision()}
          onBusyChange={value => { publicationPending.current = value; if (alive.current) setPublicationBusy(value); live.current.onBusyChange(value); }} />
      </>}
    </div>
  </Panel>;
}
