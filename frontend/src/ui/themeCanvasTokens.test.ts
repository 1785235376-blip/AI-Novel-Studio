// [HERMIA-FE-20261026 THEME] 画布 / 剪辑台 / 预览舞台颜色跟主题：用到的 token 在深浅两套里都有定义；浅色底是浅的；深色值保持原样。
import {describe, it, expect} from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
const src = path.resolve(__dirname, '..');
const read = (p: string) => fs.readFileSync(path.join(src, p), 'utf8');
const tokens = read('ui/tokens.css');
const block = (sel: string) => { const i = tokens.indexOf(sel); const j = tokens.indexOf('}', i); return tokens.slice(i, j); };
const DARK = block(':root,\n[data-theme="dark"]'), LIGHT = block('[data-theme="light"] {');
const val = (b: string, t: string) => b.match(new RegExp(`${t.replace(/[-]/g, '\\-')}:\\s*([^;]+);`))?.[1]?.trim();
const FILES = ['rebuild/canvas/rebuildCanvas.css', 'rebuild/edit/editRebuild.css', 'ui/EditNleShell.css', 'rebuild/video/videoRebuild.css', 'rebuild/audio/audioRebuild.css', 'rebuild/image/imageRebuild.css', 'rebuild/assets/assetsRebuild.css'];
const lum = (hex: string) => { const h = hex.replace('#', ''); const [r, g, b] = [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16) / 255).map(v => v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
describe('theme canvas / edit-desk tokens', () => {
  it('every --cv-* / --stg-* used in the stage CSS is defined in BOTH dark and light', () => {
    const used = new Set(FILES.flatMap(f => [...read(f).matchAll(/var\((--(?:cv|stg)-[a-z0-9-]+)/g)].map(m => m[1])));
    expect(used.size).toBeGreaterThan(30);
    for (const t of used) { expect(val(DARK, t), `dark ${t}`).toBeTruthy(); expect(val(LIGHT, t), `light ${t}`).toBeTruthy(); }
  });
  it('dark keeps the previous ComfyUI-like values exactly; light surfaces are light', () => {
    expect(val(DARK, '--cv-bg')).toBe('#0d0f13'); expect(val(DARK, '--cv-node')).toBe('#1c2129'); expect(val(DARK, '--stg-tl')).toBe('#232830'); expect(val(DARK, '--stg-mon')).toBe('#1a1d24');
    for (const t of ['--cv-bg', '--cv-node', '--cv-input', '--stg-mon', '--stg-tl', '--stg-tools', '--stg-ruler', '--stg-track', '--stg-frame-a', '--stg-frame-b', '--stg-ph-a', '--stg-ph-b']) expect(lum(val(LIGHT, t)!), t).toBeGreaterThan(0.55);
    for (const t of ['--cv-ink', '--stg-ink', '--stg-ink-tl']) expect(lum(val(LIGHT, t)!), t).toBeLessThan(0.05);
  });
  it('no hard-coded dark surface literals left on canvas / timeline / monitor backgrounds', () => {
    const bad = /(background(-color)?|fill)\s*:\s*(#0d0f13|#1c2129|#1a1d24|#232830|#2a303a|#1e232b|#1a1e26|#1b1e24|#000)\b/;
    for (const f of FILES) for (const line of read(f).split('\n')) if (!/\.clip|comic-cell|\.bub|\.dual-cv__panes/.test(line)) expect(bad.test(line), `${f}: ${line.slice(0, 120)}`).toBe(false);
    expect(read('rebuild/canvas/RebuildCanvas.tsx')).not.toMatch(/fill="#8a93a5"/);
  });
});
