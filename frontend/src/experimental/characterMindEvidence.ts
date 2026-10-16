import type { Row } from './api';
import { validStoryEvidence, type StoryEvidence } from './StoryGraphEvidenceReview';

export type CharacterMindEvidence = {
  characterId: string;
  category: string;
  text: string;
  evidenceStatus: string;
  evidence: StoryEvidence;
};
const object = (value: unknown): value is Record<string, any> => !!value && typeof value === 'object' && !Array.isArray(value);
const text = (value: unknown, max = 160): value is string => typeof value === 'string' && !!value.trim() && Array.from(value).length <= max;
const categories = ['KNOWN_FACT', 'BELIEF', 'FALSE_BELIEF', 'SECRET', 'GOAL', 'FEAR', 'VALUE', 'EMOTION', 'INTENT', 'RELATIONSHIP_STATE'];
export function validCharacterMindEvidence(pin: CharacterMindEvidence): boolean {
  return object(pin) && text(pin.characterId) && categories.includes(pin.category) && typeof pin.text === 'string' && Array.from(pin.text).length <= 8000 && ['EXPLICIT', 'HYPOTHESIS'].includes(pin.evidenceStatus) && validStoryEvidence(pin.evidence);
}

/** Author-only reconciliation. Never fetch author records from character projection. */
export function matchesCharacterMindEvidence(row: Row, pin: CharacterMindEvidence): boolean {
  if (!validCharacterMindEvidence(pin) || !object(row)) return false;
  const evidence = pin.evidence, data = row.data;
  if (row.kind !== 'KNOWLEDGE_EVENT' || row.status !== 'APPROVED' || row.stale !== false || row.id !== evidence.record_id || row.version !== evidence.record_version || row.chapter_id !== evidence.chapter_id || !text(row.title, 240) || !object(data) || !object(row.sources)) return false;
  if (data.character_id !== pin.characterId || data.category !== pin.category || data.evidence_status !== pin.evidenceStatus || !text(data.state_key) || !['LEARN', 'HEARSAY', 'MISUNDERSTAND', 'CORRECT', 'GOAL_CHANGE', 'SET_STATE'].includes(data.operation)) return false;
  if (typeof data.value !== 'string' || Array.from(data.value).length > 8000 || !['KNOWN_FACT', 'SECRET'].includes(pin.category) && data.value !== pin.text) return false;
  if (['KNOWN_FACT', 'BELIEF', 'FALSE_BELIEF', 'SECRET', 'RELATIONSHIP_STATE'].includes(pin.category) && !text(data.relation_id)) return false;
  if (data.operation === 'MISUNDERSTAND' && data.category !== 'FALSE_BELIEF' || data.operation === 'HEARSAY' && !['BELIEF', 'FALSE_BELIEF'].includes(data.category) || data.operation === 'GOAL_CHANGE' && data.category !== 'GOAL') return false;
  if (!Number.isSafeInteger(row.event_order) || row.event_order < 0 || row.event_order > 1000000) return false;
  if (!text(data.calendar, 80) || ['world_time', 'valid_from', 'valid_to'].some(key => data[key] != null && !Number.isSafeInteger(data[key]))) return false;
  if (typeof data.valid_from === 'number' && typeof data.valid_to === 'number' && data.valid_to <= data.valid_from) return false;
  if (['scene_id', 'until_chapter_id', 'psychology_id', 'relation_id'].some(key => data[key] != null && (typeof data[key] !== 'string' || Array.from(data[key]).length > 160))) return false;
  if (!Array.isArray(data.evidence) || data.evidence.length > 20 || !data.evidence.every((quote: unknown) => object(quote) && text(quote.chapter_id) && Object.hasOwn(evidence.source_versions, quote.chapter_id) && text(quote.quote, 4000) && Number.isSafeInteger(quote.start) && quote.start >= 0)) return false;
  const keys = Object.keys(evidence.source_versions);
  return keys.length === Object.keys(row.sources).length && keys.every(key => object(row.sources[key]) && row.sources[key].version === evidence.source_versions[key].version && row.sources[key].digest === evidence.source_versions[key].digest);
}
