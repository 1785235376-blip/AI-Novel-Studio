import { createHash, webcrypto } from 'node:crypto';
import { afterEach, expect, it, vi } from 'vitest';
import { readOraFile } from './comicOraClient';
afterEach(() => vi.unstubAllGlobals());
it('derives exact archive SHA-256 and base64 from transient raw bytes', async () => {
  vi.stubGlobal('crypto', webcrypto);
  const raw = new Uint8Array(Array.from({ length: 65539 }, (_, index) => index % 256));
  const file = { size: raw.length, arrayBuffer: async () => raw.buffer } as File;
  const result = await readOraFile(file);
  expect(result.archive_sha256).toBe(createHash('sha256').update(raw).digest('hex'));
  expect(result.archive_base64).toBe(Buffer.from(raw).toString('base64'));
});
it.each([0, 21, 16 * 1024 * 1024 + 1])('rejects size %s before reading bytes', async size => {
  const arrayBuffer = vi.fn(); await expect(readOraFile({ size, arrayBuffer } as unknown as File)).rejects.toThrow(/16 MiB/); expect(arrayBuffer).not.toHaveBeenCalled();
});
