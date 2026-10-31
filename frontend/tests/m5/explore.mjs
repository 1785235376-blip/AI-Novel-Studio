import {open, SHOTS} from './harness.mjs';
const {browser, page, backend, consoleLog} = await open();
await page.getByTestId('u3-tasks').waitFor(); await page.waitForTimeout(1500);
console.log('TASKS:', (await page.getByTestId('u3-tasks').innerText()).slice(0, 600));
console.log('BTNS:', await page.locator('[data-testid=u3-tasks] button, [data-testid=u3-tasks] [role=button], [data-testid=u3-tasks] li').evaluateAll(a => a.map(e => e.tagName + ':' + (e.getAttribute('data-testid') || '') + ':' + e.textContent.slice(0, 40))));
console.log('CREATIVE:', await page.locator('[aria-label="图片无限画布"] button, [data-testid^=uw-creative] button').evaluateAll(a => a.map(e => (e.getAttribute('aria-label') || '') + '|' + e.textContent.slice(0, 20))));
await browser.close();
