// @vitest-environment jsdom
// [HERMIA-FE-20261031 VERA-P3] Vera 62f7684f 复审 P3-2：引导关闭焦点兜底跳过不可见元素
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {translateZh} from '../i18n';
import {OnboardingTour, useOnboarding} from './onboarding/OnboardingTour';
import {__resetOnboarding} from './onboarding/onboarding';

(globalThis as {IS_REACT_ACT_ENVIRONMENT?: boolean}).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { vi.useRealTimers(); document.body.innerHTML = ''; });

describe('onboarding close focus skips invisible targets (P3-2)', () => {
  for (const mode of ['display', 'ancestor', 'hidden-attr'] as const) {
    it(`switcher present but invisible (${mode}) -> focus goes to main, not BODY`, () => {
      vi.useFakeTimers(); localStorage.clear(); __resetOnboarding();
      const wrap = document.createElement('nav');
      const tab = document.createElement('button'); tab.setAttribute('data-module-tab', 'NOVEL'); tab.setAttribute('aria-selected', 'true');
      wrap.append(tab); document.body.append(wrap);
      if (mode === 'display') tab.style.display = 'none'; else if (mode === 'ancestor') wrap.style.display = 'none'; else wrap.hidden = true;
      const main = document.createElement('main'); main.textContent = 'work'; document.body.append(main);
      const host = document.createElement('div'); document.body.append(host);
      const root: Root = createRoot(host);
      function H() { const c = useOnboarding({shellMode: 'basic', auto: true}); return <OnboardingTour c={c} />; }
      act(() => root.render(<H />)); act(() => { vi.advanceTimersByTime(500); });
      act(() => (document.querySelector('[data-onboarding-skip]') as HTMLButtonElement).click());
      act(() => { vi.advanceTimersByTime(10); });
      expect(document.activeElement).toBe(main);
      act(() => root.unmount());
    });
  }
});
