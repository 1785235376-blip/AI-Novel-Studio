import { expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const css = fs.readFileSync(path.join(root, 'src/interop/localTutor.css'), 'utf8');
it('consumes DS tokens and responsive bounds without modifying protected shell geometry', () => {
  expect(css).not.toMatch(/#[0-9a-f]{3,8}\b|\brgb\(|\bhsl\(/i);
  expect(css).not.toMatch(/\b\d+(?:px|rem)\b/);
  expect(css).toContain('var(--layout-workspace-min)'); expect(css).toContain('var(--space-8)');
  expect(css).toContain('calc(100vh - var(--space-8))'); expect(css).toContain('var(--z-dialog)');
  expect(css).not.toMatch(/\.(?:app-shell|global-header|module-switcher|context-bar|status-bar|workspace-sidebar)\s*\{/);
});
it('uses shared primitives and never gives guidance direct write or URI navigation authority', () => {
  const source = fs.readFileSync(path.join(root, 'src/interop/LocalTutorIntegration.tsx'), 'utf8');
  expect(source).toContain("from '../ui/primitives'"); expect(source).toContain('createPortal(body, document.body)');
  expect(source).not.toMatch(/dangerouslySetInnerHTML|location\.(?:href|assign|replace)|window\.open|api\.saveChapter|api\.accept|modelCenterStartRuntime/);
});
