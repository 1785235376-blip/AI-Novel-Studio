export const MAX_OFFLINE_SYNC_BYTES = 512 * 1024;
const MAX_OFFLINE_SYNC_DEPTH = 64;

/** Fixed messages only: never show parser excerpts, file contents or local paths. */
export class OfflineSyncInputError extends Error {}
const tooLarge = () => new OfflineSyncInputError('同步消息不能超过 512 KiB，请选择较小的交换文件。');
const tooDeep = () => new OfflineSyncInputError('同步消息的 JSON 嵌套不能超过 64 层，请简化消息后重试；原输入已保留。');
const unreadable = () => new OfflineSyncInputError('无法读取本地文件，请重新选择文件；原输入已保留。');
const cancelled = () => new DOMException('文件读取已取消。', 'AbortError');

/** Bound containers before parsing so recursive preview serialization stays safe. */
function checkStructuralDepth(text: string): void {
  let depth = 0, inString = false, escaped = false;
  for (let index = 0; index < text.length; index++) {
    const character = text[index];
    if (inString) {
      if (escaped) escaped = false;
      else if (character === '\\') escaped = true;
      else if (character === '"') inString = false;
    } else if (character === '"') inString = true;
    else if (character === '[' || character === '{') {
      if (++depth > MAX_OFFLINE_SYNC_DEPTH) throw tooDeep();
    } else if (character === ']' || character === '}') depth--;
  }
  // JSON.parse remains responsible for all syntax, including bracket matching.
}

/** Syntax and resource limits only. The original sync owner validates the envelope. */
export function parseOfflineSyncMessage(text: string): unknown {
  if (new TextEncoder().encode(text).byteLength > MAX_OFFLINE_SYNC_BYTES) throw tooLarge();
  checkStructuralDepth(text);
  // Accept one UTF-8 BOM from local text exporters, but retain the exact input
  // in the editor and enforce its bytes above. Never trim other content.
  try { return JSON.parse(text.startsWith('\uFEFF') ? text.slice(1) : text); }
  catch { throw new OfflineSyncInputError('同步消息不是有效的 JSON，请检查文件或手动修正文本；原输入已保留。'); }
}

export function offlineSyncInputError(error: unknown): string {
  return error instanceof OfflineSyncInputError ? error.message : unreadable().message;
}

/** Read locally, with actual-byte enforcement and cancellable FileReader ownership. */
export function readOfflineSyncFile(file: File, signal?: AbortSignal): Promise<string> {
  if (signal?.aborted) return Promise.reject(cancelled());
  if (file.size > MAX_OFFLINE_SYNC_BYTES) return Promise.reject(tooLarge());
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    let settled = false;
    const finish = (text?: string, error?: Error) => {
      if (settled) return;
      settled = true;
      signal?.removeEventListener('abort', abort);
      reader.onload = reader.onerror = reader.onabort = null;
      if (error) reject(error); else resolve(text!);
    };
    const abort = () => {
      finish(undefined, cancelled());
      if (reader.readyState === FileReader.LOADING) reader.abort();
    };
    reader.onerror = () => finish(undefined, unreadable());
    reader.onabort = () => finish(undefined, cancelled());
    reader.onload = () => {
      const bytes = reader.result;
      if (!bytes || typeof bytes === 'string') { finish(undefined, unreadable()); return; }
      if (bytes.byteLength > MAX_OFFLINE_SYNC_BYTES) { finish(undefined, tooLarge()); return; }
      let text: string;
      try { text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes); }
      catch { finish(undefined, new OfflineSyncInputError('同步文件必须是有效的 UTF-8 文本，请另存为 UTF-8 后重选；原输入已保留。')); return; }
      try { parseOfflineSyncMessage(text); finish(text); }
      catch (error) { finish(undefined, error instanceof OfflineSyncInputError ? error : unreadable()); }
    };
    signal?.addEventListener('abort', abort, { once: true });
    try { reader.readAsArrayBuffer(file); }
    catch { finish(undefined, unreadable()); }
  });
}
