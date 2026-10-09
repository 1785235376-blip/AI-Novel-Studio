import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const css = readFileSync(fileURLToPath(new URL('./creative.css', import.meta.url)), 'utf8').replace(/\s+/g, '');

describe('creative timeline sticky header stacking', () => {
  it('keeps the opaque header above scrolled controls inside its own token-based layer', () => {
    expect(css).toContain('.creative-production-timeline{flex:01auto;max-height:calc(var(--space-12)*5);overflow:auto;isolation:isolate}');
    expect(css).toContain('.creative-production-timeline>header{position:sticky;top:0;z-index:var(--z-dropdown);background:var(--color-bg-surface)}');
    expect(css).not.toContain('pointer-events:none');
  });
});
