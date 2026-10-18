import type { ExperimentalClient } from './api';
import type { ComicRecord } from './comicLayoutsClient';
export type OraLayer = { name: string; x: number; y: number; width: number; height: number; visible: boolean; opacity_percent: number; png_sha256: string; asset_id: string; state: 'PENDING' | 'STAGED' | 'REVIEWED' };
export type OraReceipt = { id: string; version: number; archive_sha256: string; status: string; steps: OraLayer[]; losses: string[]; review_digest?: string; review_license_note?: string; manifest_digest?: string; attachment?: { page_id?: string } };
export type OraPreview = { report: { archive_sha256: string; width: number; height: number; layers: OraLayer[]; losses: string[] }; thumbnail_base64: string };
export type OraManifest = { manifest_digest: string; manifest: { page: { width: number; height: number }; layers: OraLayer[] } };
export type OraBytes = { archive_base64: string; archive_sha256: string };
const root = '/comic-layouts/ora-imports';
export function comicOraClient(client: ExperimentalClient) {
  const path = (receipt: OraReceipt) => `${root}/${encodeURIComponent(receipt.id)}`;
  return {
    list: (signal?: AbortSignal) => client.get<{ receipts: OraReceipt[] }>(root, signal),
    status: (receipt: OraReceipt) => client.get<OraReceipt>(path(receipt)),
    preview: (bytes: OraBytes) => client.post<OraPreview>(root + '/preview', bytes),
    prepare: (bytes: OraBytes, request_key: string) => client.post<OraReceipt>(root, { ...bytes, request_key }),
    stage: (receipt: OraReceipt, bytes: OraBytes) => client.post<OraReceipt>(path(receipt) + '/stage', { ...bytes, max_steps: 8 }),
    manifest: (receipt: OraReceipt, bytes: OraBytes) => client.post<OraManifest>(path(receipt) + '/review-manifest', bytes),
    candidate: (receipt: OraReceipt, index: number) => client.blob(path(receipt) + `/candidates/${index}`),
    review: (receipt: OraReceipt, bytes: OraBytes, manifest_digest: string, license_note: string) => client.post<OraReceipt>(path(receipt) + '/review', { ...bytes, manifest_digest, license_note, acknowledge_raster_text: true, max_steps: 8 }),
    attach: (receipt: OraReceipt, page: ComicRecord) => client.post<{ receipt: OraReceipt; page: ComicRecord }>(path(receipt) + '/attach', { page_id: page.id, expected_page_version: page.version, review_digest: receipt.review_digest }),
  };
}
// Bytes stay within the mounted workflow. Nothing is placed in browser storage.
export async function readOraFile(file: File): Promise<OraBytes> {
  if (file.size < 22 || file.size > 16 * 1024 * 1024) throw new Error('ORA 文件必须为 22 字节至 16 MiB。');
  const buffer = await file.arrayBuffer(), bytes = new Uint8Array(buffer);
  const digest = await globalThis.crypto.subtle.digest('SHA-256', buffer);
  let binary = ''; for (let i = 0; i < bytes.length; i += 32768) binary += String.fromCharCode(...bytes.subarray(i, i + 32768));
  return { archive_base64: btoa(binary), archive_sha256: Array.from(new Uint8Array(digest), n => n.toString(16).padStart(2, '0')).join('') };
}
export function oraThumbnail(base64: string): Blob { return new Blob([Uint8Array.from(atob(base64), c => c.charCodeAt(0))], { type: 'image/png' }); }
