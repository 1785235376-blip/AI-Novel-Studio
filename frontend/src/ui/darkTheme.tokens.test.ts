import {describe,expect,it} from 'vitest';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const tokens = readFileSync(fileURLToPath(new URL('./tokens.css', import.meta.url)), 'utf8');
const graph = readFileSync(fileURLToPath(new URL('../creative/graphCanvas.css', import.meta.url)), 'utf8');
const ui = readFileSync(fileURLToPath(new URL('./ui.css', import.meta.url)), 'utf8');
const compact = (v: string) => v.replace(/\s+/g, '');

describe('T-DARK dark theme tokens contract [HERMIA-FE-20261022]', () => {
  it('T-DARK-01 defaults to dark color-scheme and CapCut-like surfaces', () => {
    expect(tokens).toMatch(/color-scheme:\s*dark/);
    expect(tokens).toMatch(/--color-bg-app:\s*#0d0f12/);
    expect(tokens).toMatch(/--color-bg-surface:\s*#161a20/);
    expect(tokens).toMatch(/--color-bg-editor:\s*#1a1d21/);
    expect(tokens).toMatch(/--color-accent-primary:\s*#4db8c4/);
    expect(tokens).not.toMatch(/color-scheme:\s*light/);
  });

  it('T-DARK-02 exposes canvas tokens and graph/placeholder use them', () => {
    expect(tokens).toMatch(/--color-canvas-bg:\s*#0b0b0b/);
    expect(tokens).toMatch(/--color-canvas-grid:\s*#1a1a1a/);
    const g = compact(graph);
    expect(g).toContain('background:var(--color-canvas-bg)');
    expect(g).toContain('radial-gradient(var(--color-canvas-grid)');
    const u = compact(ui);
    expect(u).toContain('background-color:var(--color-canvas-bg)');
    expect(u).toContain('radial-gradient(var(--color-canvas-grid)');
  });

  it('T-DARK-03 defines premium motion tokens and respects reduced-motion', () => {
    expect(tokens).toMatch(/--motion-panel:\s*280ms/);
    expect(tokens).toMatch(/--ease-emphasized:\s*cubic-bezier\(0\.22,\s*1,\s*0\.36,\s*1\)/);
    expect(ui).toContain('prefers-reduced-motion');
    expect(ui).toContain('hermia-panel-in');
  });

  it('Lumen §3.1 semantic aliases map to --color-* terminals', () => {
    expect(tokens).toMatch(/--surface-chrome:\s*var\(--color-bg-app\)/);
    expect(tokens).toMatch(/--surface-canvas:\s*var\(--color-canvas-bg\)/);
    expect(tokens).toMatch(/--surface-panel:\s*var\(--color-bg-surface\)/);
    expect(tokens).toMatch(/--surface-elevated:\s*var\(--color-bg-elevated\)/);
    expect(tokens).toMatch(/--surface-editor-paper:\s*var\(--color-bg-editor\)/);
    expect(tokens).toMatch(/--text-primary:\s*var\(--color-text-primary\)/);
    expect(tokens).toMatch(/--text-muted:\s*var\(--color-text-muted\)/);
    expect(tokens).toMatch(/--border-subtle:\s*var\(--color-border-default\)/);
    expect(tokens).toMatch(/--accent:\s*var\(--color-accent-primary\)/);
  });
});
