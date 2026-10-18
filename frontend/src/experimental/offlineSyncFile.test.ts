// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { MAX_OFFLINE_SYNC_BYTES, offlineSyncInputError, parseOfflineSyncMessage, readOfflineSyncFile } from './offlineSyncFile';

afterEach(() => { vi.restoreAllMocks(); });

it('reads the actual local file and preserves whitespace and literal Unicode without schema coercion', async () => {
  const text = ' \n{ "snapshot": "合成输入🙂é", "arbitrary": true }\n';
  expect(await readOfflineSyncFile(new File([text], 'exchange.json', { type: 'application/json' }))).toBe(text);
  expect(await readOfflineSyncFile(new File(['null'], 'copy.txt', { type: 'text/plain' }))).toBe('null');
  expect(parseOfflineSyncMessage('false')).toBe(false);
});

it('accepts exactly 512 KiB and rejects a single additional actual byte', async () => {
  const exact = JSON.stringify('a'.repeat(MAX_OFFLINE_SYNC_BYTES - 2));
  expect(new TextEncoder().encode(exact).byteLength).toBe(MAX_OFFLINE_SYNC_BYTES);
  expect(await readOfflineSyncFile(new File([exact], 'limit.json'))).toBe(exact);
  await expect(readOfflineSyncFile(new File([exact + ' '], 'oversize.json'))).rejects.toThrow(/512 KiB/);
});

it('checks File.size before allocating a reader and independently enforces actual returned bytes', async () => {
  const read = vi.spyOn(FileReader.prototype, 'readAsArrayBuffer');
  await expect(readOfflineSyncFile(new File([new Uint8Array(MAX_OFFLINE_SYNC_BYTES + 1)], 'large.json'))).rejects.toThrow(/512 KiB/);
  expect(read).not.toHaveBeenCalled();
  const dishonest = new File([JSON.stringify('a'.repeat(MAX_OFFLINE_SYNC_BYTES))], 'small-metadata.json');
  Object.defineProperty(dishonest, 'size', { value: 1 });
  await expect(readOfflineSyncFile(dishonest)).rejects.toThrow(/512 KiB/);
  expect(read).toHaveBeenCalledTimes(1);
});

it('counts pasted UTF-8 bytes rather than characters', () => {
  const text = JSON.stringify('中'.repeat(Math.floor(MAX_OFFLINE_SYNC_BYTES / 3) + 1));
  expect(text.length).toBeLessThan(MAX_OFFLINE_SYNC_BYTES);
  expect(() => parseOfflineSyncMessage(text)).toThrow(/512 KiB/);
});

it.each([
  new Uint8Array([0xff, 0xfe]),
  new Uint8Array([0x22, 0xc3, 0x28, 0x22]),
  new Uint8Array([0x22, 0xe4, 0xb8]),
])('rejects invalid and truncated UTF-8 instead of replacing bytes', async bytes => {
  await expect(readOfflineSyncFile(new File([bytes], 'invalid.json'))).rejects.toThrow(/UTF-8/);
});

it('accepts exactly one leading UTF-8 BOM without changing the editable text or byte limit', async () => {
  const text = '\uFEFF{"text":"interior\uFEFFliteral"}';
  expect(await readOfflineSyncFile(new File([text], 'windows-export.json'))).toBe(text);
  expect(parseOfflineSyncMessage(text)).toEqual({ text: 'interior\uFEFFliteral' });
  const atLimit = '\uFEFF' + JSON.stringify('a'.repeat(MAX_OFFLINE_SYNC_BYTES - 5));
  expect(new TextEncoder().encode(atLimit).byteLength).toBe(MAX_OFFLINE_SYNC_BYTES);
  expect(await readOfflineSyncFile(new File([atLimit], 'limit.json'))).toBe(atLimit);
  expect(() => parseOfflineSyncMessage(atLimit + ' ')).toThrow(/512 KiB/);
});

it.each(['', '  ', '{"private-path":"C:\\private\\secret",oops}', '\uFEFF\uFEFF{}', '\n\uFEFF{}', '{}\uFEFF'])('rejects malformed JSON with a bounded safe error', async text => {
  const result = await readOfflineSyncFile(new File([text], 'C-private-secret.json')).catch(error => error);
  expect(result).toBeInstanceOf(Error);
  expect(result.message).toMatch(/有效的 JSON/);
  expect(result.message).not.toMatch(/private|secret|oops|SyntaxError/);
});

it('sanitizes low-level file failures and synchronous reader exceptions', async () => {
  const read = vi.spyOn(FileReader.prototype, 'readAsArrayBuffer').mockImplementation(function (this: FileReader) {
    this.onerror?.(new ProgressEvent('error') as ProgressEvent<FileReader>);
  });
  await expect(readOfflineSyncFile(new File(['{}'], 'message.json'))).rejects.toThrow(/无法读取本地文件/);
  read.mockImplementation(() => { throw new Error('C:\\private\\secret'); });
  await expect(readOfflineSyncFile(new File(['{}'], 'message.json'))).rejects.toThrow(/无法读取本地文件/);
  expect(offlineSyncInputError(new Error('sensitive parser excerpt'))).not.toContain('sensitive');
});

it('rejects an already-aborted signal without reading', async () => {
  const read = vi.spyOn(FileReader.prototype, 'readAsArrayBuffer'), controller = new AbortController();
  controller.abort();
  await expect(readOfflineSyncFile(new File(['{}'], 'message.json'), controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
  expect(read).not.toHaveBeenCalled();
});

it('cancels the actual pending reader and detaches callbacks and the abort listener', async () => {
  let reader!: FileReader;
  vi.spyOn(FileReader.prototype, 'readAsArrayBuffer').mockImplementation(function (this: FileReader) {
    reader = this; Object.defineProperty(this, 'readyState', { value: FileReader.LOADING });
  });
  const abort = vi.spyOn(FileReader.prototype, 'abort').mockImplementation(() => {}), controller = new AbortController();
  const remove = vi.spyOn(controller.signal, 'removeEventListener');
  const result = readOfflineSyncFile(new File(['{}'], 'message.json'), controller.signal);
  controller.abort();
  await expect(result).rejects.toMatchObject({ name: 'AbortError' });
  expect(abort).toHaveBeenCalledOnce();
  expect(reader.onload).toBeNull(); expect(reader.onerror).toBeNull(); expect(reader.onabort).toBeNull();
  expect(remove).toHaveBeenCalledWith('abort', expect.any(Function));
});

it('settles native FileReader abort events rather than hanging', async () => {
  vi.spyOn(FileReader.prototype, 'readAsArrayBuffer').mockImplementation(function (this: FileReader) {
    this.onabort?.(new ProgressEvent('abort') as ProgressEvent<FileReader>);
  });
  await expect(readOfflineSyncFile(new File(['{}'], 'message.json'))).rejects.toMatchObject({ name: 'AbortError' });
});
