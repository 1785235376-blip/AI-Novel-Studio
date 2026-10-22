/** [HERMIA-FE-20261022 X-UX-08] pure isolation helpers + App wiring contract */
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {describe, expect, it} from 'vitest';
import {
  EMPTY_EDITOR_SELECTION,
  MEDIA_OR_TOOL_MODULES,
  NOVEL_CENTER_FORBIDDEN_SELECTORS,
  mediaShellForModule,
  novelCenterAllowsMediaShell,
  shouldRestoreNovelWriteOnEnter,
} from './moduleSwitchIsolation';

describe('X-UX-08 moduleSwitchIsolation helpers', () => {
  it('restores write only when entering NOVEL from a non-novel module', () => {
    expect(shouldRestoreNovelWriteOnEnter('VIDEO', 'NOVEL')).toBe(true);
    expect(shouldRestoreNovelWriteOnEnter('EDIT', 'NOVEL')).toBe(true);
    expect(shouldRestoreNovelWriteOnEnter('IMAGE', 'NOVEL')).toBe(true);
    expect(shouldRestoreNovelWriteOnEnter('NOVEL', 'NOVEL')).toBe(false);
    expect(shouldRestoreNovelWriteOnEnter(undefined, 'NOVEL')).toBe(false);
    expect(shouldRestoreNovelWriteOnEnter('NOVEL', 'VIDEO')).toBe(false);
    expect(shouldRestoreNovelWriteOnEnter('VIDEO', 'EDIT')).toBe(false);
  });

  it('forbids media/NLE shells inside novel center', () => {
    expect(novelCenterAllowsMediaShell('NOVEL')).toBe(false);
    for (const m of MEDIA_OR_TOOL_MODULES) {
      expect(novelCenterAllowsMediaShell(m)).toBe(true);
    }
  });

  it('maps only media modules to data-module-shell markers', () => {
    expect(mediaShellForModule('VIDEO')).toBe('VIDEO');
    expect(mediaShellForModule('EDIT')).toBe('EDIT');
    expect(mediaShellForModule('NOVEL')).toBeNull();
    expect(mediaShellForModule('CONTROL')).toBeNull();
    expect(NOVEL_CENTER_FORBIDDEN_SELECTORS.some(s => s.includes('edit-nle'))).toBe(true);
    expect(EMPTY_EDITOR_SELECTION).toEqual({from: 0, to: 0, text: ''});
  });
});

describe('X-UX-08 App wiring contract', () => {
  const app = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');

  it('early-returns ModuleWorkspaceRoutes when studioModule !== NOVEL (media never in novel center)', () => {
    expect(app).toMatch(/if \(studioModule !== "NOVEL"\) return[\s\S]*<ModuleWorkspaceRoutes/);
    expect(app).toContain('shouldRestoreNovelWriteOnEnter');
    expect(app).toContain('EMPTY_EDITOR_SELECTION');
    expect(app).toContain('X-UX-08');
    // restore write + clear selection on media → NOVEL
    expect(app).toMatch(/shouldRestoreNovelWriteOnEnter\(studioModule, module\)/);
    expect(app).toMatch(/setPanel\("write"\)/);
    expect(app).toMatch(/setSelection\(\{ \.\.\.EMPTY_EDITOR_SELECTION \}\)/);
    // N-UX-04 untouched
    expect(app).not.toMatch(/N-UX-04.*X-UX-08|X-UX-08.*N-UX-04/);
  });
});
