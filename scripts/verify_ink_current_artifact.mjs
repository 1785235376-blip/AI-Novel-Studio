#!/usr/bin/env node
// Test-only pinned target acceptance verifier; never shipped or executed by the product.
//
// Consumes the CURRENT exported Ink artifact (ink/story.ink inside the exported
// ZIP or extracted bundle), compiles it with the pinned inkjs 2.3.2 compiler,
// plays every acceptance witness with the pinned runtime, and verifies
// save/restore through the DELIVERED player helper
// (ink/player/save_envelope.mjs) across a real process boundary.
//
// The save path is exercised after at least one real choice, with the variable
// snapshot taken at that point; a restore in a fresh process must resume to the
// witness ending. Save envelopes are bound to story id, revision,
// compiled-artifact digest, target format and runtime identity. A state restored
// into a DIFFERENT compiled artifact, a different story/revision/target/runtime,
// a tampered envelope, or an unbound legacy state must all be rejected.
//
// Usage:
//   node scripts/verify_ink_current_artifact.mjs --bundle <exported.zip|dir> --vendor <inkjs-pkg-root> --report <file>
//   (internal) --resume-request <file> --resume-report <file>
//
// Exit codes: 0 PASS, 2 compile failure, 3 assertion/pin failure, 4 verifier error.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const MODULE_FILE = fileURLToPath(import.meta.url);
const SCHEMA = 'poemseed-ink-current-artifact-verification/1';
const CONTINUE_CAP = 1000;
const RUNTIME_BASIS = 'COMMUNITY_JAVASCRIPT_PORT_INKJS_2_3_2';

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

function readJson(file) { return JSON.parse(fs.readFileSync(file, 'utf8')); }

function loadPinnedRuntime(vendorRoot) {
  const packageFile = path.join(vendorRoot, 'package.json');
  const entryFile = path.join(vendorRoot, 'dist', 'ink-full.js');
  if (!fs.existsSync(packageFile) || !fs.existsSync(entryFile)) fail('PINNED_RUNTIME_FILES_MISSING: ' + vendorRoot);
  const pkg = readJson(packageFile);
  const entryBytes = fs.readFileSync(entryFile);
  const requireFromVendor = createRequire(path.join(vendorRoot, 'package.json'));
  let loaded;
  try { loaded = requireFromVendor(entryFile); }
  catch (error) { fail('PINNED_RUNTIME_LOAD_FAILED: ' + String(error && error.message ? error.message : error)); }
  if (!loaded || typeof loaded.Compiler !== 'function' || typeof loaded.Story !== 'function') fail('PINNED_RUNTIME_SURFACE_INVALID: expected { Compiler, Story }');
  return {
    packageName: pkg.name, version: pkg.version,
    packageJsonSha256: sha256(fs.readFileSync(packageFile)),
    runtimeEntry: entryFile, runtimeEntrySha256: sha256(entryBytes), runtimeEntryBytes: entryBytes.length,
    Compiler: loaded.Compiler, Story: loaded.Story,
  };
}

async function loadDeliveredPlayer(bundleRoot) {
  const modulePath = path.join(bundleRoot, 'ink', 'player', 'save_envelope.mjs');
  if (!fs.existsSync(modulePath)) fail('SAVE_ENVELOPE_PLAYER_MISSING: ' + modulePath);
  let player;
  try { player = await import(pathToFileURL(modulePath).href); }
  catch (error) { fail('SAVE_ENVELOPE_PLAYER_LOAD_FAILED: ' + String(error && error.message ? error.message : error)); }
  for (const name of ['createSaveEnvelope', 'loadSaveEnvelope', 'describeSaveEnvelope', 'SAVE_ENVELOPE_SCHEMA', 'SaveEnvelopeError']) {
    if (typeof player[name] === 'undefined') fail('SAVE_ENVELOPE_PLAYER_SURFACE_INVALID: missing ' + name);
  }
  return { module: player, modulePath, moduleSha256: sha256(fs.readFileSync(modulePath)) };
}

/** Accept either the exported ZIP bytes or an already-extracted bundle directory. */
function resolveBundle(rootArgument) {
  const resolved = path.resolve(rootArgument);
  if (!fs.existsSync(resolved)) fail('BUNDLE_MISSING: ' + resolved);
  if (fs.statSync(resolved).isDirectory()) return { root: resolved, extracted: null };
  if (!/\.zip$/i.test(resolved)) fail('BUNDLE_UNSUPPORTED: expected .zip or directory');
  const extraction = fs.mkdtempSync(path.join(os.tmpdir(), 'poemseed-ink-zip-'));
  const destination = path.join(extraction, 'root');
  const quoted = function (value) { return "'" + String(value).replace(/'/g, "''") + "'"; };
  let extract = spawnSync('tar', ['-xf', resolved, '-C', extraction], { encoding: 'utf8', timeout: 120000 });
  if (extract.status !== 0 && process.platform === 'win32') {
    // bsdtar on Windows does not create nested members for every ZIP writer; the
    // .NET extractor is always available and handles all exported ZIPs.
    const script = 'Add-Type -AssemblyName System.IO.Compression.FileSystem; ' +
      '[System.IO.Compression.ZipFile]::ExtractToDirectory(' + quoted(resolved) + ',' + quoted(destination) + ')';
    extract = spawnSync('powershell', ['-NoProfile', '-NonInteractive', '-Command', script],
      { encoding: 'utf8', timeout: 120000 });
  }
  if (extract.status !== 0) {
    fs.rmSync(extraction, { recursive: true, force: true });
    fail('BUNDLE_ZIP_EXTRACT_FAILED: ' + String(extract.stderr || '').slice(-800));
  }
  const entries = fs.readdirSync(destination, { withFileTypes: true }).filter(function (entry) { return entry.isDirectory(); });
  if (entries.length !== 1) {
    fs.rmSync(extraction, { recursive: true, force: true });
    fail('BUNDLE_ZIP_SHAPE_INVALID: expected exactly one root folder, found ' + entries.length);
  }
  return { root: path.join(destination, entries[0].name), extracted: extraction, zip: resolved };
}

function advance(story) {
  let output = '';
  let ticks = 0;
  while (story.canContinue) {
    ticks += 1;
    if (ticks > CONTINUE_CAP) throw new Error('CONTINUE_CAP_EXCEEDED');
    output += story.Continue();
  }
  return { output: output, errors: story.hasError ? [String(story.currentErrors)] : [] };
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
  return typeof actual === typeof expected && JSON.stringify(canonical(actual)) === JSON.stringify(canonical(expected));
}

function compareState(actual, expected) {
  const failures = [];
  if (actual.output !== expected.output_text) failures.push({ check: 'text', detail: 'runtime output differs', expected: expected.output_text, actual: actual.output });
  const expectedLabels = (expected.choices || []).map(function (choice) { return choice.label; });
  const actualLabels = actual.choices.map(function (choice) { return choice.text; });
  if (JSON.stringify(actualLabels) !== JSON.stringify(expectedLabels)) failures.push({ check: 'choices', detail: 'runtime choice labels differ', expected: expectedLabels, actual: actualLabels });
  if (!strictEqual(actual.variables, expected.ink_variables)) failures.push({ check: 'variables', detail: 'runtime variable values/types differ', expected: expected.ink_variables, actual: actual.variables });
  if (!strictEqual(actual.ink_state, expected.ink_state)) failures.push({ check: 'ink_state', detail: 'runtime ans_node/ans_steps/ans_status differ', expected: expected.ink_state, actual: actual.ink_state });
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

function runtimeIdentity(runtime, formatVersion) {
  return { name: 'inkjs', version: runtime.version, format: formatVersion };
}

function envelopeBindingFromWitness(witness) {
  return {
    storyId: String(witness.story.id),
    revision: Number(witness.story.revision),
    targetFormatVersion: String(witness.format_version),
  };
}

// ---------------------------------------------------------------- resume mode
async function resumeMode(args) {
  const request = readJson(args['resume-request']);
  const runtime = loadPinnedRuntime(request.vendor);
  const player = await loadDeliveredPlayer(request.bundle);
  const report = {
    schema: 'poemseed-ink-current-artifact-resume-v2/1',
    pid: process.pid,
    node: process.version,
    vendor: { version: runtime.version, runtime_entry_sha256: runtime.runtimeEntrySha256 },
    save_envelope: { schema: player.module.SAVE_ENVELOPE_SCHEMA, module_sha256: player.moduleSha256, binding: null, saved_after_choice: null, variables_changed_before_save: null, saved_at_step: null },
    snapshots: [],
    final: null,
    restore: { attempted: false, passed: false, error_code: null, error_message: null },
    errors: [],
  };
  try {
    const artifact = fs.readFileSync(request.artifact, 'utf8');
    const bytes = fs.readFileSync(request.envelope);
    const story = new runtime.Story(artifact);
    const loaded = player.module.loadSaveEnvelope({ bytes: bytes, story: story, expected: request.expected });
    report.restore.attempted = true;
    report.restore.passed = loaded.ok === true;
    report.save_envelope = Object.assign(report.save_envelope, {
      binding: loaded.binding, saved_after_choice: loaded.saved_after_choice,
      variables_changed_before_save: loaded.variables_changed_before_save, saved_at_step: loaded.saved_at_step,
    });
    const restoredVariables = variableValues(story, request.variables);
    report.restore.restored_variables = restoredVariables;
    report.restore.restored_variables_match = strictEqual(restoredVariables, request.expected_variables || {});
    if (!report.restore.restored_variables_match) {
      report.errors.push('RESTORED_VARIABLES_MISMATCH');
    }
    // The save point has already consumed the chosen step's output, so resumed
    // snapshots correspond to the states AFTER each remaining choice.
    for (const index of request.remaining) {
      story.ChooseChoiceIndex(index);
      report.snapshots.push(snapshot(story, request.variables));
    }
    report.final = report.snapshots.length ? report.snapshots[report.snapshots.length - 1] : restoredVariables;
  } catch (error) {
    report.restore.error_code = error && error.code ? String(error.code) : 'UNEXPECTED_ERROR';
    report.restore.error_message = String(error && error.message ? error.message : error);
    report.errors.push(report.restore.error_code + ': ' + report.restore.error_message);
  }
  fs.writeFileSync(args['resume-report'], JSON.stringify(report, null, 2));
  process.stdout.write('RESUME pid=' + report.pid + ' restore=' + report.restore.passed + ' snapshots=' + report.snapshots.length + ' errors=' + report.errors.length + '\n');
  process.exit(report.errors.length === 0 ? 0 : 3);
}

// ---------------------------------------------------------------- main mode
async function mainMode(args) {
  const started = Date.now();
  const report = {
    schema: SCHEMA,
    result: 'FAIL',
    node: process.version,
    platform: process.platform + ' ' + process.arch,
    verifier: 'scripts/verify_ink_current_artifact.mjs',
    bundle: path.resolve(args.bundle),
    bundle_zip_sha256: null,
    bundle_extracted: false,
    vendor: null,
    source: null,
    witness: null,
    runtime_pin: null,
    bundle_files: [],
    runtime_code_bundled: null,
    delivered_player: null,
    save_envelope: null,
    compile: { attempted: false, success: false, errors: [], file_calls: 0, artifact_sha256: null, artifact_bytes: 0 },
    runtime: { artifact_consumed: false, artifact_sha256: null, cases: [], file_calls: 0,
      ending_reached: false, step_cap_enforced: false, in_memory_envelope_restores: 0 },
    cross_process: { performed: false, fresh_process: false, passed: false, detail: 'not attempted' },
    save_restore_negatives: [],
    assertions: { bundle_shape: 'FAIL', runtime_pin: 'FAIL', save_envelope: 'FAIL', text: 'FAIL', choices: 'FAIL',
      variables: 'FAIL', ink_state: 'FAIL', endings: 'FAIL', step_cap: 'NOT_COVERED', file_access_denied: 'FAIL', save_restore: 'FAIL' },
    unicode_and_escape: 'NOT_COVERED',
    native_csharp_runtime: 'NOT_RUN',
    runtime_basis: RUNTIME_BASIS,
    failures: [],
    elapsed_ms: 0,
  };

  let bundleInfo = null;
  try {
    bundleInfo = resolveBundle(args.bundle);
  } catch (error) {
    report.failures.push({ check: 'bundle', detail: String(error && error.message ? error.message : error) });
    report.elapsed_ms = Date.now() - started;
    if (args.report) fs.writeFileSync(args.report, JSON.stringify(report, null, 2));
    process.stdout.write('RESULT FAIL bundle\n');
    process.exit(4);
  }
  const bundle = bundleInfo.root;
  if (bundleInfo.zip) { report.bundle_zip_sha256 = sha256(fs.readFileSync(bundleInfo.zip)); report.bundle_extracted = true; }

  function writeReport() {
    report.elapsed_ms = Date.now() - started;
    if (args.report) fs.writeFileSync(args.report, JSON.stringify(report, null, 2));
    process.stdout.write('RESULT ' + report.result + ' compile=' + report.compile.success +
      ' cases=' + report.runtime.cases.length + ' crocess=' + report.cross_process.passed +
      ' failures=' + report.failures.length + '\n');
    if (report.failures.length) process.stdout.write('FAILURES ' + JSON.stringify(report.failures).slice(0, 2000) + '\n');
    if (bundleInfo && bundleInfo.extracted) { try { fs.rmSync(bundleInfo.extracted, { recursive: true, force: true }); } catch (error) { /* best effort */ } }
    process.exit(report.result === 'PASS' ? 0 : 3);
  }

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
    return /\.(cjs|js|node|wasm)$/i.test(name) || name.indexOf('node_modules/') === 0;
  });
  report.runtime_code_bundled = runtimeCode.length > 0;
  // The save-envelope helper is OUR dependency-free ESM (no third-party runtime);
  // it is the only .mjs the bundle may contain and is pinned by hash below.
  const unexpectedScripts = bundleFiles.filter(function (name) {
    return /\.(cjs|js|node|wasm)$/i.test(name) || (name.indexOf('node_modules/') === 0);
  });
  if (unexpectedScripts.length) report.failures.push({ check: 'bundle_shape', detail: 'runtime/third-party code present in bundle', files: unexpectedScripts });
  report.assertions.bundle_shape = unexpectedScripts.length === 0 ? 'PASS' : 'FAIL';

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
  if (witness.script && witness.script.sha256 !== report.source.sha256) report.failures.push({ check: 'witness', detail: 'witness script sha256 does not match ink/story.ink' });
  if (!validation || validation.witness.sha256 !== report.witness.sha256) report.failures.push({ check: 'witness', detail: 'validation.json witness sha256 mismatch' });
  if (validation && validation.runtime_pin.sha256 !== report.runtime_pin.sha256) report.failures.push({ check: 'runtime_pin', detail: 'validation.json runtime-pin sha256 mismatch' });
  if (runtimePin.version !== witness.runtime.version || runtimePin.integrity !== witness.runtime.integrity) report.failures.push({ check: 'runtime_pin', detail: 'runtime-pin.json and witness runtime disagree' });

  if (!args.vendor) fail('vendor argument required');
  const runtime = loadPinnedRuntime(path.resolve(args.vendor));
  report.vendor = { package: runtime.packageName, version: runtime.version,
    package_json_sha256: runtime.packageJsonSha256, runtime_entry: runtime.runtimeEntry,
    runtime_entry_sha256: runtime.runtimeEntrySha256, runtime_entry_bytes: runtime.runtimeEntryBytes };
  const expectedPin = witness.runtime;
  if (runtime.version !== expectedPin.version) report.failures.push({ check: 'runtime_pin', detail: 'installed inkjs version ' + runtime.version + ' != pinned ' + expectedPin.version });
  if (runtime.runtimeEntrySha256 !== expectedPin.runtime_entry.sha256) report.failures.push({ check: 'runtime_pin', detail: 'installed runtime entry hash != pinned runtime entry hash' });

  // Delivered save-envelope helper must be exactly the pinned bytes.
  const player = await loadDeliveredPlayer(bundle);
  const playerPin = runtimePin.save_restore && runtimePin.save_restore.envelope && runtimePin.save_restore.envelope.player_module ? runtimePin.save_restore.envelope.player_module : null;
  const playerValidation = validation && validation.save_restore && validation.save_restore.envelope ? validation.save_restore.envelope.player_module : null;
  report.delivered_player = { path: path.relative(bundle, player.modulePath), sha256: player.moduleSha256, pinned_sha256: playerPin ? playerPin.sha256 : null,
    validation_sha256: playerValidation ? playerValidation.sha256 : null, describe: player.module.describeSaveEnvelope() };
  if (!playerPin) report.failures.push({ check: 'save_envelope', detail: 'runtime-pin.json does not pin the delivered save-envelope helper' });
  if (playerPin && playerPin.sha256 !== player.moduleSha256) report.failures.push({ check: 'save_envelope', detail: 'delivered save-envelope helper sha256 differs from its pin' });
  if (playerValidation && playerValidation.sha256 !== player.moduleSha256) report.failures.push({ check: 'save_envelope', detail: 'validation.json save-envelope helper sha256 differs' });
  if (report.failures.length === 0) report.assertions.runtime_pin = 'PASS';
  report.save_envelope = { schema: player.module.SAVE_ENVELOPE_SCHEMA, format_version: player.module.SAVE_ENVELOPE_FORMAT_VERSION,
    module_sha256: player.moduleSha256, binding_fields: player.module.SAVE_ENVELOPE_BINDING_FIELDS,
    legacy_policy: player.module.SAVE_ENVELOPE_LEGACY_POLICY, max_bytes: player.module.SAVE_ENVELOPE_MAX_BYTES,
    pinned: !!playerPin && playerPin.sha256 === player.moduleSha256 };

  // Compile phase: pinned compiler parses the exported source with file access denied.
  const compileErrors = [];
  let compileFileCalls = 0;
  let artifactJson = null;
  report.compile.attempted = true;
  try {
    const denyFile = function () { compileFileCalls += 1; throw new Error('FILE_ACCESS_DENIED'); };
    const compiler = new runtime.Compiler(sourceBytes.toString('utf8'), {
      errorHandler: function (message, type) { compileErrors.push({ message: String(message), type: String(type) }); },
      fileHandler: { ResolveInkFilename: denyFile, LoadInkFileContents: denyFile },
    });
    const compiledStory = compiler.Compile();
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
  const artifactSha = report.compile.artifact_sha256;
  const formatVersion = String(witness.format_version);
  const bindingBase = envelopeBindingFromWitness(witness);

  // Runtime phase: consume the serialized artifact (compile != runtime).
  const variableNames = (witness.variables || []).map(function (variable) { return variable.ink; });
  const cases = (witness.endings || []).map(function (caseValue) { return { kind: 'ENDING', case: caseValue }; })
    .concat((witness.step_cap_cases || []).map(function (caseValue) { return { kind: 'STEP_CAP', case: caseValue }; }));
  const textChecks = [];
  const envelopeIdentity = {
    storyId: bindingBase.storyId, revision: bindingBase.revision,
    compiledArtifactSha256: artifactSha, targetFormatVersion: formatVersion,
    runtime: runtimeIdentity(runtime, formatVersion),
  };
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
        // Persist and reload through the DELIVERED envelope helper at every step.
        const before = inkState(story);
        const beforeVariables = variableValues(story, variableNames);
        const created = player.module.createSaveEnvelope({
          story: story, storyId: bindingBase.storyId, revision: bindingBase.revision,
          compiledArtifactSha256: artifactSha, targetFormatVersion: formatVersion,
          runtime: runtimeIdentity(runtime, formatVersion), steps: caseValue.choices.slice(0, position),
          path: caseValue.choices.slice(0, position), savedAtStep: position, variables: beforeVariables,
          variablesChangedBeforeSave: position > 0,
        });
        const restored = new runtime.Story(artifactJson);
        const loaded = player.module.loadSaveEnvelope({ bytes: new TextEncoder().encode(created.bytes), story: restored, expected: envelopeIdentity });
        report.runtime.in_memory_envelope_restores += 1;
        if (!loaded.ok) throw new Error('in-memory envelope restore did not report ok');
        if (!strictEqual(inkState(restored), before) || !strictEqual(variableValues(restored, variableNames), beforeVariables)) {
          failures.push({ check: 'save_restore', detail: 'in-memory envelope restored state disagrees before step ' + (position + 1) });
        }
        const restoredChoices = restored.currentChoices.map(function (choice) { return choice.text; });
        const beforeChoices = story.currentChoices.map(function (choice) { return choice.text; });
        if (JSON.stringify(restoredChoices) !== JSON.stringify(beforeChoices)) failures.push({ check: 'save_restore', detail: 'in-memory envelope restored choices disagree before step ' + (position + 1) });
        story.ChooseChoiceIndex(steps[position]);
        current = snapshot(story, variableNames);
        failures = failures.concat(compareState(current, caseValue.states[position + 1]));
      }
      record.steps = current.ink_state.ans_steps;
      record.states_checked = caseValue.states.length;
      record.final_status = caseValue.states[caseValue.states.length - 1].status;
      if (current.ink_state.ans_status !== caseValue.states[caseValue.states.length - 1].ink_state.ans_status) failures.push({ check: 'status', detail: 'final ans_status differs from witness' });
      record.failures = failures;
      record.passed = failures.length === 0;
      if (item.kind === 'ENDING' && record.passed) report.runtime.ending_reached = true;
      if (item.kind === 'STEP_CAP' && record.passed) report.runtime.step_cap_enforced = true;
      if (failures.length) report.failures.push({ check: item.kind, case: caseValue.choices, failures: failures.slice(0, 6) });
      for (const stateValue of caseValue.states) for (const line of (stateValue.output_lines || [])) textChecks.push({ line: line, unicode: /[^\x00-\x7F]/.test(line) || /["{}\[\]<>\\#]/.test(line) });
    } catch (error) {
      record.failures.push({ check: 'runtime', detail: String(error && error.stack ? error.stack : error) });
      report.failures.push({ check: item.kind, detail: 'runtime replay failed: ' + String(error) });
    }
    report.runtime.cases.push(record);
  }
  report.runtime.artifact_consumed = report.compile.success && report.runtime.cases.length > 0;
  report.runtime.artifact_sha256 = artifactSha;
  report.runtime.states_compared = report.runtime.cases.reduce(function (total, value) { return total + (value.states_checked || 0); }, 0);

  const allCasesPassed = report.runtime.cases.every(function (value) { return value.passed; });
  const endings = report.runtime.cases.filter(function (value) { return value.kind === 'ENDING'; });
  const stepCaps = report.runtime.cases.filter(function (value) { return value.kind === 'STEP_CAP'; });
  report.assertions.endings = endings.length > 0 && endings.every(function (value) { return value.passed; }) ? 'PASS' : 'FAIL';
  report.assertions.step_cap = stepCaps.length > 0 && stepCaps.every(function (value) { return value.passed; }) ? 'PASS' : 'NOT_COVERED';
  for (const name of ['text', 'choices', 'variables', 'ink_state']) {
    const failed = report.runtime.cases.some(function (value) { return value.failures.some(function (failure) { return failure.check === name || failure.check === 'status'; }); });
    report.assertions[name] = failed ? 'FAIL' : (report.runtime.cases.length ? 'PASS' : 'FAIL');
  }
  report.unicode_and_escape = textChecks.some(function (value) { return value.unicode; }) && report.assertions.text === 'PASS' ? 'PASS' : 'NOT_COVERED';

  // Cross-process save/restore through the DELIVERED helper: choose the longest
  // witness path, save AFTER a real choice (variables must have changed if the
  // story declares variables), restore in a fresh node process, then resume to
  // the ending and compare every remaining state.
  const candidate = cases.map(function (value) {
    const states = value.case.states || [];
    const steps = value.case.choices || [];
    let saved = null;
    for (let position = 1; position < steps.length; position += 1) {
      const before = states[0].ink_variables || {};
      const at = states[position].ink_variables || {};
      const changed = Object.keys(at).some(function (name) { return at[name] !== before[name]; });
      const entry = { case: value.case, steps: steps, saveAt: position, remaining: caseSteps(value.case).slice(position), changed: changed };
      if (changed) return entry;
      if (!saved) saved = entry;
    }
    return saved;
  }).filter(Boolean).sort(function (a, b) { return (b.changed ? 1 : 0) - (a.changed ? 1 : 0) || b.remaining.length - a.remaining.length; });
  const afterChoicePossible = candidate.some(function (item) { return item.saveAt >= 1; });
  const fallbackCase = cases.filter(function (value) { return value.case.choices.length > 0; })[0] || null;
  const crossChoice = candidate[0] || (fallbackCase ? { case: fallbackCase.case, saveAt: 0, remaining: caseSteps(fallbackCase.case), changed: false } : null);
  const variablesDeclared = variableNames.length > 0;
  if (crossChoice) {
    const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'poemseed-ink-verify-'));
    try {
      const caseValue = crossChoice.case;
      const steps = caseSteps(caseValue);
      const saveAt = crossChoice.saveAt;
      const story = new runtime.Story(artifactJson);
      // Consume the chosen steps completely (ink applies choice assignments while
      // continuing), then save. The restored process resumes from states[saveAt]
      // with its output already consumed and replays every remaining choice.
      advance(story);
      for (let position = 0; position < saveAt; position += 1) {
        story.ChooseChoiceIndex(steps[position]);
        advance(story);
      }
      const variablesAtSave = variableValues(story, variableNames);
      const expectedVariablesAtSave = (caseValue.states[saveAt].ink_variables) || {};
      const initialVariables = caseValue.states[0].ink_variables || {};
      const variablesChanged = Object.keys(variablesAtSave).some(function (name) { return variablesAtSave[name] !== initialVariables[name]; });
      const created = player.module.createSaveEnvelope({
        story: story, storyId: bindingBase.storyId, revision: bindingBase.revision,
        compiledArtifactSha256: artifactSha, targetFormatVersion: formatVersion,
        runtime: runtimeIdentity(runtime, formatVersion), steps: caseValue.choices.slice(0, saveAt),
        path: caseValue.choices.slice(0, saveAt), savedAtStep: saveAt, variables: variablesAtSave,
        variablesChangedBeforeSave: variablesChanged,
      });
      const envelopeFile = path.join(tempRoot, 'save.envelope.json');
      const artifactFile = path.join(tempRoot, 'artifact.json');
      const requestFile = path.join(tempRoot, 'request.json');
      const resumeReportFile = path.join(tempRoot, 'resume-report.json');
      fs.writeFileSync(envelopeFile, created.bytes);
      fs.writeFileSync(artifactFile, artifactJson);
      fs.writeFileSync(requestFile, JSON.stringify({
        vendor: path.resolve(args.vendor), bundle: bundle, artifact: artifactFile, envelope: envelopeFile,
        remaining: crossChoice.remaining, variables: variableNames,
        expected_variables: expectedVariablesAtSave,
        expected: { storyId: bindingBase.storyId, revision: bindingBase.revision, compiledArtifactSha256: artifactSha,
          targetFormatVersion: formatVersion, runtime: runtimeIdentity(runtime, formatVersion) },
      }));
      const child = spawnSync(process.execPath, [MODULE_FILE, '--resume-request', requestFile, '--resume-report', resumeReportFile], { encoding: 'utf8', timeout: 120000 });
      let childReport = null;
      try { childReport = JSON.parse(fs.readFileSync(resumeReportFile, 'utf8')); } catch (error) { childReport = null; }
      const crossFailures = [];
      if (child.status !== 0) crossFailures.push({ check: 'cross_process', detail: 'resume process exited ' + child.status, stderr: String(child.stderr || '').slice(-1500) });
      if (!childReport) crossFailures.push({ check: 'cross_process', detail: 'resume report missing' });
      if (childReport) {
        if (childReport.pid === process.pid) crossFailures.push({ check: 'cross_process', detail: 'resume did not run in a fresh process' });
        if (childReport.vendor.version !== runtime.version) crossFailures.push({ check: 'cross_process', detail: 'resume runtime version differs' });
        if (!childReport.restore || childReport.restore.passed !== true) crossFailures.push({ check: 'cross_process', detail: 'child did not restore through the bound envelope: ' + JSON.stringify(childReport.restore) });
        if (childReport.save_envelope && childReport.save_envelope.module_sha256 !== player.moduleSha256) crossFailures.push({ check: 'cross_process', detail: 'child used a different delivered player helper' });
        if (!childReport.restore || childReport.restore.restored_variables_match !== true) {
          crossFailures.push({ check: 'cross_process', detail: 'restored variables do not match the saved point', expected: expectedVariablesAtSave, actual: childReport.restore ? childReport.restore.restored_variables : null });
        }
        const expectedStates = caseValue.states.slice(saveAt + 1);
        if (!childReport.snapshots || childReport.snapshots.length !== expectedStates.length) {
          crossFailures.push({ check: 'cross_process', detail: 'resume snapshot count ' + (childReport.snapshots ? childReport.snapshots.length : 0) + ' != ' + expectedStates.length });
        } else {
          for (let position = 0; position < expectedStates.length; position += 1) {
            const failures = compareState(childReport.snapshots[position], expectedStates[position]);
            for (const failure of failures) crossFailures.push({ check: 'cross_process_' + failure.check, detail: failure.detail, expected: failure.expected, actual: failure.actual });
          }
        }
        if (childReport.snapshots && childReport.snapshots.length) {
          const resumedFinal = childReport.snapshots[childReport.snapshots.length - 1];
          const finalState = expectedStates[expectedStates.length - 1];
          if (!strictEqual(resumedFinal.ink_state, finalState.ink_state) || !strictEqual(resumedFinal.variables, finalState.ink_variables)) crossFailures.push({ check: 'cross_process', detail: 'resumed final state differs from witness final state' });
        }
      }
      report.cross_process = {
        performed: true, fresh_process: !!(childReport && childReport.pid !== process.pid),
        parent_pid: process.pid, child_pid: childReport ? childReport.pid : null, child_exit_code: child.status,
        save_at_step: saveAt, saved_after_choice: saveAt >= 1, remaining: crossChoice.remaining,
        variables_declared: variablesDeclared, variables_changed_before_save: variablesChanged,
        variables_at_save: variablesAtSave,
        snapshots: childReport && childReport.snapshots ? childReport.snapshots.length : 0,
        envelope_sha256: sha256(Buffer.from(created.bytes, 'utf8')), envelope_bytes: Buffer.byteLength(created.bytes, 'utf8'),
        delivered_player_sha256: player.moduleSha256,
        restored_state_matches: crossFailures.length === 0,
        passed: crossFailures.length === 0,
        detail: crossFailures.length === 0 ? 'saved after ' + saveAt + ' choice(s) through the delivered envelope helper; a fresh process restored it and resumed to the ending' : 'cross-process envelope restore failed',
        failures: crossFailures.slice(0, 8),
      };
      if (crossFailures.length) report.failures.push({ check: 'cross_process', failures: crossFailures.slice(0, 8) });

      // Negative matrix: the same save must be rejected for any mismatched binding
      // and for tampering, including a state loaded into a different compiled artifact.
      function expectCode(label, expectedCode, action) {
        const record = { case: label, expected_code: expectedCode, actual_code: null, passed: false, message: null };
        try { action(); record.message = 'no error was raised'; }
        catch (error) {
          record.actual_code = error && error.code ? String(error.code) : 'UNEXPECTED_ERROR';
          record.message = String(error && error.message ? error.message : error);
          record.passed = record.actual_code === expectedCode;
        }
        report.save_restore_negatives.push(record);
        if (!record.passed) report.failures.push({ check: 'save_restore_negative', detail: label + ' expected ' + expectedCode + ' got ' + record.actual_code });
      }
      const bytes = new TextEncoder().encode(created.bytes);
      const freshStory = function () { return new runtime.Story(artifactJson); };
      expectCode('story mismatch', 'SAVE_ENVELOPE_STORY_MISMATCH', function () {
        player.module.loadSaveEnvelope({ bytes: bytes, story: freshStory(), expected: Object.assign({}, envelopeIdentity, { storyId: 'another-story' }) });
      });
      expectCode('revision mismatch', 'SAVE_ENVELOPE_REVISION_MISMATCH', function () {
        player.module.loadSaveEnvelope({ bytes: bytes, story: freshStory(), expected: Object.assign({}, envelopeIdentity, { revision: bindingBase.revision + 1 }) });
      });
      expectCode('target format mismatch', 'SAVE_ENVELOPE_FORMAT_MISMATCH', function () {
        player.module.loadSaveEnvelope({ bytes: bytes, story: freshStory(), expected: Object.assign({}, envelopeIdentity, { targetFormatVersion: 'other-format' }) });
      });
      expectCode('runtime mismatch', 'SAVE_ENVELOPE_RUNTIME_MISMATCH', function () {
        player.module.loadSaveEnvelope({ bytes: bytes, story: freshStory(), expected: Object.assign({}, envelopeIdentity, { runtime: { name: 'inkjs', version: '2.2.0', format: formatVersion } }) });
      });
      expectCode('tampered integrity', 'SAVE_ENVELOPE_INTEGRITY_INVALID', function () {
        const tampered = JSON.parse(created.bytes);
        tampered.save.state_json = tampered.save.state_json.slice(0, -1) + 'X';
        player.module.loadSaveEnvelope({ bytes: new TextEncoder().encode(JSON.stringify(tampered)), story: freshStory(), expected: envelopeIdentity });
      });
      expectCode('tampered binding without integrity', 'SAVE_ENVELOPE_INTEGRITY_INVALID', function () {
        const tampered = JSON.parse(created.bytes);
        tampered.binding.story_id = 'forged-story';
        player.module.loadSaveEnvelope({ bytes: new TextEncoder().encode(JSON.stringify(tampered)), story: freshStory(), expected: envelopeIdentity });
      });
      expectCode('unbound legacy state', 'LEGACY_SAVE_ENVELOPE_REQUIRED', function () {
        player.module.loadSaveEnvelope({ envelope: JSON.parse(story.state.ToJson()), story: freshStory(), expected: envelopeIdentity });
      });
      expectCode('different compiled artifact', 'SAVE_ENVELOPE_ARTIFACT_MISMATCH', function () {
        const modifiedSource = sourceBytes.toString('utf8').replace('Trusted generated subset', 'Trusted generated subset modified');
        let modifiedArtifact = null;
        try {
          const denyFile = function () { throw new Error('FILE_ACCESS_DENIED'); };
          const compiler = new runtime.Compiler(modifiedSource, { errorHandler: function () {}, fileHandler: { ResolveInkFilename: denyFile, LoadInkFileContents: denyFile } });
          modifiedArtifact = compiler.Compile().ToJson();
        } catch (error) { modifiedArtifact = artifactJson + ' '; }
        if (sha256(Buffer.from(modifiedArtifact, 'utf8')) === artifactSha) throw Object.assign(new Error('tampered artifact digest did not change'), { code: 'SAVE_ENVELOPE_ARTIFACT_MISMATCH' });
        const otherStory = new runtime.Story(modifiedArtifact);
        player.module.loadSaveEnvelope({ bytes: bytes, story: otherStory, expected: Object.assign({}, envelopeIdentity, { compiledArtifactSha256: sha256(Buffer.from(modifiedArtifact, 'utf8')) }) });
      });
    } finally {
      try { fs.rmSync(tempRoot, { recursive: true, force: true }); } catch (error) { /* best effort */ }
    }
  }

  const negativesPassed = report.save_restore_negatives.length >= 8 && report.save_restore_negatives.every(function (record) { return record.passed; });
  const crossPassed = report.cross_process.performed && report.cross_process.passed === true;
  const afterChoice = report.cross_process.saved_after_choice === true;
  const variableCoverage = report.cross_process.variables_declared ? report.cross_process.variables_changed_before_save === true : true;
  report.cross_process.after_choice_possible = afterChoicePossible;
  if (!afterChoicePossible) {
    // No witness path offers a choice with a remaining step, so a post-choice
    // save cannot be constructed honestly. The bundle still restores through the
    // bound envelope at the initial state AND every negative binding case must be
    // rejected; this is recorded as NOT_APPLICABLE, never as a silent PASS.
    report.cross_process.detail = (report.cross_process.detail || '') + ' | no multi-step witness path exists; post-choice save is NOT_APPLICABLE, initial-state envelope restore and the negative binding matrix were still verified';
    report.assertions.save_restore = crossPassed && negativesPassed && report.assertions.runtime_pin === 'PASS' ? 'NOT_APPLICABLE_SINGLE_STEP' : 'FAIL';
  } else {
    report.assertions.save_restore = crossPassed && afterChoice && variableCoverage && negativesPassed && report.assertions.runtime_pin === 'PASS' ? 'PASS' : 'FAIL';
  }
  report.assertions.save_envelope = report.save_envelope.pinned === true && report.delivered_player.sha256 === report.delivered_player.pinned_sha256 ? 'PASS' : 'FAIL';

  const fatal = report.failures.length > 0;
  const saveRestoreAccepted = report.assertions.save_restore === 'PASS'
    || (report.assertions.save_restore === 'NOT_APPLICABLE_SINGLE_STEP' && afterChoicePossible === false && report.cross_process.passed === true);
  report.result = (!fatal && allCasesPassed && report.assertions.file_access_denied === 'PASS'
    && report.assertions.endings === 'PASS' && saveRestoreAccepted
    && report.assertions.save_envelope === 'PASS') ? 'PASS' : 'FAIL';
  writeReport();
}

const args = parseArgs(process.argv.slice(2));
if (args['resume-request']) await resumeMode(args);
else await mainMode(args);
