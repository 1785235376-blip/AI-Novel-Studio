import { expect, type Page } from '@playwright/test';

/** Real rendered prose must occupy the flexible second workspace row. DOM
 * presence, successful typing and frozen shell dimensions alone cannot prove it.
 */
export async function expectVisibleWorkspaceEditor(page: Page, resumeEnabled: boolean) {
  const prose = page.getByRole('textbox', { name: '章节正文', exact: true });
  await expect(prose).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  const metrics = await prose.evaluate((element, enabled) => {
    const workspace = element.closest('.novel-writing-workspace')!;
    const chrome = workspace.querySelector(':scope > .novel-workspace-chrome')!;
    const bar = chrome.querySelector('.editorbar')!;
    const editor = element.closest('.editor')!;
    const main = workspace.closest('.main-workspace')!;
    const rect = (node: Element) => { const r = node.getBoundingClientRect(); return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, width: r.width, height: r.height }; };
    const frame = rect(main), editing = rect(editor), controls = rect(chrome), saveBar = rect(bar);
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    let text: Node | null;
    do { text = walker.nextNode(); } while (text && !text.textContent?.trim());
    if (!text) throw new Error('Geometry assertion requires actual nonempty manuscript text');
    const range = document.createRange(); range.setStart(text, 0); range.setEnd(text, Math.min(4, text.textContent!.length));
    const firstText = range.getBoundingClientRect();
    let visibleTop = Math.max(0, firstText.top), visibleBottom = Math.min(innerHeight, firstText.bottom);
    let visibleLeft = Math.max(0, firstText.left), visibleRight = Math.min(innerWidth, firstText.right);
    for (let node: Element | null = element; node; node = node.parentElement) {
      const css = getComputedStyle(node), box = node.getBoundingClientRect();
      if (/(auto|scroll|hidden|clip)/.test(css.overflowY)) { visibleTop = Math.max(visibleTop, box.top); visibleBottom = Math.min(visibleBottom, box.bottom); }
      if (/(auto|scroll|hidden|clip)/.test(css.overflowX)) { visibleLeft = Math.max(visibleLeft, box.left); visibleRight = Math.min(visibleRight, box.right); }
    }
    const x = (visibleLeft + visibleRight) / 2, y = (visibleTop + visibleBottom) / 2;
    const hit = document.elementFromPoint(x, y);
    const summary = chrome.querySelector('.workspace-resume-summary');
    const note = summary?.querySelector('.workspace-resume-summary__note');
    return {
      rowCount: getComputedStyle(workspace).gridTemplateRows.trim().split(/\s+/).length,
      directChildren: workspace.children.length, firstChrome: workspace.firstElementChild === chrome,
      editorSecond: workspace.children[1]?.classList.contains('writing-editor-row'),
      editorTop: editing.top, chromeBottom: controls.bottom,
      visibleEditor: Math.min(editing.bottom, frame.bottom, innerHeight) - Math.max(editing.top, frame.top, 0),
      visibleTextHeight: visibleBottom - visibleTop, visibleTextWidth: visibleRight - visibleLeft,
      textHit: !!hit && element.contains(hit), textOffset: firstText.top - controls.bottom,
      summaryPresent: !!summary, chromeHeight: controls.height, barHeight: saveBar.height,
      noteHeight: note?.getBoundingClientRect().height ?? 0,
      noteLineHeight: note ? parseFloat(getComputedStyle(note).lineHeight) : 0,
      noteClipped: note ? note.scrollWidth > note.clientWidth : false,
      header: rect(document.querySelector('.global-header')!).height,
      context: rect(document.querySelector('.context-bar')!).height,
      status: rect(document.querySelector('.status-bar')!).height,
      overflow: document.documentElement.scrollWidth - innerWidth,
      expectedResume: enabled,
    };
  }, resumeEnabled);
  expect(metrics.directChildren).toBe(3); expect(metrics.rowCount).toBe(3);
  expect(metrics.firstChrome).toBe(true); expect(metrics.editorSecond).toBe(true);
  expect(Math.abs(metrics.editorTop - metrics.chromeBottom)).toBeLessThanOrEqual(1);
  expect(metrics.visibleEditor).toBeGreaterThanOrEqual(200);
  expect(metrics.visibleTextHeight).toBeGreaterThan(8); expect(metrics.visibleTextWidth).toBeGreaterThan(8);
  expect(metrics.textHit).toBe(true); expect(metrics.textOffset).toBeLessThan(160);
  expect(metrics.summaryPresent).toBe(resumeEnabled);
  if (!resumeEnabled) expect(metrics.chromeHeight).toBe(metrics.barHeight);
  expect(metrics.header).toBe(56); expect(metrics.context).toBe(44); expect(metrics.status).toBe(32); expect(metrics.overflow).toBeLessThanOrEqual(1);
  await expectEditorbarControlsActionable(page, ['保存']);
  return metrics;
}

/** Guard the real click centers and full target rectangles without force-clicks,
 * dismissing the inspector, or moving its original shell control. */
export async function expectEditorbarControlsActionable(page: Page, expectedLabels: string[]) {
  const toolbar = page.locator('.novel-workspace-chrome > .editorbar');
  await expect(toolbar).toBeVisible();
  for (const label of expectedLabels) await expect(toolbar.getByRole('button', { name: label, exact: true })).toBeVisible();
  await toolbar.hover();
  const metrics = await toolbar.evaluate(element => {
    const box = element.getBoundingClientRect();
    const toggle = document.querySelector('.inspector-edge-toggle')!;
    const edge = toggle.getBoundingClientRect();
    const workspace = element.closest('.novel-writing-workspace')!;
    const main = workspace.closest('.main-workspace')!;
    const controls = Array.from(element.querySelectorAll<HTMLButtonElement>('.save-controls button')).map(button => {
      const rect = button.getBoundingClientRect();
      const center = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
      return { label: button.textContent?.trim(), width: rect.width, height: rect.height,
        ownsCenter: center === button || !!center && button.contains(center),
        inToolbar: rect.left >= box.left && rect.right <= box.right && rect.top >= box.top && rect.bottom <= box.bottom,
        overlapsToggle: Math.min(rect.right, edge.right) > Math.max(rect.left, edge.left)
          && Math.min(rect.bottom, edge.bottom) > Math.max(rect.top, edge.top),
        whiteSpace: getComputedStyle(button).whiteSpace,
      };
    });
    return { controls, toolbarOverflow: element.scrollWidth - element.clientWidth,
      workspaceOverflow: workspace.scrollWidth - workspace.clientWidth, workspaceScroll: workspace.scrollLeft,
      mainOverflow: main.scrollWidth - main.clientWidth, mainScroll: main.scrollLeft,
      toggleWidth: edge.width, toggleHeight: edge.height,
      reserve: parseFloat(getComputedStyle(element).paddingRight) };
  });
  expect(metrics.controls.length).toBeGreaterThan(0);
  for (const control of metrics.controls) {
    expect(control.ownsCenter, `${control.label} click center is covered`).toBe(true);
    expect(control.inToolbar, `${control.label} is outside editor chrome`).toBe(true);
    expect(control.overlapsToggle, `${control.label} overlaps the inspector toggle`).toBe(false);
    expect(control.whiteSpace).toBe('nowrap');
    expect(control.width).toBeGreaterThan(32); expect(control.height).toBeGreaterThanOrEqual(28);
  }
  expect(metrics.reserve).toBeGreaterThan(metrics.toggleWidth);
  expect(metrics.toggleWidth).toBeGreaterThanOrEqual(32); expect(metrics.toggleHeight).toBeGreaterThanOrEqual(32);
  expect(metrics.toolbarOverflow).toBeLessThanOrEqual(1); expect(metrics.workspaceOverflow).toBeLessThanOrEqual(1);
  expect(metrics.mainOverflow).toBeLessThanOrEqual(1); expect(metrics.workspaceScroll).toBe(0); expect(metrics.mainScroll).toBe(0);
}
