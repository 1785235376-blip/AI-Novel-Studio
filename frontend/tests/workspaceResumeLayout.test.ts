import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';
const consumer = readFileSync(new URL('../src/experimental/workspaceResume.css', import.meta.url), 'utf8');
const shell = readFileSync(new URL('../src/ui/shell-overrides.css', import.meta.url), 'utf8');
const focus = readFileSync(new URL('../src/experimental/writingFocus.css', import.meta.url), 'utf8');
function rule(selector: string) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const result = consumer.match(new RegExp(`${escaped}\\s*\\{([^}]+)\\}`))?.[1];
  expect(result, `missing consumer rule ${selector}`).toBeTruthy(); return result!;
}
it('leaves original shell grid and feature-off editor participation unchanged', () => {
  expect(shell).toContain('.novel-writing-workspace{display:grid;grid-template-rows:auto minmax(320px,1fr) auto;height:100%;min-height:0}');
  expect(focus).toContain('.writing-editor-row{display:contents}');
  expect(rule('.novel-workspace-chrome')).toBe('min-width:0');
  expect(consumer).not.toMatch(/grid-template-rows|\.app-shell|\.main-workspace|\.writing-editor-row|!important/);
});
it('uses existing tokens for compact resume chrome and keeps actions outside truncation', () => {
  const summary = rule('.workspace-resume-summary');
  expect(summary).toContain('gap:var(--space-2)');
  expect(summary).toContain('padding:var(--space-2) var(--space-3)');
  expect(rule('.workspace-resume-summary>.ui-button')).toContain('flex:none');
  expect(rule('.workspace-resume-summary__content')).toContain('min-width:0');
  expect(consumer).not.toMatch(/#[0-9a-f]{3,8}\b|\brgb\(|\bhsl\(|\b\d+px\b/i);
});
it('bounds the stopping-note preview to one ellipsized line without truncating stored text', () => {
  const preview = rule('.workspace-resume-summary__content>strong,.workspace-resume-summary__note');
  for (const value of ['overflow:hidden', 'white-space:nowrap', 'text-overflow:ellipsis', 'margin:0']) expect(preview).toContain(value);
  expect(consumer).not.toMatch(/textarea|\.ProseMirror|\.tiptap/);
});
