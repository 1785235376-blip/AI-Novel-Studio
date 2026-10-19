import type { StudioGraphTransport } from '../creative/studioGraphClient';
export type FactPin = { id: string; version: number; digest: string };
export type StoryFact = FactPin & { title: string };
export type FactPurpose = 'APPEARANCE_STATE' | 'PROP_STATE' | 'KNOWLEDGE' | 'CAUSAL_CONTEXT';
export type FactTarget = { document_id: string; document_version: number; document_digest: string;
  scene_id: string; shot_id: string; shot_version: number; shot_digest: string };
export type FactUse = { id: string; version: number; fact: FactPin;
  current_fact: StoryFact & { status: string }; target: FactTarget; state: 'CURRENT' | 'STALE';
  blockers: string[]; purpose: FactPurpose; rationale: string;
  assets: { asset_id: string; version: number; digest: string; kind: 'image' | 'video' }[] };
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const text = (v: unknown): v is string => typeof v === 'string' && v.length > 0;
const version = (v: unknown) => Number.isSafeInteger(v) && Number(v) > 0;
const digest = (v: unknown) => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const pin = (v: unknown) => object(v) && text(v.id) && version(v.version) && digest(v.digest);
export const purposes: FactPurpose[] = ['APPEARANCE_STATE', 'PROP_STATE', 'KNOWLEDGE', 'CAUSAL_CONTEXT'];
function invalid(): never { throw new Error('事实依赖回执不完整，请重新读取。'); }
export function checkedFacts(value: unknown): StoryFact[] {
  if (!object(value) || value.contract !== 'creative-story-facts/1' || value.coverage !== 'APPROVED_WORLD_FACT_RELATIONS_ONLY'
    || !Array.isArray(value.items) || !value.items.every(v => pin(v) && object(v) && typeof v.title === 'string')) invalid();
  return value.items as StoryFact[];
}
export function checkedImpact(value: unknown, documentId: string): FactUse[] {
  if (!object(value) || value.contract !== 'creative-fact-impact/1'
    || value.coverage !== 'EXPLICIT_CONFIRMED_FACT_USES_AND_CURRENT_SHOT_ASSET_BINDINGS'
    || value.unrecorded_dependencies !== 'UNKNOWN' || value.automatic_regeneration !== false || value.model_called !== false
    || !Array.isArray(value.items) || value.items.length > 200) invalid();
  const ids = new Set<string>();
  for (const row of value.items) {
    if (!object(row) || !text(row.id) || !version(row.version) || !pin(row.fact) || !pin(row.current_fact)
      || !object(row.current_fact) || typeof row.current_fact.title !== 'string' || !text(row.current_fact.status)
      || !['CURRENT', 'STALE'].includes(String(row.state)) || !purposes.includes(row.purpose as FactPurpose)
      || typeof row.rationale !== 'string' || !Array.isArray(row.blockers) || !row.blockers.every(text)
      || !object(row.target) || row.target.document_id !== documentId || !version(row.target.document_version)
      || !digest(row.target.document_digest) || !text(row.target.scene_id) || !text(row.target.shot_id)
      || !version(row.target.shot_version) || !digest(row.target.shot_digest) || !Array.isArray(row.assets)
      || !row.assets.every(a => object(a) && text(a.asset_id) && version(a.version) && digest(a.digest) && ['image', 'video'].includes(String(a.kind)))) invalid();
  }
  for (const row of value.items as FactUse[]) {
    if (ids.has(row.id) || row.assets.length > 2 || new Set(row.assets.map(asset => asset.asset_id)).size !== row.assets.length) invalid();
    ids.add(row.id);
  }
  return value.items as FactUse[];
}
export function createStoryFactClient(projectId: string, transport: StudioGraphTransport) {
  const base = `/api/novels/${encodeURIComponent(projectId)}/experimental/creative`;
  const document = (id: string) => `${base}/documents/${encodeURIComponent(id)}`;
  return {
    facts: async () => checkedFacts(await transport.json<unknown>(`${base}/story-facts`, 'GET')),
    impact: async (id: string) => checkedImpact(await transport.json<unknown>(`${document(id)}/fact-uses`, 'GET'), id),
    confirm: async (target: FactTarget, fact: FactPin, purpose: FactPurpose, rationale: string) => {
      const result = await transport.json<unknown>(`${document(target.document_id)}/shots/${encodeURIComponent(target.shot_id)}/fact-uses`, 'POST', {
        expected_version: target.document_version, document_digest: target.document_digest,
        shot_version: target.shot_version, shot_digest: target.shot_digest,
        fact: { id: fact.id, version: fact.version, digest: fact.digest }, purpose, rationale, confirmed: true,
      });
      if (!object(result) || !text(result.id) || !version(result.version) || result.status !== 'CONFIRMED') invalid();
      return { id: result.id, version: Number(result.version) };
    },
  };
}
