// Discovery only: Vitest never imports suites; Playwright never starts browsers,
// services or test hooks. The two listed configs have no config-load fixtures.
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {readFileSync, readdirSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const manifest = JSON.parse(readFileSync(path.join(frontend, 'test-runner-manifest.json'), 'utf8'));
const relative = file => path.relative(frontend, file).split(path.sep).join('/');
const inDirectory = (file, directory) => file.startsWith(`${directory}/`);
const sorted = values => [...values].sort();
const testName = /\.(?:test|spec)\.[cm]?[jt]sx?$/;

function testFiles(directory = frontend) {
  return readdirSync(directory, {withFileTypes: true}).flatMap(entry => {
    if (entry.name.startsWith('.') || ['node_modules', 'dist'].includes(entry.name)
      || entry.name.startsWith('test-results')) return [];
    const file = path.join(directory, entry.name);
    return entry.isDirectory() ? testFiles(file) : testName.test(entry.name) ? [relative(file)] : [];
  });
}

// Use an independent source inventory, not the config's include/exclude globs.
// A new unit file silently excluded by Vitest or a misplaced Playwright spec fails.
const allFiles = sorted(testFiles());
const browserFiles = allFiles.filter(file => manifest.vitest.browserDirectories.some(dir => inDirectory(file, dir)));
const unitFiles = allFiles.filter(file => !browserFiles.includes(file));
for (const file of allFiles) {
  const source = ts.createSourceFile(file, readFileSync(path.join(frontend, file), 'utf8'), ts.ScriptTarget.Latest, true);
  const imports = source.statements.filter(ts.isImportDeclaration)
    .filter(statement => !statement.importClause?.isTypeOnly)
    .map(statement => statement.moduleSpecifier.text);
  const browser = browserFiles.includes(file);
  assert(imports.includes(browser ? '@playwright/test' : 'vitest'), `Missing expected runner import: ${file}`);
  assert(!imports.includes(browser ? 'vitest' : '@playwright/test'), `Mixed/wrong runner syntax: ${file}`);
}

function runJson(binary, args) {
  const env = {...process.env};
  // Keep --reporter=json on stdout even when a caller normally writes receipts.
  for (const key of ['PLAYWRIGHT_JSON_OUTPUT_FILE', 'PLAYWRIGHT_JSON_OUTPUT_DIR', 'PLAYWRIGHT_JSON_OUTPUT_NAME']) delete env[key];
  const output = execFileSync(process.execPath, [binary, ...args], {
    cwd: frontend, env, encoding: 'utf8', maxBuffer: 8 * 1024 * 1024,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  return JSON.parse(output);
}

const listedUnits = sorted(runJson('node_modules/vitest/vitest.mjs',
  ['list', '--config', manifest.vitest.config, '--filesOnly', '--json'])
  .map(entry => relative(entry.file)));
assert.deepEqual(listedUnits, unitFiles,
  'Vitest must list every unit/component file exactly once and no Playwright specs');

const affectedBrowserFiles = browserFiles.filter(file => inDirectory(file, 'e2e'));
const declaredBrowserFiles = manifest.playwright.flatMap(owner => Object.keys(owner.suites));
assert.deepEqual(sorted(declaredBrowserFiles), affectedBrowserFiles,
  'Every frontend/e2e spec must have exactly one explicit existing Playwright owner');

const playwright = [];
for (const owner of manifest.playwright) {
  const report = runJson('node_modules/@playwright/test/cli.js',
    ['test', '--config', owner.config, '--list', '--reporter=json']);
  assert.deepEqual(report.errors, [], `Playwright collection failed: ${owner.config}`);
  assert.equal(report.config.projects.length, owner.projects, `Project coverage changed: ${owner.config}`);
  const projectNames = report.config.projects.map(project => project.name);
  if (owner.projectNames) {
    assert.deepEqual(sorted(projectNames), sorted(owner.projectNames), `Named project coverage changed: ${owner.config}`);
  }
  const counts = new Map();
  const cases = [];
  function visit(suite) {
    for (const spec of suite.specs ?? []) {
      const file = `${owner.directory}/${spec.file.replaceAll('\\', '/')}`;
      for (const test of spec.tests) {
        assert.equal(test.expectedStatus, 'passed', `Disabled/expected-failure test: ${file}: ${spec.title}`);
        assert.deepEqual(test.results, [], `A test executed during discovery: ${file}`);
        const key = `${file}::${test.projectName}`;
        counts.set(key, (counts.get(key) ?? 0) + 1);
        cases.push({file, project: test.projectName, title: spec.title});
      }
    }
    for (const child of suite.suites ?? []) visit(child);
  }
  for (const suite of report.suites) visit(suite);
  const expected = new Map();
  for (const [file, count] of Object.entries(owner.suites)) {
    for (const projectName of owner.projectNames ?? projectNames) expected.set(`${file}::${projectName}`, count);
  }
  assert.deepEqual(sorted(counts), sorted(expected), `Playwright case/project coverage changed: ${owner.config}`);
  playwright.push({config: owner.config, files: sorted(Object.keys(owner.suites)), listedCases: cases.length, cases});
}

console.log(JSON.stringify({
  status: 'PASS_DISCOVERY_ONLY',
  vitest: {count: listedUnits.length, files: listedUnits},
  playwright,
  unchangedLegacyBrowserFiles: browserFiles.filter(file => !inDirectory(file, 'e2e')),
  note: 'No browser acceptance was executed. Legacy tests/e2e and tests/visual ownership is unchanged; their Playwright configs were not loaded.',
}, null, 2));
