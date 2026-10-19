// Compare exact baseline/current sources without renaming application files or relaxing TS options.
const fs = require('node:fs'), path = require('node:path'), cp = require('node:child_process');
const root = path.resolve(__dirname, '../studio-v2-selected-video-binding');
const frontend = path.join(root, 'frontend');
const ts = require(path.join(frontend, 'node_modules/typescript'));
const baseline = 'c1638908168cfdcea0b63cef9388b88cf66a91f3';
const git = (...args) => cp.execFileSync('git', ['-c', 'core.longpaths=true', '-C', root, ...args], { encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 });
const baselinePaths = git('ls-tree', '-r', '--name-only', baseline, '--', 'frontend/src').trim().split('\n');
const baselineSet = new Set(baselinePaths), overlays = new Map();
for (const file of git('diff', baseline, '--name-only', '--', 'frontend/src').trim().split('\n'))
  if (baselineSet.has(file)) overlays.set(path.resolve(root, file).toLowerCase(), git('show', `${baseline}:${file}`));
const config = ts.readConfigFile(path.join(frontend, 'tsconfig.json'), ts.sys.readFile);
if (config.error) throw new Error(ts.flattenDiagnosticMessageText(config.error.messageText, '\n'));
const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, frontend);
const directoryCache = new Map();
function exactFile(file) {
  try {
    const dir = path.dirname(file);
    if (!directoryCache.has(dir)) directoryCache.set(dir, new Set(fs.readdirSync(dir)));
    return directoryCache.get(dir).has(path.basename(file)) && fs.statSync(file).isFile();
  } catch { return false; }
}
function check(label, old, exact) {
  const originalCase = ts.sys.useCaseSensitiveFileNames;
  ts.sys.useCaseSensitiveFileNames = exact;
  try {
    const host = ts.createCompilerHost(parsed.options);
    if (exact) {
      host.useCaseSensitiveFileNames = () => true;
      host.getCanonicalFileName = file => file;
      host.fileExists = exactFile;
    }
    const read = host.readFile;
    host.readFile = file => old && overlays.has(path.resolve(file).toLowerCase()) ? overlays.get(path.resolve(file).toLowerCase()) : read(file);
    host.getSourceFile = (file, languageVersion) => {
      const text = host.readFile(file);
      return text === undefined ? undefined : ts.createSourceFile(file, text, languageVersion, true);
    };
    const currentParsed = ts.parseJsonConfigFileContent(config.config, ts.sys, frontend);
    const rootNames = old ? baselinePaths.filter(file => /\.tsx?$/.test(file)).map(file => path.resolve(root, file)) : currentParsed.fileNames;
    const program = ts.createProgram(rootNames, parsed.options, host);
    const diagnostics = ts.getPreEmitDiagnostics(program).map(d => ({ code: d.code,
      file: d.file ? path.relative(root, d.file.fileName).replaceAll('\\', '/') : null,
      line: d.file && d.start !== undefined ? d.file.getLineAndCharacterOfPosition(d.start).line + 1 : null,
      message: ts.flattenDiagnosticMessageText(d.messageText, '\n') }));
    const result = { label, baseline: old, exact_case_host: exact, root_files: rootNames.length, errors: diagnostics.length, diagnostics };
    fs.writeFileSync(path.join(__dirname, `${label}.json`), JSON.stringify(result, null, 2));
    console.log(JSON.stringify({ label, root_files: rootNames.length, errors: diagnostics.length, first: diagnostics.slice(0, 2) }));
    return result;
  } finally { ts.sys.useCaseSensitiveFileNames = originalCase; }
}
const results = [];
const currentOnly = process.argv.includes('--current-only');
for (const [label, old, exact] of (currentOnly ? [['current-exact-case-host-final', false, true]] : [['baseline-native-host', true, false], ['current-native-host', false, false], ['baseline-exact-case-host', true, true], ['current-exact-case-host', false, true]])) {
  results.push(check(label, old, exact)); if (global.gc) global.gc();
}
const summary = results.map(({ label, root_files, errors }) => ({ label, root_files, errors }));
fs.writeFileSync(path.join(__dirname, currentOnly ? 'typecheck-final.json' : 'typecheck-comparison.json'), JSON.stringify({ baseline, native_host_still_blocked: currentOnly ? true : results[1].errors > 0,
  same_strict_compiler_options: true, default_production_config_unchanged: true, results: summary }, null, 2));
process.exitCode = results.at(-1).errors ? 1 : 0;
