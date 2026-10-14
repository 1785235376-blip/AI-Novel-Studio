/**
 * AI-Novel-Studio V2 — Phase8 real-browser acceptance for the six Studio surfaces.
 *
 * Each case drives the REAL running app in a REAL browser and asserts the
 * surface's own accessible landmark is visible. Nothing here mocks an API
 * response, stubs a component, or asserts against a jsdom render.
 *
 * Landmarks are the shipped ones (verified in source, not invented):
 *   START        section[aria-label="项目入口"]        + h2 "进入创作工作区"
 *   TASKS        section[aria-label="统一任务中心"]
 *   ASSETS       Panel title "独立素材工作区"           (h2, no aria-label)
 *   PRODUCTION   section[aria-label="Studio 生产工作流看板"]
 *   MODEL CENTER section[aria-label="模型中心与存储"]   (opened from PRODUCTION)
 *   DELIVERY     section[aria-label="统一导出与工程交接"] (opened from PRODUCTION)
 * A <section> carrying an aria-label is exposed with the `region` role, so the
 * cases query it by role+name rather than by CSS.
 *
 * PREREQUISITE: the app must already be running, with the
 * `narrative_production_v2` surface flag enabled and a usable storage backend.
 * See ./README.md. An operator-provided browser is required; this suite never
 * downloads one.
 *
 * EACH CASE CREATES ONE REAL `NEUTRAL_STUDIO` PROJECT on the server it is
 * pointed at, through the app's own blank-project entry. Point the suite at a
 * disposable or local instance. The runtime directory is deliberately NOT
 * cleaned up here: deleting server-owned projects is a destructive act that
 * belongs to the operator, not to an acceptance spec (the repository's existing
 * live specs track ownership explicitly for exactly this reason).
 */
import {expect, test, type Locator, type Page} from '@playwright/test';

/** The Studio view switcher — always present once the workspace overview loads. */
const switcher = (page: Page) => page.locator('[aria-label="独立工作区内容"]');

/** Advance keyboard focus with real Tab presses (never `.focus()`), so the
 *  engine applies `:focus-visible` exactly as a keyboard user would see it. */
async function tabUntilFocused(page: Page, target: Locator, limit = 80): Promise<number> {
  for (let step = 1; step <= limit; step += 1) {
    await page.keyboard.press('Tab');
    if (await target.evaluate(node => node === document.activeElement).catch(() => false)) return step;
  }
  return 0;
}

/**
 * Enter the independent Studio the way an author does, and be idempotent about
 * it.
 *
 * The entry is NOT always the blank-project form: once any project exists, the
 * app re-opens the most recent one on the next load, so the studio may already
 * be mounted when this runs. Creating a project unconditionally would then wait
 * forever on a field that is not on screen — and would also pile up a fresh
 * project per case. So this waits for whichever entry actually appears, and
 * only creates a project when the studio is genuinely absent.
 */
async function enterStudio(page: Page): Promise<void> {
  await page.goto('/');
  const ready = switcher(page);
  const blankName = page.getByLabel('空白项目名称', {exact: true});
  // Whichever of the two entry states this load lands on.
  await expect(ready.or(blankName).first()).toBeVisible({timeout: 30_000});
  if (await ready.isVisible().catch(() => false)) return; // studio already open
  await blankName.fill('Studio 发布验收');
  await page.getByRole('button', {name: '创建空白项目', exact: true}).click();
  await expect(ready).toBeVisible();
}

/** Switch to one of the four Studio views the switcher owns. */
async function openView(page: Page, name: '创作开始' | '任务中心' | '素材工作区' | '制作操作'): Promise<void> {
  const button = switcher(page).getByRole('button', {name, exact: true});
  await expect(button).toBeVisible();
  await button.click();
  await expect(button).toHaveAttribute('aria-pressed', 'true');
}

test.describe('Studio release acceptance — six surfaces in a real browser', () => {
  test('START: the creative start entry renders its own landmark', async ({page}) => {
    await enterStudio(page);
    await openView(page, '创作开始');
    await expect(page.getByRole('region', {name: '项目入口', exact: true})).toBeVisible();
    await expect(page.getByRole('heading', {name: '进入创作工作区', exact: true})).toBeVisible();
  });

  test('TASKS: the unified task centre renders its own landmark', async ({page}) => {
    await enterStudio(page);
    await openView(page, '任务中心');
    await expect(page.getByRole('region', {name: '统一任务中心', exact: true})).toBeVisible();
  });

  test('ASSETS: the independent asset workspace renders its own heading', async ({page}) => {
    await enterStudio(page);
    await openView(page, '素材工作区');
    await expect(page.getByRole('heading', {name: '独立素材工作区', exact: true})).toBeVisible();
  });

  test('PRODUCTION: the production workflow dashboard renders its own landmark', async ({page}) => {
    await enterStudio(page);
    await openView(page, '制作操作');
    await expect(page.getByRole('region', {name: 'Studio 生产工作流看板', exact: true})).toBeVisible();
  });

  test('MODEL CENTER: opened on demand from production, renders its own landmark', async ({page}) => {
    await enterStudio(page);
    await openView(page, '制作操作');
    await page.getByRole('button', {name: '按需打开模型中心', exact: true}).click();
    await expect(page.getByRole('region', {name: '模型中心与存储', exact: true})).toBeVisible();
    await expect(page.getByRole('heading', {name: '模型中心与存储', exact: true})).toBeVisible();
  });

  test('DELIVERY: opened on demand from production, renders its own landmark', async ({page}) => {
    await enterStudio(page);
    await openView(page, '制作操作');
    await page.getByRole('button', {name: '按需打开统一导出与工程交接', exact: true}).click();
    await expect(page.getByRole('region', {name: '统一导出与工程交接', exact: true})).toBeVisible();
  });

  test('SMOKE (zh-CN): the studio shell really renders authored Chinese copy', async ({page}) => {
    await enterStudio(page);
    // The sidebar heading is authored Chinese, not a placeholder or a raw key.
    await expect(page.getByRole('heading', {name: '独立创作', exact: true})).toBeVisible();
    const body = await page.locator('body').innerText();
    expect(body, 'The Studio shell must render Chinese text, not untranslated keys.').toMatch(/[\u4e00-\u9fff]/);
    // A surface with Chinese copy must also carry the Chinese switcher labels.
    await expect(switcher(page).getByRole('button', {name: '素材工作区', exact: true})).toBeVisible();
  });

  test('KEYBOARD: a switcher control is reachable by Tab and shows a visible focus indicator', async ({page}) => {
    await enterStudio(page);
    const target = switcher(page).getByRole('button', {name: '任务中心', exact: true});
    const steps = await tabUntilFocused(page, target);
    expect(steps, 'Tab must reach the 任务中心 control within a sane number of stops.').toBeGreaterThan(0);
    await expect(target).toBeFocused();

    // The focused control must actually show a focus indicator, not just hold
    // focus: either an outline or a ring shadow, with a non-zero width.
    const indicator = await target.evaluate(node => {
      const style = getComputedStyle(node);
      return {outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth, boxShadow: style.boxShadow};
    });
    const outlineVisible = indicator.outlineStyle !== 'none' && parseFloat(indicator.outlineWidth) > 0;
    const shadowVisible = indicator.boxShadow !== 'none' && indicator.boxShadow.trim() !== '';
    expect(outlineVisible || shadowVisible, `Focused control shows no focus indicator: ${JSON.stringify(indicator)}`).toBe(true);

    // The same control must also be operable from the keyboard alone.
    await page.keyboard.press('Enter');
    await expect(target).toHaveAttribute('aria-pressed', 'true');
  });
});
