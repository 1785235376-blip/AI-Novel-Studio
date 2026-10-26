import {open, SHOTS} from './harness.mjs';
const {browser, page, backend, consoleLog} = await open();
await page.waitForTimeout(6000);
await page.screenshot({path: `${SHOTS}/00-probe-after-1366.png`});
console.log(backend.st.log.join('\n')); console.log('BLOCKED', backend.st.blocked); console.log(consoleLog.slice(0, 10).join('\n'));
console.log((await page.locator('body').innerText()).slice(0, 800));
await browser.close();
