// @vitest-environment node
/* [HERMIA-FE-20261026 DCI] Vera dualcanvas MUST-FIX: VideoRebuild .mw-tree uses aria-pressed,
   but imageRebuild.css historically only styled aria-selected — VIDEO shot tree lost highlight. */
import {readFileSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {describe, expect, it} from 'vitest';

const cssPath = resolve(dirname(fileURLToPath(import.meta.url)), 'imageRebuild.css');

describe('imageRebuild.css mw-tree selection highlight (Vera dualcanvas P1)', () => {
  it('styles .mw-tree>button[aria-pressed="true"] so VIDEO shot tree selection highlights', () => {
    const css = readFileSync(cssPath, 'utf8');
    expect(css).toMatch(/\.mw-tree\s*>\s*button\[aria-pressed=["']true["']\]/);
  });
  it('keeps IMAGE aria-selected highlight (do not drop the old selector)', () => {
    const css = readFileSync(cssPath, 'utf8');
    expect(css).toMatch(/\.mw-tree\s*>\s*button\[aria-selected=["']true["']\]/);
  });
});
