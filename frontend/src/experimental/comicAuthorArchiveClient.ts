import type { ExperimentalClient } from './api';
import type { ComicBook, ComicBookDocument, ComicRecord } from './comicLayoutsClient';
export const authorArchiveMaxBytes = 2_000_000;
export const authorDisclosure = 'PRIVATE_AUTHOR_CONTENT_INCLUDES_HIDDEN_TEXT_AND_IMAGE_BRIEFS_NOT_A_PUBLIC_READING_COPY';
const coverage = 'ASSETLESS_INDEPENDENT_PAGE_ONLY';
const contract = 'comic-author-assetless-page/1';
const hex = (value: string) => /^[a-f0-9]{64}$/.test(value);
const invalid = (): never => { throw new Error('COMIC_AUTHOR_ARCHIVE_INVALID_RESPONSE'); };
export type AuthorBytes = { archive_base64: string; archive_sha256: string };
export type AuthorPreview = { contract: string; export_digest: string; book_version: number; page_count: number; disclosure: string; coverage: string; conveys_approval: false; pages: { id: string; version: number }[] };
export type AuthorInspection = { contract: string; archive_sha256: string; inspection_digest: string; title: string; page_count: number; disclosure: string; coverage: string; restore_status: string; receipt_capacity: number; receipt_remaining: number; completed_attempts: { request_key: string; result_state: 'COMPLETED' }[] };
export type AuthorRestore = { book: ComicBook & ComicBookDocument; pages: ComicRecord[]; replayed: boolean; request_key: string };
const sha = async (buffer: ArrayBuffer) => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', buffer)), n => n.toString(16).padStart(2, '0')).join('');
export async function readAuthorArchive(file: File): Promise<AuthorBytes> {
  if (file.size < 22 || file.size > authorArchiveMaxBytes) throw new Error('作者归档必须为 22–2,000,000 字节。');
  const buffer = await file.slice(0, authorArchiveMaxBytes + 1).arrayBuffer();
  if (buffer.byteLength !== file.size || buffer.byteLength > authorArchiveMaxBytes) return invalid();
  const bytes = new Uint8Array(buffer); let binary = '';
  for (let i = 0; i < bytes.length; i += 32768) binary += String.fromCharCode(...bytes.subarray(i, i + 32768));
  return { archive_base64: btoa(binary), archive_sha256: await sha(buffer) };
}
export function comicAuthorArchiveClient(client: ExperimentalClient) {
  const root = '/comic-layouts';
  return {
    preview: async (book: ComicBook & ComicBookDocument, records: ComicRecord[]) => {
      const result = await client.post<AuthorPreview>(`${root}/books/${encodeURIComponent(book.id)}/author-archive-preview`, { expected_version: book.version });
      const ids = book.chapters.flatMap(c => c.pages);
      if (!result || result.contract !== contract || result.coverage !== coverage || result.disclosure !== authorDisclosure || result.conveys_approval !== false || !hex(result.export_digest) || result.book_version !== book.version || result.page_count !== ids.length || ids.length < 1 || ids.length > 10 || !Array.isArray(result.pages) || result.pages.length !== ids.length || result.pages.some((p, i) => !p || p.id !== ids[i] || p.version !== records.find(r => r.id === ids[i])?.version)) return invalid();
      return result;
    },
    download: async (book: ComicBook, preview: AuthorPreview) => {
      if (!client.postBlob || preview.book_version !== book.version || !hex(preview.export_digest)) return invalid();
      const { blob, headers } = await client.postBlob(`${root}/books/${encodeURIComponent(book.id)}/export-author-archive`, { expected_version: book.version, export_digest: preview.export_digest, acknowledge_author_content: true }, { maxBytes: authorArchiveMaxBytes });
      if (blob.type.split(';')[0] !== 'application/zip' || blob.size < 22 || blob.size > authorArchiveMaxBytes || headers.get('X-Comic-Author-Export-Digest') !== preview.export_digest || await sha(await blob.arrayBuffer()) !== headers.get('X-Content-SHA256')) return invalid();
      return blob;
    },
    inspect: async (bytes: AuthorBytes) => {
      const result = await client.post<AuthorInspection>(`${root}/author-archive/inspect`, bytes);
      if (!result || result.contract !== contract || result.archive_sha256 !== bytes.archive_sha256 || result.coverage !== coverage || result.disclosure !== authorDisclosure || result.restore_status !== 'NEW_UNAPPROVED_DRAFTS' || !hex(result.inspection_digest) || typeof result.title !== 'string' || !result.title || !Number.isSafeInteger(result.page_count) || result.page_count < 1 || result.page_count > 10 || result.receipt_capacity !== 20 || !Number.isSafeInteger(result.receipt_remaining) || result.receipt_remaining < 0 || result.receipt_remaining > 20) return invalid();
      if (!Array.isArray(result.completed_attempts) || result.completed_attempts.length > 20 || result.completed_attempts.some(a => !a || !/^[a-f0-9]{32}$/.test(a.request_key) || a.result_state !== 'COMPLETED')) return invalid();
      return result;
    },
    restore: async (bytes: AuthorBytes, report: AuthorInspection, request_key: string) => {
      const result = await client.post<AuthorRestore>(`${root}/author-archive/restore`, { ...bytes, inspection_digest: report.inspection_digest, request_key, acknowledge_restore_drafts: true });
      if (!result || result.request_key !== request_key || typeof result.replayed !== 'boolean' || !result.book || result.book.stale || !Array.isArray(result.book.chapters) || !Array.isArray(result.pages) || result.pages.length !== report.page_count || result.pages.some(p => !p || p.stale || !p.document || (!result.replayed && p.status !== 'DRAFT'))) return invalid();
      const ids = result.book.chapters.flatMap(c => c.pages);
      if (ids.length !== result.pages.length || new Set(ids).size !== ids.length || ids.some(id => !result.pages.some(p => p.id === id))) return invalid();
      return result;
    },
  };
}
// Bounded recovery identity only: never persist archive bytes, author text or credentials.
const attemptStorage = 'comic-author-attempts-v1';
type Attempt = { digest: string; request_key: string; status: 'PENDING' | 'COMPLETED' };
function attempts(): Attempt[] {
  try {
    const raw = localStorage.getItem(attemptStorage); if (!raw) return [];
    if (raw.length > 20000) throw new Error('invalid');
    const items: Attempt[] = JSON.parse(raw);
    if (!Array.isArray(items) || items.length > 64 || items.some(a => !a || !hex(a.digest) || !/^[a-f0-9]{32}$/.test(a.request_key) || !['PENDING', 'COMPLETED'].includes(a.status))) throw new Error('invalid');
    return items;
  } catch { throw new Error('无法读取本地恢复标识。请保留文件，并在可用的浏览器存储环境中重试。'); }
}
export const readAuthorAttempt = (digest: string) => attempts().find(a => a.digest === digest);
export function saveAuthorAttempt(digest: string, request_key: string, status: Attempt['status']) {
  const next = attempts().filter(a => a.digest !== digest);
  if (next.length >= 64) { const completed = next.findIndex(a => a.status === 'COMPLETED'); if (completed < 0) throw new Error('本地待核对恢复标识已满，请先核对已有恢复结果。'); next.splice(completed, 1); }
  next.push({ digest, request_key, status });
  try { const encoded = JSON.stringify(next); localStorage.setItem(attemptStorage, encoded); if (localStorage.getItem(attemptStorage) !== encoded) throw new Error('readback'); }
  catch { throw new Error(status === 'PENDING' ? '无法保存恢复标识，尚未提交恢复。请启用本地存储后重试。' : '服务器已返回结果，但无法保存完成状态。请保留相同文件并重新检查、重试以核对已有结果。'); }
}

export async function withAuthorAttempt<T>(digest: string, candidate: string, expectedCompletedKey: string | undefined, current: () => boolean, work: (requestKey: string) => Promise<T>): Promise<T> {
  if (!navigator.locks?.request) throw new Error('此浏览器不支持跨标签页恢复锁，不能安全提交恢复。请使用支持 Web Locks 的浏览器。');
  // The outer lock also protects the bounded shared metadata map across distinct archives.
  return navigator.locks.request('comic-author-attempt-store-v1', () => navigator.locks.request(`comic-author-restore:${digest}`, async () => {
    if (!current()) throw new Error('作者归档范围已变化，请重新检查。');
    const saved = readAuthorAttempt(digest);
    if (expectedCompletedKey && saved && (saved.request_key !== expectedCompletedKey || saved.status !== 'COMPLETED')) {
      throw new Error('已有恢复尝试已变化或结果未知。请重新选择相同文件并检查、核对已有结果，不能开始另一份导入。');
    }
    const requestKey = !expectedCompletedKey && saved ? saved.request_key : candidate;
    saveAuthorAttempt(digest, requestKey, 'PENDING');
    const result = await work(requestKey);
    saveAuthorAttempt(digest, requestKey, 'COMPLETED');
    return result;
  }));
}
