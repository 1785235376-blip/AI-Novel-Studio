// [HERMIA-FE-20261025 LAYOUT-P2] 1024/1100 下隐藏左栏后，网格不得留 0 宽首列（曾导致空态逐字竖排）。
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const css = (p: string) => readFileSync(resolve(__dirname, p), 'utf8');
const narrow = (src: string) => {
  const m = src.match(/@media \(max-width:1100px\)\{([^\n]*)\}/);
  expect(m).not.toBeNull();
  return m![1];
};

describe('narrow layout grids', () => {
  it('image/audio .mw-split drops the hidden left column instead of a 0 track', () => {
    const rule = narrow(css('image/imageRebuild.css'));
    expect(rule).toContain('.mw-left{display:none}');
    const cols = rule.match(/\.mw-split\{grid-template-columns:([^}]*)\}/)![1];
    expect(cols.split(/\s+(?![^(]*\))/)).toHaveLength(2);
    expect(cols).not.toMatch(/^0\s/);
    expect(cols).toMatch(/^minmax\(320px,1fr\)/);
  });
  it('video .vid-body is a single main column when the rail is hidden', () => {
    const rule = narrow(css('video/videoRebuild.css'));
    expect(rule).toContain('.vid-rail{display:none}');
    expect(rule).toContain('.vid-body{grid-template-columns:minmax(0,1fr)}');
  });
  it('empty-state actions may wrap', () => {
    expect(css('image/imageRebuild.css')).toMatch(/\.img-empty button\{white-space:normal/);
  });
  it('header tightens at <=1200px so Settings stays in viewport', () => {
    const s = css('protoShell.css');
    expect(s).toMatch(/@media \(max-width:1200px\)\{[^}]*\.global-header\{gap:8px/);
  });
});
