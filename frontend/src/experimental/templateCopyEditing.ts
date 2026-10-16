/** Presentation helpers only. The original template owner validates every save. */
export type TemplateSection = { key: string; title: string; text: string; [key: string]: unknown };
type SectionContent = Record<string, unknown> & { sections: TemplateSection[] };
export function editableSections(raw: string): SectionContent | undefined {
  try {
    const value = JSON.parse(raw);
    if (!value || typeof value !== 'object' || Array.isArray(value) || !Array.isArray(value.sections) ||
      value.sections.length < 1 || value.sections.length > 20 || value.sections.some((section: unknown) => {
        if (!section || typeof section !== 'object' || Array.isArray(section)) return true;
        const s = section as Record<string, unknown>;
        return typeof s.key !== 'string' || !/^[a-z][a-z0-9_-]{0,39}$/.test(s.key) ||
          typeof s.title !== 'string' || !s.title.length || Array.from(s.title).length > 160 || typeof s.text !== 'string' || Array.from(s.text).length > 8000;
      }) || new Set(value.sections.map((s: TemplateSection) => s.key)).size !== value.sections.length) return undefined;
    return value;
  } catch { return undefined; }
}
export function editSection(raw: string, key: string, text: string): string {
  const value = editableSections(raw);
  if (!value || Array.from(text).length > 8000 || !value.sections.some(s => s.key === key)) throw new Error('Unsupported section edit');
  return JSON.stringify({ ...value, sections: value.sections.map(s => s.key === key ? { ...s, text } : s) }, null, 2);
}
/** Bounded changed block, not a minimal semantic diff. Original history stays visible. */
export function templateHistoryDiff(before: unknown, after: unknown) {
  const a = (JSON.stringify(before, null, 2) ?? 'null').split('\n');
  const b = (JSON.stringify(after, null, 2) ?? 'null').split('\n');
  let start = 0, endA = a.length, endB = b.length;
  while (start < endA && start < endB && a[start] === b[start]) start++;
  while (endA > start && endB > start && a[endA - 1] === b[endB - 1]) { endA--; endB--; }
  const removed = a.slice(start, endA), added = b.slice(start, endB);
  // Cap each side separately so a large removal never hides every addition.
  return { removed: removed.slice(0, 100), added: added.slice(0, 100), truncated: removed.length > 100 || added.length > 100,
    changed: removed.length > 0 || added.length > 0 };
}
