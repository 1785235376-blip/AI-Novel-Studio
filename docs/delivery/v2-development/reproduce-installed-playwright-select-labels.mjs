// Run from frontend with: node --input-type=module < ../docs/delivery/v2-development/reproduce-installed-playwright-select-labels.mjs
// Executes only helpers from the installed, locked Playwright package over jsdom.
// This is a selector-mechanism reproduction, not a browser acceptance test.
import fs from 'node:fs';
import { JSDOM } from 'jsdom';
const bundle = fs.readFileSync('node_modules/.pnpm/playwright-core@1.62.1/node_modules/playwright-core/lib/coreBundle.js', 'utf8');
const literal = bundle.match(/source4 = ('(?:\\.|[^'\\])*');/s)?.[1];
if (!literal) throw new Error('Installed injected selector source is unavailable');
const injected = Function(`return ${literal}`)();
const names = ['getElementLabels', 'getAriaLabelledByElements', 'elementText', 'shouldSkipForTextMatching', 'normalizeWhiteSpace'];
const pieces = names.map(name => {
  const start = injected.indexOf(`function ${name}(`);
  if (start < 0) throw new Error(`Missing ${name}`);
  return injected.slice(start, injected.indexOf('\n}\n', start) + 3);
});
const dom = new JSDOM('<label>关联目标<select><option>请选择（可跳过）</option><option>relationship-target.png · v2</option></select></label><label>已保存创作图<select><option>未选择已保存图</option><option>可独立保存的图 · v1</option></select></label>');
const readLabels = Function('HTMLInputElement', 'Node', `let normalizedWhitespaceCache; ${pieces.join('\n')} return getElementLabels;`)(dom.window.HTMLInputElement, dom.window.Node);
for (const [index, name] of ['关联目标', '已保存创作图'].entries()) {
  const select = dom.window.document.querySelectorAll('select')[index];
  const before = readLabels(new Map(), select).map(value => value.normalized);
  select.setAttribute('aria-label', name);
  const after = readLabels(new Map(), select).map(value => value.normalized);
  if (before.includes(name) || !after.includes(name)) throw new Error('Expected selector mismatch/fix was not reproduced');
  console.log(JSON.stringify({name, installedPlaywright:'1.62.1', before, exactBefore:before.includes(name), after, exactAfter:after.includes(name), browserLaunched:false}));
}
