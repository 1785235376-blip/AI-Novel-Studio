import { expect, it } from 'vitest';
import { editableSections, editSection, templateHistoryDiff } from './templateCopyEditing';
it('updates text while preserving keys, titles and other fields', () => {
  const content = { sections: [{ key: 'purpose', title: '用途', text: '旧文', future: 'retained' }], provenance: 'retained' };
  expect(JSON.parse(editSection(JSON.stringify(content), 'purpose', '新文'))).toEqual({ ...content, sections: [{ ...content.sections[0], text: '新文' }] });
  expect(content.sections[0].text).toBe('旧文');
});
it('does not project malformed, duplicate or oversized sections', () => {
  for (const content of ['{', '{}', '[]', '{"sections":[]}', JSON.stringify({ sections: [{ key: 'x', title: 'x', text: 'x'.repeat(8001) }] }), JSON.stringify({ sections: [{ key: 'x', title: 'x', text: '' }, { key: 'x', title: 'x', text: '' }] })]) expect(editableSections(content)).toBeUndefined();
  expect(() => editSection('{}', 'x', '')).toThrow();
});
it('shows changed blocks bounded on both sides', () => {
  expect(templateHistoryDiff({ x: 1 }, { x: 1 }).changed).toBe(false);
  expect(templateHistoryDiff({ x: 1 }, { x: 2 })).toEqual({ removed: ['  "x": 1'], added: ['  "x": 2'], changed: true, truncated: false });
  const diff = templateHistoryDiff(Array.from({ length: 300 }, (_, i) => i), Array.from({ length: 300 }, (_, i) => i + 1000));
  expect(diff.truncated).toBe(true); expect(diff.removed).toHaveLength(100); expect(diff.added).toHaveLength(100);
});

it('counts astral text using the original owner Unicode code-point boundary', () => {
  const raw = JSON.stringify({ sections: [{ key: 'x', title: 'x', text: '🙂'.repeat(8000) }] });
  expect(editableSections(raw)).toBeTruthy();
  expect(editSection(raw, 'x', '🙂'.repeat(8000))).toBeTruthy();
  expect(() => editSection(raw, 'x', '🙂'.repeat(8001))).toThrow();
});
