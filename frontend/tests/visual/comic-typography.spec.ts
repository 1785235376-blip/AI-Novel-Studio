import { expect, test } from '@playwright/test';

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]) {
  test(`comic typography geometry and undo ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const generation: string[] = [];
    const preset = { width: 640, height: 640, safe_area: 24, segment_height: 640 };
    const document = { title: 'Synthetic typography', source_mode: 'INDEPENDENT', screenplay_id: null, expected_screenplay_version: null,
      preset: 'PAGE', font_family: 'NOTO_SANS_SC_OFL', ...preset,
      panels: [{ id: 'panel', shot_id: null, artwork_mode: 'BLANK', order: 1, x: 24, y: 24, width: 592, height: 592,
        character_ids: [], asset_id: null, expected_asset_version: null, fit: 'CONTAIN',
        bubbles: [{ id: 'bubble', kind: 'DIALOGUE', text: '天地\n日', character_id: null, font_size: 32, x: 40, y: 40, width: 300, height: 200 }] }] };
    await page.route('**/api/**', route => {
      const url = route.request().url(); if (/generate|execute/.test(url)) generation.push(url);
      return route.fulfill({ json: url.endsWith('/comic-layouts/catalog')
        ? { screenplays: [], characters: [], assets: [], presets: { PAGE: preset, WEBTOON: preset }, renderer: { available: true }, font: { available: true } }
        : { items: url.endsWith('/comic-layouts/records') ? [{ id: 'layout', version: 1, status: 'DRAFT', stale: false, document, history_versions: [] }] : [] } });
    });
    await page.goto('/ui-fixture?module=IMAGE');
    await expect(page.locator('.app-shell')).toBeVisible();
    await page.evaluate(async () => {
      const load = (url: string) => import(/* @vite-ignore */ url);
      const { default: React } = await load('/node_modules/.vite/deps/react.js');
      const { default: ReactDOM } = await load('/node_modules/.vite/deps/react-dom_client.js');
      const { ComicLayoutsPanel } = await load('/src/experimental/ComicLayoutsPanel.tsx');
      const { experimentalClient } = await load('/src/experimental/api.ts');
      await load('/src/experimental/experimental.css');
      const slot = window.document.createElement('div');
      window.document.querySelector('.main-workspace')!.replaceChildren(slot);
      ReactDOM.createRoot(slot).render(React.createElement(ComicLayoutsPanel, { client: experimentalClient('typography-fixture', { sessionToken: 'fixture' }) }));
    });
    await page.getByRole('button', { name: /打开布局/ }).click();
    const alignment = page.getByLabel('格框 1 气泡 1 文字对齐');
    const spacing = page.getByLabel('格框 1 气泡 1 行距 (%)');
    await expect(alignment).toHaveValue('LEFT'); await expect(spacing).toHaveValue('150');
    await alignment.selectOption('CENTER'); await spacing.fill('200');
    await page.getByRole('button', { name: '撤销本地排版', exact: true }).click(); await expect(spacing).toHaveValue('150');
    await page.getByRole('button', { name: '重做本地排版', exact: true }).click(); await expect(spacing).toHaveValue('200');
    await alignment.scrollIntoViewIfNeeded();
    await page.evaluate(() => document.fonts.ready);
    const geometry = await page.evaluate(() => {
      const height = (selector: string) => document.querySelector(selector)!.getBoundingClientRect().height;
      const main = document.querySelector('.main-workspace')!;
      return { header: height('.global-header'), context: height('.context-bar'), status: height('.status-bar'),
        overflow: document.documentElement.scrollWidth > innerWidth, mainOverflow: main.scrollWidth > main.clientWidth };
    });
    expect(geometry).toEqual({ header: 56, context: 44, status: 32, overflow: false, mainOverflow: false });
    expect(generation).toEqual([]);
    await page.screenshot({ path: info.outputPath(`comic-typography-${viewport.width}.png`) });
  });
}
