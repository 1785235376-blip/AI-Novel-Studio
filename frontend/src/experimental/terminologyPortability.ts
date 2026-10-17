import type { ExperimentalClient } from './api';
import type { LanguageEdition, TermInput } from './multilingualEditionsClient';
export const MAX_GLOSSARY_BYTES = 512 * 1024;
export const MAX_GLOSSARY_RULES = 100;
export type GlossaryDocument = { schema: 'language-terminology-v1'; source_language: string; target_language: string; rules: TermInput[] };
export type GlossaryReference = { kind: 'file' | 'existing'; index: number };
export type GlossaryPreview = { preview_digest: string; entries: { index: number; rule: TermInput; duplicates: GlossaryReference[]; conflicts: GlossaryReference[]; eligible: boolean }[]; remaining_capacity: number; edition_version: number; draft_only: true };
export type GlossaryExport = { filename: string; mime: string; content: string; rule_count: number; draft_only: true; published: false };
const fields = ['source_term', 'source_aliases', 'preferred', 'target_aliases', 'forbidden', 'category', 'strategy', 'match', 'note'].sort();
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const exact = (value: Record<string, unknown>, keys: string[]) => Object.keys(value).sort().join('|') === [...keys].sort().join('|');
const validString = (value: unknown, min: number, max: number): value is string => {
  if (typeof value !== 'string' || [...value].length < min || [...value].length > max || /^\p{White_Space}|\p{White_Space}$/u.test(value)) return false;
  for (const char of value) {
    const code = char.codePointAt(0)!;
    if ((code < 32 && !['\n', '\r', '\t'].includes(char)) || (code >= 0xd800 && code <= 0xdfff)) return false;
  }
  return true;
};
/** Local format checks only. The owner checks duplicate JSON keys, authority,
 * current conflicts and the complete schema again before any write. */
export function parseGlossary(text: string): GlossaryDocument {
  const invalid = () => new Error('术语文件无效：只接受封闭 v1 JSON、有效 Unicode 和原术语长度限制，不自动修剪文字。');
  if (new TextEncoder().encode(text).length > MAX_GLOSSARY_BYTES) throw invalid();
  let value: unknown;
  try { value = JSON.parse(text); } catch { throw invalid(); }
  if (!object(value) || !exact(value, ['schema', 'source_language', 'target_language', 'rules']) || value.schema !== 'language-terminology-v1') throw invalid();
  const language = /^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8}){0,7}$/;
  if (!validString(value.source_language, 2, 64) || !language.test(value.source_language) || !validString(value.target_language, 2, 64) || !language.test(value.target_language)) throw invalid();
  if (!Array.isArray(value.rules) || value.rules.length > MAX_GLOSSARY_RULES) throw invalid();
  for (const rule of value.rules) {
    if (!object(rule) || !exact(rule, fields) || !validString(rule.source_term, 1, 160) || !validString(rule.preferred, 1, 160) || !validString(rule.note, 0, 1000)) throw invalid();
    for (const key of ['source_aliases', 'target_aliases', 'forbidden']) {
      const list = rule[key];
      if (!Array.isArray(list) || list.length > 20 || list.some(item => !validString(item, 1, 160)) || new Set(list).size !== list.length) throw invalid();
    }
    if (!['term', 'character', 'title', 'place', 'world'].includes(String(rule.category)) || !['meaning', 'transliteration', 'preserve'].includes(String(rule.strategy)) || !['substring', 'word'].includes(String(rule.match))) throw invalid();
    const sourceAliases = rule.source_aliases as string[], targetAliases = rule.target_aliases as string[], forbidden = rule.forbidden as string[];
    if ([rule.preferred, ...targetAliases].some(term => forbidden.includes(term as string))) throw invalid();
    if (rule.strategy === 'preserve' && (rule.preferred !== rule.source_term || sourceAliases.length || targetAliases.length)) throw invalid();
  }
  return value as GlossaryDocument;
}
export async function readGlossaryFile(file: File): Promise<string> {
  if (file.size > MAX_GLOSSARY_BYTES) throw new Error('术语文件不能超过 512 KiB。');
  const bytes = await file.arrayBuffer();
  if (bytes.byteLength > MAX_GLOSSARY_BYTES) throw new Error('术语文件不能超过 512 KiB。');
  const text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
  parseGlossary(text);
  return text;
}
// Captured clients identify the original session/scope. Keep unknown admissions
// across edition switches and panel remounts; only a fresh owner read clears one.
const unknownAdmissions = new WeakMap<ExperimentalClient, Map<string, number>>();
let admissionSequence = 0;
export function glossaryAdmissionToken(client: ExperimentalClient, id: string) { return unknownAdmissions.get(client)?.get(id); }
export function startGlossaryAdmission(client: ExperimentalClient, id: string) {
  if (!unknownAdmissions.has(client)) unknownAdmissions.set(client, new Map());
  const token = ++admissionSequence; unknownAdmissions.get(client)!.set(id, token); return token;
}
export function clearGlossaryAdmission(client: ExperimentalClient, id: string, token: number | undefined) {
  if (token === undefined || glossaryAdmissionToken(client, id) !== token) return false;
  unknownAdmissions.get(client)!.delete(id); return true;
}
export function terminologyPortabilityClient(client: ExperimentalClient) {
  const base = (edition: LanguageEdition) => `/language-editions/${encodeURIComponent(edition.id)}/glossary`;
  return {
    reconcile: (edition: LanguageEdition) => client.get<LanguageEdition>(`/language-editions/${encodeURIComponent(edition.id)}`),
    preview: (edition: LanguageEdition, document: string) => client.post<GlossaryPreview>(base(edition) + '/preview', { expected_version: edition.version, document }),
    adopt: (edition: LanguageEdition, document: string, preview: GlossaryPreview, selected_indices: number[]) => client.post<LanguageEdition>(base(edition) + '/adopt', { expected_version: edition.version, document, preview_digest: preview.preview_digest, selected_indices }),
    export: (edition: LanguageEdition) => client.post<GlossaryExport>(base(edition) + '/export', { expected_version: edition.version }),
  };
}
