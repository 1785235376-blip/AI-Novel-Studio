import type { ExperimentalClient } from './api';
import type { DirectorScreenplay } from './directorClient';
export type Rational = { numerator: number; denominator: number };
export type ExchangeReport = { path: string; code: string; severity: 'LOSS' | 'WARNING' };
export type ExchangeRecord = { id: string; version: number; status: string; origin: string; stale: boolean; filename?: string;
  summary?: { name: string; duration_semantics: string; tracks: { name: string; kind: string; duration_seconds: Rational; cuts: { name: string; kind: string; start_seconds: Rational; duration_seconds: Rational }[] }[] };
  loss_report?: ExchangeReport[]; media?: { name: string; state: string; target_url: string | null }[];
};
export type ExchangeCatalog = { screenplays: DirectorScreenplay[]; assets: { id: string; filename: string; media_type: string; version: number }[];
  parser: { available: boolean; required_version: string; runtime_install: false }; limitations: string[] };
export function timelineExchangeClient(client: ExperimentalClient) {
  return {
    catalog: (signal?: AbortSignal) => client.get<ExchangeCatalog>('/timeline-exchange/catalog', signal),
    records: (signal?: AbortSignal) => client.get<{ items: ExchangeRecord[] }>('/timeline-exchange/records', signal),
    importFile: (filename: string, content: string) => client.post<ExchangeRecord>('/timeline-exchange/import', { filename, content }),
    fromScreenplay: (screenplay: DirectorScreenplay, rate: [number, number], shots: { shot_id: string; asset_id?: string }[]) => client.post<ExchangeRecord>('/timeline-exchange/from-screenplay', { screenplay_id: screenplay.id, expected_screenplay_version: screenplay.edit_version, rate_numerator: rate[0], rate_denominator: rate[1], shots }),
    download: (row: ExchangeRecord, acknowledge: boolean) => client.blob(`/timeline-exchange/records/${encodeURIComponent(row.id)}/file?expected_version=${row.version}&acknowledge_losses=${acknowledge}`),
  };
}
export function readOtioFile(file: File): Promise<string> {
  if (!/\.otio$/i.test(file.name) || !file.size || file.size > 2 * 1024 * 1024) return Promise.reject(new Error('请选择不超过 2 MiB 的非空 .otio 文件。'));
  return new Promise((resolve, reject) => {
    const reader = new FileReader(); reader.onerror = () => reject(new Error('文件无法读取。'));
    reader.onload = () => {
      try { resolve(new TextDecoder('utf-8', { fatal: true }).decode(reader.result as ArrayBuffer)); }
      catch { reject(new Error('OTIO 文件必须是有效的 UTF-8 文本。')); }
    };
    reader.readAsArrayBuffer(file);
  });
}
export function saveOtioFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob); const link = document.createElement('a');
  link.href = url; link.download = filename; document.body.appendChild(link); link.click(); link.remove();
  // Release only after the browser has consumed the current download action.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
