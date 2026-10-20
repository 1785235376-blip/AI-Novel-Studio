#!/usr/bin/env node
// Test-only pinned target acceptance verifier; never shipped or executed by the product.
//
// Compiles the CURRENT exported Ink artifact (ink/story.ink) with the pinned
// inkjs 2.3.2 compiler, consumes the compiled artifact with the pinned runtime,
// asserts every acceptance-witness state (text, enabled choice list, variables,
// ink state and ending/step-cap status) and verifies state save/restore across a
// real process boundary. It never bundles or installs runtime code and denies
// Ink file access so INCLUDE/external files cannot load.
//
// Usage:
//   node scripts/verify_ink_current_artifact.mjs --bundle <dir> --vendor <inkjs-package-root> --report <file>
//   (internal) --resume-request <file> --resume-report <file>
//
// Exit codes: 0 PASS, 2 compile failure, 3 assertion/pin failure, 4 verifier error.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const MODULE_FILE = fileURLToPath(import.meta.url);

const SCHEMA = 'poemseed-ink-current-artifact-verification/1';
const CONTINUE_CAP = 1000;

function fail(message, code) {
  process.stderr.write('VERIFIER_ERROR ' + message + '\n');
  process.exit(code || 4);
}

function sha256(buffer) {
  return crypto.createHash('sha256').update(buffer).digest('hex');
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (!item.startsWith('--')) fail('unexpected argument ' + item);
    const name = item.slice(2);
    const value = argv[index + 1];
    if (value === undefined || value.startsWith('--')) fail('missing value for ' + item);
    args[name] = value;
    index += 1;
  }
  return args;
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function loadPinnedRuntime(vendorRoot) {
  const packageFile = path.join(vendorRoot, 'package.json');
  const entryFile = path.join(vendorRoot, 'dist', 'ink-full.js');
  if (!fs.existsSync(packageFile) || !fs.existsSync(entryFile)) fail('PINNED_RUNTIME_FILES_MISSING: ' + vendorRoot);
  const pkg = readJson(packageFile);
  const entryBytes = fs.readFileSync(entryFile);
  const requireFromVendor = createRequire(path.join(vendorRoot, 'package.json'));
  let loaded;
  try {
    loaded = requireFromVendor(entryFile);
  } catch (error) {
    fail('PINNED_RUNTIME_LOAD_FAILED: ' + String(error && error.message ? error.message : error));
  }
  if (!loaded || typeof loaded.Compiler !== 'function' || typeof loaded.Story !== 'function') {
    fail('PINNED_RUNTIME_SURFACE_INVALID: expected {Compiler, Story}');
  }
  return {
    packageName: pkg.name,
    version: pkg.version,
    packageJsonSha256: sha256(fs.readFileSync(packageFile)),
    runtimeEntry: entryFile,
    runtimeEntrySha256: sha256(entryBytes),
    runtimeEntryBytes: entryBytes.length,
    Compiler: loaded.Compiler,
    Story: loaded.Story,
  };
}

function advance(story) {
  let output = '';
  const errors = [];
  let ticks = 0;
  while (story.canContinue) {
    ticks += 1;
    if (ticks > CONTINUE_CAP) throw new Error('CONTINUE_CAP_EXCEEDED');
    output += story.Continue();
  }
  if (story.hasError) errors.push(String(story.currentErrors));
  return { output: output, errors: errors };
}

function variableValues(story, names) {
  const values = {};
  for (const name of names) values[name] = story.variablesState.$(name);
  return values;
}

function inkState(story) {
  return {
    ans_node: story.variablesState.$('ans_node'),
    ans_steps: story.variablesState.$('ans_steps'),
    ans_status: story.variablesState.$('ans_status'),
  };
}

function snapshot(story, variableNames) {
  return {
    output: advance(story).output,
    choices: story.currentChoices.map(function (choice) { return { text: choice.text, index: choice.index }; }),
    variables: variableValues(story, variableNames),
    ink_state: inkState(story),
  };
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') {
    const result = {};
    for (const key of Object.keys(value).sort()) result[key] = canonical(value[key]);
    return result;
  }
  return value;
}

function strictEqual(actual, expected) {
  // Type strict (true !== 1) and key-order independent.
  return typeof actual === typeof expected && JSON.stringify(canonical(actual)) === JSON.stringify(canonical(expected));
}

function compareState(actual, expected) {
  const failures = [];
  if (actual.output !== expected.output_text) {
    failures.push({ check: 'text', detail: 'runtime output differs', expected: expected.output_text, actual: actual.output });
  }
  const expectedLabels = (expected.choices || []).map(function (choice) { return choice.label; });
  const actualLabels = actual.choices.map(function (choice) { return choice.text; });
  if (JSON.stringify(actualLabels) !== JSON.stringify(expectedLabels)) {
    failures.push({ check: 'choices', detail: 'runtime choice labels differ', expected: expectedLabels, actual: actualLabels });
  }
  if (!strictEqual(actual.variables, expected.ink_variables)) {
    failures.push({ check: 'variables', detail: 'runtime variable values/types differ', expected: expected.ink_variables, actual: actual.variables });
  }
  if (!strictEqual(actual.ink_state, expected.ink_state)) {
    failures.push({ check: 'ink_state', detail: 'runtime ans_node/ans_steps/ans_status differ', expected: expected.ink_state, actual: actual.ink_state });
  }
  return failures;
}

function choiceIndexFor(expectedState, choiceId) {
  const choices = expectedState.choices || [];
  const entry = choices.find(function (choice) { return choice.id === choiceId; });
  if (!entry) return { index: -1, detail: 'witness choice id missing from expected enabled list: ' + choiceId };
  const position = choices.indexOf(entry);
  if (entry.index !== position) return { index: -1, detail: 'witness choice index mismatch for ' + choiceId };
  return { index: entry.index, detail: null };
}

function caseSteps(caseValue) {
  const steps = [];
  for (let position = 0; position < caseValue.choices.length; position += 1) {
    const mapped = choiceIndexFor(caseValue.states[position], caseValue.choices[position]);
    if (mapped.index < 0) throw new Error('WITNESS_INVALID: ' + mapped.detail);
    steps.push(mapped.index);
  }
  return steps;
}

// ---------------------------------------------------------------- resume mode
function resumeMode(args) {
  const request = readJson(args['resume-request']);
  const runtime = loadPinnedRuntime(request.vendor);
  const report = {
    schema: 'poemseed-ink-current-artifact-resume/1',
    pid: process.pid,
    node: process.version,
    vendor: { version: runtime.version, runtime_entry_sha256: runtime.runtimeEntrySha256 },
    snapshots: [],
    final: null,
    file_calls: 0,
    errors: [],
  };
  try {
    const artifact = JSON.parse(fs.readFileSync(request.artifact, 'utf8'));
    const state = fs.readFileSync(request.state, 'utf8');
    const story = new runtime.Story(artifact);
    story.state.LoadJson(state);
    report.snapshots.push(snapshot(story, request.variables));
    for (const index of request.remaining) {
      story.ChooseChoiceIndex(index);
      report.snapshots.push(snapshot(story, request.variables));
    }
    report.final = report.snapshots[report.snapshots.length - 1];
  } catch (error) {
    report.errors.push(String(error && error.stack ? error.stack : error));
  }
  fs.writeFileSync(args['resume-report'], JSON.stringify(report, null, 2));
  process.stdout.write('RESUME pid=' + report.pid + ' snapshots=' + report.snapshots.length + ' errors=' + report.errors.length + '\n');
  process.exit(report.errors.length === 0 ? 0 : 3);
}

// ---------------------------------------------------------------- main mode
function mainMode(args) {
  const started = Date.now();
  const report = {
    schema: SCHEMA,
    result: 'FAIL',
    node: process.version,
    platform: process.platform + ' ' + process.arch,
    verifier: 'scripts/verify_ink_current_artifact.mjs',
    bundle: path.resolve(args.bundle),
    vendor: null,
    source: null,
    witness: null,
    runtime_pin: null,
    bundle_files: [],
    runtime_code_bundled: null,
    compile: { attempted: false, success: false, errors: [], file_calls: 0, artifact_sha256: null, artifact_bytes: 0 },
    runtime: { artifact_consumed: false, artifact_sha256: null, cases: [], file_calls: 0,
      ending_reached: false, step_cap_enforced: false, in_memory_restore_checks: 0 },
    cross_process: { performed: false, fresh_process: false, passed: false, detail: 'not attempted' },
    assertions: { bundle_shape: 'FAIL', runtime_pin: 'FAIL', text: 'FAIL', choices: 'FAIL', variables: 'FAIL',
      ink_state: 'FAIL', endings: 'FAIL', step_cap: 'NOT_COVERED', file_access_denied: 'FAIL', save_restore: 'FAIL' },
    unicode_and_escape: 'NOT_COVERED',
    native_csharp_runtime: 'NOT_RUN',
    runtime_basis: 'COMMUNITY_JAVASCRIPT_PORT_INKJS_2_3_2',
    failures: [],
    elapsed_ms: 0,
  };

  function writeReport() {
    report.elapsed_ms = Date.now() - started;
    if (args.report) fs.writeFileSync(args.report, JSON.stringify(report, null, 2));
    process.stdout.write('RESULT ' + report.result + ' compile=' + report.compile.success +
      ' cases=' + report.runtime.cases.length + ' cross_process=' + report.cross_process.passed +
      ' failures=' + report.failures.length + '\n');
    if (report.failures.length) process.stdout.write('FAILURES ' + JSON.stringify(report.failures).slice(0, 2000) + '\n');
    process.exit(report.result === 'PASS' ? 0 : 3);
  }

  const bundle = path.resolve(args.bundle);
  const witnessFile = path.join(bundle, 'acceptance', 'witness.json');
  const sourceFile = path.join(bundle, 'ink', 'story.ink');
  const pinFile = path.join(bundle, 'ink', 'runtime-pin.json');
  const validationFile = path.join(bundle, 'ink', 'validation.json');
  for (const file of [witnessFile, sourceFile, pinFile]) {
    if (!fs.existsSync(file)) fail('BUNDLE_FILE_MISSING: ' + file);
  }
  const bundleFiles = [];
  (function walk(directory, prefix) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true }).sort(function (a, b) { return a.name < b.name ? -1 : 1; })) {
      const relative = prefix ? prefix + '/' + entry.name : entry.name;
      if (entry.isDirectory()) walk(path.join(directory, entry.name), relative);
      else bundleFiles.push(relative);
    }
  })(bundle, '');
  report.bundle_files = bundleFiles;
  const runtimeCode = bundleFiles.filter(function (name) {
    return /\.(cjs|mjs|js|node|wasm)$/i.test(name) || name.indexOf('node_modules/') === 0;
  });
  report.runtime_code_bundled = runtimeCode.length > 0;
  report.assertions.bundle_shape = runtimeCode.length === 0 ? 'PASS' : 'FAIL';
  if (runtimeCode.length) report.failures.push({ check: 'bundle_shape', detail: 'runtime code present in bundle', files: runtimeCode });

  const witnessBytes = fs.readFileSync(witnessFile);
  const witness = JSON.parse(witnessBytes.toString('utf8'));
  const sourceBytes = fs.readFileSync(sourceFile);
  const runtimePin = JSON.parse(fs.readFileSync(pinFile, 'utf8'));
  const validation = fs.existsSync(validationFile) ? readJson(validationFile) : null;
  report.source = { path: path.relative(bundle, sourceFile), sha256: sha256(sourceBytes), bytes: sourceBytes.length };
  report.witness = { path: path.relative(bundle, witnessFile), sha256: sha256(witnessBytes),
    endings: (witness.endings || []).length, step_cap_cases: (witness.step_cap_cases || []).length };
  report.runtime_pin = { sha256: sha256(fs.readFileSync(pinFile)), package: runtimePin.package,
    version: runtimePin.version, integrity: runtimePin.integrity, runtime_bundled: runtimePin.runtime_bundled };

  if (witness.script && witness.script.sha256 !== report.source.sha256) {
    report.failures.push({ check: 'witness', detail: 'witness script sha256 does not match ink/story.ink' });
  }
  if (!validation || validation.witness.sha256 !== report.witness.sha256) {
    report.failures.push({ check: 'witness', detail: 'validation.json witness sha256 mismatch' });
  }
  if (validation && validation.runtime_pin.sha256 !== report.runtime_pin.sha256) {
    report.failures.push({ check: 'runtime_pin', detail: 'validation.json runtime-pin sha256 mismatch' });
  }
  if (runtimePin.version !== witness.runtime.version || runtimePin.integrity !== witness.runtime.integrity) {
    report.failures.push({ check: 'runtime_pin', detail: 'runtime-pin.json and witness runtime disagree' });
  }
  if (runtimeCode.length === 0 && report.failures.length === 0) report.assertions.runtime_pin = 'PASS';

  if (!args.vendor) fail('vendor argument required');
  const runtime = loadPinnedRuntime(path.resolve(args.vendor));
  report.vendor = { package: runtime.packageName, version: runtime.version,
    package_json_sha256: runtime.packageJsonSha256, runtime_entry: runtime.runtimeEntry,
    runtime_entry_sha256: runtime.runtimeEntrySha256, runtime_entry_bytes: runtime.runtimeEntryBytes };
  const expectedPin = witness.runtime;
  if (runtime.version !== expectedPin.version) {
    report.failures.push({ check: 'runtime_pin', detail: 'installed inkjs version ' + runtime.version + ' != pinned ' + expectedPin.version });
  }
  if (runtime.runtimeEntrySha256 !== expectedPin.runtime_entry.sha256) {
    report.failures.push({ check: 'runtime_pin', detail: 'installed runtime entry hash != pinned runtime entry hash' });
  }

  // Compile phase: the pinned compiler parses the exported source; file access denied.
  const compileErrors = [];
  let compileFileCalls = 0;
  let compiledStory = null;
  let artifactJson = null;
  report.compile.attempted = true;
  try {
    const denyFile = function () { compileFileCalls += 1; throw new Error('FILE_ACCESS_DENIED'); };
    const compiler = new runtime.Compiler(sourceBytes.toString('utf8'), {
      errorHandler: function (message, type) { compileErrors.push({ message: String(message), type: String(type) }); },
      fileHandler: { ResolveInkFilename: denyFile, LoadInkFileContents: denyFile },
    });
    compiledStory = compiler.Compile();
    if (compileErrors.length) throw new Error('COMPILER_REPORTED_ERRORS');
    artifactJson = compiledStory.ToJson();
    report.compile.success = true;
    report.compile.artifact_sha256 = sha256(Buffer.from(artifactJson, 'utf8'));
    report.compile.artifact_bytes = Buffer.byteLength(artifactJson, 'utf8');
  } catch (error) {
    report.compile.errors = compileErrors.length ? compileErrors : [{ message: String(error) }];
  }
  report.compile.file_calls = compileFileCalls;
  report.assertions.file_access_denied = compileFileCalls === 0 ? 'PASS' : 'FAIL';
  if (!report.compile.success) {
    report.failures.push({ check: 'compile', detail: 'pinned compiler did not produce an artifact', errors: report.compile.errors.slice(0, 5) });
    writeReport();
  }

  // Runtime phase: consume the serialized artifact (compile != runtime).
  const variableNames = (witness.variables || []).map(function (variable) { return variable.ink; });
  const cases = (witness.endings || []).map(function (caseValue) { return { kind: 'ENDING', case: caseValue }; })
    .concat((witness.step_cap_cases || []).map(function (caseValue) { return { kind: 'STEP_CAP', case: caseValue }; }));
  const textChecks = [];
  for (const item of cases) {
    const caseValue = item.case;
    const record = { kind: item.kind, ending_node_id: caseValue.ending_node_id || null, choices: caseValue.choices.slice(),
      passed: false, final_status: null, failures: [], steps: 0 };
    try {
      const steps = caseSteps(caseValue);
      const story = new runtime.Story(artifactJson);
      let failures = [];
      let current = snapshot(story, variableNames);
      failures = failures.concat(compareState(current, caseValue.states[0]));
      for (let position = 0; position < steps.length; position += 1) {
        // Persist and reload the runtime state at every step of the accepted path.
        const before = inkState(story);
        const beforeVariables = variableValues(story, variableNames);
        const savedState = story.state.ToJson();
        const restored = new runtime.Story(artifactJson);
        restored.state.LoadJson(savedState);
        report.runtime.in_memory_restore_checks += 1;
        if (!strictEqual(inkState(restored), before) || !strictEqual(variableValues(restored, variableNames), beforeVariables)) {
          failures.push({ check: 'save_restore', detail: 'in-memory restored state disagrees before step ' + (position + 1) });
        }
        const restoredChoices = restored.currentChoices.map(function (choice) { return choice.text; });
        const beforeChoices = story.currentChoices.map(function (choice) { return choice.text; });
        if (JSON.stringify(restoredChoices) !== JSON.stringify(beforeChoices)) {
          failures.push({ check: 'save_restore', detail: 'in-memory restored choices disagree before step ' + (position + 1) });
        }
        story.ChooseChoiceIndex(steps[position]);
        current = snapshot(story, variableNames);
        failures = failures.concat(compareState(current, caseValue.states[position + 1]));
      }
      record.steps = current.ink_state.ans_steps;
      record.final_status = caseValue.states[caseValue.states.length - 1].status;
      if (current.ink_state.ans_status !== caseValue.states[caseValue.states.length - 1].ink_state.ans_status) {
        failures.push({ check: 'status', detail: 'final ans_status differs from witness' });
      }
      record.failures = failures;
      record.passed = failures.length === 0;
      if (item.kind === 'ENDING' && record.passed) report.runtime.ending_reached = true;
      if (item.kind === 'STEP_CAP' && record.passed) report.runtime.step_cap_enforced = true;
      if (failures.length) report.failures.push({ check: item.kind, case: caseValue.choices, failures: failures.slice(0, 6) });
      for (const stateValue of caseValue.states) {
        for (const line of (stateValue.output_lines || [])) textChecks.push({ line: line, unicode: /[^\x00-\x7F]/.test(line) || /["{}\[\]<>\\#]/.test(line) });
      }
    } catch (error) {
      record.failures.push({ check: 'runtime', detail: String(error && error.stack ? error.stack : error) });
      report.failures.push({ check: item.kind, detail: 'runtime replay failed: ' + String(error) });
    }
    report.runtime.cases.push(record);
  }
  report.runtime.artifact_consumed = report.compile.success && report.runtime.cases.length > 0;
  report.runtime.artifact_sha256 = report.compile.artifact_sha256;

  const allCasesPassed = report.runtime.cases.every(function (value) { return value.passed; });
  const endings = report.runtime.cases.filter(function (value) { return value.kind === 'ENDING'; });
  const stepCaps = report.runtime.cases.filter(function (value) { return value.kind === 'STEP_CAP'; });
  report.assertions.endings = endings.length > 0 && endings.every(function (value) { return value.passed; }) ? 'PASS' : 'FAIL';
  report.assertions.step_cap = stepCaps.length > 0 && stepCaps.every(function (value) { return value.passed; }) ? 'PASS' : 'NOT_COVERED';
  const checkNames = ['text', 'choices', 'variables', 'ink_state'];
  for (const name of checkNames) {
    const failed = report.runtime.cases.some(function (value) {
      return value.failures.some(function (failure) { return failure.check === name || failure.check === 'status'; });
    });
    report.assertions[name] = failed ? 'FAIL' : (report.runtime.cases.length ? 'PASS' : 'FAIL');
  }
  const unicodeChecks = textChecks.filter(function (value) { return value.unicode; });
  report.unicode_and_escape = unicodeChecks.length > 0 && report.assertions.text === 'PASS' ? 'PASS' : 'NOT_COVERED';

  // Cross-process save/restore: parent saves artifact+state, a fresh node process restores and resumes.
  const crossCase = cases.filter(function (value) { return value.case.choices.length > 0; })
    .sort(function (a, b) { return b.case.choices.length - a.case.choices.length; })[0];
  if (crossCase) {
    const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'poemseed-ink-verify-'));
    const artifactFile = path.join(tempRoot, 'artifact.json');
    const stateFile = path.join(tempRoot, 'state.json');
    const requestFile = path.join(tempRoot, 'request.json');
    const resumeReportFile = path.join(tempRoot, 'resume-report.json');
    try {
      const caseValue = crossCase.case;
      // Save the runtime state before any content is consumed; the fresh process
      // must restore it and replay the complete accepted path to the ending.
      const saveAt = 0;
      const steps = caseSteps(caseValue);
      const story = new runtime.Story(artifactJson);
      fs.writeFileSync(artifactFile, artifactJson);
      fs.writeFileSync(stateFile, story.state.ToJson());
      const remaining = steps.slice(saveAt);
      fs.writeFileSync(requestFile, JSON.stringify({ vendor: path.resolve(args.vendor), artifact: artifactFile,
        state: stateFile, remaining: remaining, variables: variableNames, save_at: saveAt }));
      const child = spawnSync(process.execPath, [MODULE_FILE, '--resume-request', requestFile, '--resume-report', resumeReportFile],
        { encoding: 'utf8', timeout: 120000 });
      const childExit = child.status;
      let childReport = null;
      try { childReport = JSON.parse(fs.readFileSync(resumeReportFile, 'utf8')); } catch (error) { childReport = null; }
      const crossFailures = [];
      if (childExit !== 0) crossFailures.push({ check: 'cross_process', detail: 'resume process exited ' + childExit, stderr: String(child.stderr || '').slice(-1500) });
      if (!childReport) crossFailures.push({ check: 'cross_process', detail: 'resume report missing' });
      if (childReport) {
        if (childReport.pid === process.pid) crossFailures.push({ check: 'cross_process', detail: 'resume did not run in a fresh process' });
        if (childReport.vendor.version !== runtime.version) crossFailures.push({ check: 'cross_process', detail: 'resume runtime version differs' });
        const expectedStates = caseValue.states.slice(saveAt);
        if (childReport.snapshots.length !== expectedStates.length) {
          crossFailures.push({ check: 'cross_process', detail: 'resume snapshot count ' + childReport.snapshots.length + ' != ' + expectedStates.length });
        } else {
          for (let position = 0; position < expectedStates.length; position += 1) {
            const failures = compareState(childReport.snapshots[position], expectedStates[position]);
            for (const failure of failures) crossFailures.push({ check: 'cross_process_' + failure.check, detail: failure.detail,
              expected: failure.expected, actual: failure.actual });
          }
          const finalState = expectedStates[expectedStates.length - 1];
          const resumedFinal = childReport.snapshots[childReport.snapshots.length - 1];
          if (!resumedFinal || !strictEqual(resumedFinal.ink_state, finalState.ink_state)
              || !strictEqual(resumedFinal.variables, finalState.ink_variables)) {
            crossFailures.push({ check: 'cross_process', detail: 'resumed final state differs from witness final state' });
          }
        }
      }
      report.cross_process = {
        performed: true,
        fresh_process: !!(childReport && childReport.pid !== process.pid),
        parent_pid: process.pid,
        child_pid: childReport ? childReport.pid : null,
        child_exit_code: childExit,
        save_at_step: saveAt,
        remaining: remaining,
        snapshots: childReport ? childReport.snapshots.length : 0,
        restored_state_matches: crossFailures.length === 0,
        passed: crossFailures.length === 0,
        detail: crossFailures.length === 0 ? 'save in parent process, resume to the ending in a fresh process' : 'cross-process restore failed',
        failures: crossFailures.slice(0, 6),
      };
      if (crossFailures.length) report.failures.push({ check: 'cross_process', failures: crossFailures.slice(0, 6) });
    } finally {
      try { fs.rmSync(tempRoot, { recursive: true, force: true }); } catch (error) { /* best effort */ }
    }
  }
  report.assertions.save_restore = report.cross_process.performed && report.cross_process.passed ? 'PASS' : 'FAIL';

  const fatal = report.failures.length > 0;
  report.result = (!fatal && allCasesPassed && report.assertions.file_access_denied === 'PASS'
    && report.assertions.endings === 'PASS' && report.assertions.save_restore === 'PASS') ? 'PASS' : 'FAIL';
  writeReport();
}

const args = parseArgs(process.argv.slice(2));
if (args['resume-request']) resumeMode(args);
else mainMode(args);
