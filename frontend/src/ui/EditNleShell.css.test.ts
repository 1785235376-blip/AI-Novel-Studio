// [HERMIA-FE-20261030 B3] Vera P3：EditNleShell 渐变 / 片段色不得硬编码 hex，必须走主题 token（浅色 / 深色各自定义）。
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const css = (p: string) => readFileSync(resolve(__dirname, p), 'utf8');
const NEW_TOKENS = ['--stg-mon-tint', '--stg-mon-tint-src', '--stg-clip', '--stg-clip-line'];

describe('EditNleShell theme tokens', () => {
  it('has no raw hex colour outside var() fallbacks', () => {
    const src = css('EditNleShell.css').replace(/\/\*[\s\S]*?\*\//g, '').replace(/var\(--[a-z0-9-]+,\s*#[0-9a-fA-F]{3,8}\)/g, '');
    expect(src.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).toEqual([]);
  });
  it('the replacement tokens exist in both dark and light themes', () => {
    const tokens = css('tokens.css');
    const dark = tokens.slice(tokens.indexOf('[data-theme="dark"]'), tokens.indexOf('[data-theme="light"]'));
    const light = tokens.slice(tokens.indexOf('[data-theme="light"]'));
    for (const t of NEW_TOKENS) { expect(dark).toContain(`${t}:`); expect(light).toContain(`${t}:`); }
  });
});
