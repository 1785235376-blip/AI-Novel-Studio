export type AudioDraftSummary = {
  id: string; title: string; version: number; timelineDigest: string; draftDigest: string; requestId: string;
  sourceId: string; sourceVersion: number; canvasId: string; canvasVersion: number; cardId: string;
  inMs: number; outMs: number; gainDb?: number; fadeInMs?: number; fadeOutMs?: number;
  templateGraphId?: string; templateVersion?: number; parentJobId?: string; parentJobVersion?: number;
};
const required = ['id','title','version','timelineDigest','draftDigest','requestId','sourceId','sourceVersion','canvasId','canvasVersion','cardId','inMs','outMs'] as const;
const optional = ['gainDb','fadeInMs','fadeOutMs','templateGraphId','templateVersion','parentJobId','parentJobVersion'] as const;
const name = (v: unknown) => typeof v === 'string' && !!v.trim() && v.length <= 240 && !/[\u0000-\u001f\u007f]/.test(v);
const version = (v: unknown) => typeof v === 'number' && Number.isSafeInteger(v) && v > 0;
const integer = (v: unknown, min: number, max: number) => typeof v === 'number' && Number.isSafeInteger(v) && v >= min && v <= max;
const digest = (v: unknown) => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const bad = (): never => { throw new Error('AUDIO_DRAFT_SUMMARY_INVALID'); };
/** Display projection only. The original owner must re-read and validate before restoring. */
export function checkedAudioDraftSummary(value: unknown): Readonly<AudioDraftSummary> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) bad();
  const row = {...value as Record<string, unknown>};
  if (required.some(k => !Object.hasOwn(row,k)) || Object.keys(row).some(k => ![...required,...optional].includes(k as never))) bad();
  if (['id','title','sourceId','canvasId','cardId'].some(k => !name(row[k])) || !version(row.version) || !version(row.sourceVersion) || !version(row.canvasVersion)
    || !digest(row.timelineDigest) || !digest(row.draftDigest) || typeof row.requestId !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(row.requestId)) bad();
  if (!integer(row.inMs,0,600000) || !integer(row.outMs,1,600000) || Number(row.outMs) <= Number(row.inMs) || Number(row.outMs)-Number(row.inMs)>120000) bad();
  if (Object.hasOwn(row,'gainDb') && (typeof row.gainDb !== 'number' || !Number.isFinite(row.gainDb) || row.gainDb < -60 || row.gainDb > 12)) bad();
  if (['fadeInMs','fadeOutMs'].some(k => Object.hasOwn(row,k) && !integer(row[k],0,120000)) || Number(row.fadeInMs ?? 0)+Number(row.fadeOutMs ?? 0)>Number(row.outMs)-Number(row.inMs)) bad();
  for (const [id,rev] of [['templateGraphId','templateVersion'],['parentJobId','parentJobVersion']] as const) {
    if (Object.hasOwn(row,id) !== Object.hasOwn(row,rev) || Object.hasOwn(row,id) && (!name(row[id]) || !version(row[rev]))) bad();
  }
  return Object.freeze({...row}) as Readonly<AudioDraftSummary>;
}
const functions = new WeakMap<Function, number>(); let functionCount = 0;
/** Functions are identities; serialization failure never grants a current lease. */
export function audioDraftStamp(value: unknown): string | undefined {
  try { return JSON.stringify(value,(_key,item) => {
    if (typeof item === 'function') { if (!functions.has(item)) functions.set(item,++functionCount); return `function:${functions.get(item)}`; }
    return item;
  }); } catch { return; }
}
