import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';
it('preserves the inherited editor grid participation when focus tools are off', () => {
  const app = readFileSync(new URL('../App.tsx', import.meta.url), 'utf8');
  const css = readFileSync(new URL('./writingFocus.css', import.meta.url), 'utf8');
  expect(app).toContain("writingFocus ? 'writing-editor-row writing-focus-split' : 'writing-editor-row'");
  expect(css).toContain('.writing-editor-row{display:contents}');
  expect(css).toMatch(/\.writing-editor-row\.writing-focus-split\{[^}]*min-height:0;[^}]*overflow:hidden;/);
});
