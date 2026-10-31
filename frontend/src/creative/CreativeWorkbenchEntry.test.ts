import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const app = readFileSync(fileURLToPath(new URL('../App.tsx', import.meta.url)), 'utf8');
const css = readFileSync(fileURLToPath(new URL('./creative.css', import.meta.url)), 'utf8').replace(/\s+/g, '');

describe('V2 entry placement regression', () => {
  it('places the gated entry in chapter scroll flow before the chapter tree, outside the anchored launcher slot', () => {
    const scroller = app.indexOf('<div className="sidebar-chapter-scroll" data-testid="chapter-tree-scroll">');
    const entry = app.indexOf('打开 V2 创作工作台');
    const chapterTree = app.indexOf('<ChapterTree', scroller);
    const launcher = app.indexOf('<FeatureLauncher', chapterTree);
    expect(scroller).toBeGreaterThan(-1);
    expect(entry).toBeGreaterThan(scroller);
    expect(entry).toBeLessThan(chapterTree);
    expect(launcher).toBeGreaterThan(chapterTree);
    expect(app.lastIndexOf('打开 V2 创作工作台')).toBe(entry);
    expect(app.slice(scroller, chapterTree)).toContain('!creativeWorkbenchOpen && experimentalFlags.data?.features["experimental.narrative_production_v2"] === true');
    expect(app.slice(scroller, chapterTree)).toContain('disabled={composing}');
  });

  it('uses normal-flow token spacing without raising V2 above the existing launcher', () => {
    const entryRule = css.match(/\.creative-workbench-entry\{([^}]*)\}/)?.[1];
    expect(entryRule).toBe('padding:var(--space-2)0');
    expect(css).toContain('.creative-workbench-entry>.ui-button{width:100%}');
    expect(entryRule).not.toContain('position:');
    expect(entryRule).not.toContain('z-index:');
    expect(entryRule).not.toContain('pointer-events:');
  });
});
