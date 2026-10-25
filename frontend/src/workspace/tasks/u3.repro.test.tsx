// @vitest-environment jsdom
// [HERMIA-FE-20261025 U3-repro] Counterexample on the OLD preview TasksPanel (studioPreviewPanels.tsx:55), evidence type: mock (jsdom, stubbed fetch).
// Contract: without a real identity the panel must say "not connected" and must not read with an empty token / fabricated identity.
// Kept as it.fails so the defect stays recorded until the lead applies patches/u3-tasks-wiring.patch; the same contract passes on TasksPanelLive (u3.tasks.test.tsx).
import {cleanup, render} from '@testing-library/react';
import {afterEach, expect, it, vi} from 'vitest';
import {TasksPanel} from '../panels/studioPreviewPanels';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it.fails('old TasksPanel: no real identity ⇒ shows not-connected and performs no read', async () => {
  const fetchSpy = vi.fn(async () => new Response('{}', {status: 401}));
  vi.stubGlobal('fetch', fetchSpy);
  const {container} = render(<TasksPanel novelId="n1" active />);
  await new Promise(r => setTimeout(r, 50));
  expect(fetchSpy).not.toHaveBeenCalled();
  expect(container.querySelector('[data-state="not-connected"]')).not.toBeNull();
});
