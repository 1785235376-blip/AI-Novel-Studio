// @vitest-environment jsdom
/** [HERMIA-FE-20261031 VERA-P3 r3] en: AssetInspector 的 aria-label 与 PreferencesForm 禁用按钮的 title 不含汉字；zh 不变。 */
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { setLocale } from '../i18n';
import { AssetInspector } from './AssetInspector';
import { StudioWorkspacePreferencesForm } from '../creative/StudioWorkspacePreferencesForm';
import type { StudioWorkspacePreferencesController } from '../creative/useStudioWorkspacePreferences';
afterEach(() => { act(() => setLocale('zh-CN')); cleanup(); });
const controller = { draft: { intents: [], preset: 'BLANK', custom_intent: '' }, base: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' },
  editable: true, dirty: false, save: () => {}, change: () => {}, canCheck: false } as unknown as StudioWorkspacePreferencesController;
const read = () => {
  const a = render(<AssetInspector novelId="n1" />); const label = a.container.querySelector('.asset-inspector')!.getAttribute('aria-label'); a.unmount();
  const b = render(<StudioWorkspacePreferencesForm controller={controller} />); const title = b.container.querySelector('button[disabled][title]')!.getAttribute('title'); b.unmount();
  return [label, title];
};
it('en labels are English', () => { act(() => setLocale('en')); expect(read()).toEqual(['Asset inspector', 'Not available in the public edition']); });
it('zh labels unchanged', () => { expect(read()).toEqual(['资产检查面板', '公开版本不提供此功能']); });
