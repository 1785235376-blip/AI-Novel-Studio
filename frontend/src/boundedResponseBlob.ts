import { ApiError } from './api';

/** Opt-in cap for reading-copy downloads. Never fall back to an unbounded blob read. */
export type BlobReadLimit = { maxBytes: number };
export function checkBlobReadLimit(limit: BlobReadLimit): void {
  if (!Number.isSafeInteger(limit.maxBytes) || limit.maxBytes < 1 || limit.maxBytes > 64 * 1024 * 1024) {
    throw new ApiError({ status: 422, code: 'DOWNLOAD_LIMIT_INVALID', message: '下载文件大小上限无效。' });
  }
}
export function cancelResponseBody(response: Response): void {
  try { void response.body?.cancel().catch(() => undefined); } catch { /* Best-effort cleanup. */ }
}
export async function readBoundedResponseBlob(response: Response, limit: BlobReadLimit): Promise<Blob> {
  checkBlobReadLimit(limit);
  const invalid = () => new ApiError({ status: 422, code: 'DOWNLOAD_RESPONSE_INVALID', message: '文件未能安全读取，请重新检查后下载。' });
  const tooLarge = () => new ApiError({ status: 422, code: 'DOWNLOAD_TOO_LARGE', message: '文件超过下载大小上限，请使用更小的阅读副本。' });
  const declaredLength = response.headers.get('Content-Length');
  if (response.redirected || ['opaque', 'opaqueredirect', 'error'].includes(response.type) || !response.body || typeof response.body.getReader !== 'function') { cancelResponseBody(response); throw invalid(); }
  if (declaredLength !== null && /^\d+$/.test(declaredLength) && Number(declaredLength) > limit.maxBytes) { cancelResponseBody(response); throw tooLarge(); }
  let reader: ReadableStreamDefaultReader<Uint8Array>;
  try { reader = response.body.getReader(); } catch { cancelResponseBody(response); throw invalid(); }
  try {
    // One fixed buffer bounds bookkeeping even for arbitrarily small chunks.
    const bytes = new Uint8Array(limit.maxBytes); let size = 0;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      if (!ArrayBuffer.isView(value) || Object.prototype.toString.call(value) !== '[object Uint8Array]') throw invalid();
      if (value.byteLength > limit.maxBytes - size) throw tooLarge();
      bytes.set(value, size); size += value.byteLength;
    }
    return new Blob([bytes.subarray(0, size)], { type: response.headers.get('Content-Type') || '' });
  } catch (error) {
    try { void reader.cancel().catch(() => undefined); } catch { /* Cleanup must not replace the safe error. */ }
    if (error instanceof ApiError) throw error;
    throw invalid();
  } finally { try { reader.releaseLock(); } catch { /* A failing stream may remain locked. */ } }
}
