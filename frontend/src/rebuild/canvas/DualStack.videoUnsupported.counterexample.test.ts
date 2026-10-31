// @vitest-environment node
/**
 * Stage 4 counterexample: VIDEO DualStack must keep unsupported/unavailable markers
 * in source (no silent hide of "VIDEO 正式生成 / 执行：unsupported").
 * Static read — same style as Vera MUST-FIX CSS selector counterexample.
 */
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { zhCN } from '../../i18n/zh-CN';
import { en } from '../../i18n/en';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(resolve(here, 'DualStack.tsx'), 'utf8');

describe('Stage4 counterexample: VIDEO DualStack unsupported markers', () => {
  it('keeps data-unsupported=video-run and data-unavailable=canvas-run in DualStack source', () => {
    expect(src).toMatch(/data-unsupported=["']video-run["']/);
    expect(src).toMatch(/data-unavailable=["']canvas-run["']/);
    // [HERMIA-FE-20261031 DUALCANVAS-COMFY P2-1] 文案移入 i18n：源码引用键，词典里 zh/en 都保留 unsupported
    expect(src).toMatch(/tr\('dual\.video\.off'\)/);
    expect(zhCN['dual.video.off']).toMatch(/VIDEO 正式生成\s*\/\s*执行：unsupported/);
    expect(en['dual.video.off']).toMatch(/unsupported/);
  });

  it('does not gate video markers behind a hidden/false branch that always strips them', () => {
    // Counterexample: a silent-hide would remove the markers or only emit them for image.
    const videoSpan = src.match(/kind\s*===\s*['"]image['"][\s\S]{0,200}?data-unsupported=["']video-run["']/);
    // Marker should appear on the non-image / video side of the ternary (after `:`)
    expect(src).toMatch(/:\s*<span[^>]*data-unsupported=["']video-run["']/);
    expect(videoSpan || src.includes("kind === 'image'")).toBeTruthy();
  });
});
