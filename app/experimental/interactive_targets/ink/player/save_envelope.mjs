// PoemSeed Ink save envelope (trusted, dependency-free ESM player helper).
//
// Save data carries a versioned envelope that binds it to ONE story identity,
// revision, compiled-artifact digest, target format and runtime identity. The
// helper in this file is what the delivered bundle actually ships; the
// acceptance verifier imports THAT file so the tested entry point and the
// delivered entry point cannot drift.
//
// Security rules:
//   * No imports, no dynamic code, no file/network access, no eval.
//   * The envelope is bounded before parsing and before state restore.
//   * Restore REQUIRES the complete current-artifact context (story id, revision,
//     compiled-artifact digest, target format and runtime name/version/format).
//     The helper never derives that context from the save being loaded: a missing,
//     empty, partial or malformed context fails before any state is loaded.
//   * An unbound/legacy save is rejected with an explicit code; it is never
//     silently trusted. Migration requires an explicit caller-supplied binding and
//     is labelled as migrated, never as verified execution.
//
// This module is a pure ESM file; it runs in Node >= 18 and in modern browsers.

export const SAVE_ENVELOPE_SCHEMA = 'poemseed-ink-save-envelope/1';
export const SAVE_ENVELOPE_FORMAT_VERSION = 'ink-save-envelope-1';
export const SAVE_ENVELOPE_LEGACY_POLICY = 'UNBOUND_LEGACY_SAVE_REJECTED_EXPLICIT_MIGRATION_REQUIRED';
export const SAVE_ENVELOPE_MAX_BYTES = 2 * 1024 * 1024;
export const SAVE_ENVELOPE_BINDING_FIELDS = ['story_id', 'revision', 'compiled_artifact_sha256', 'target_format_version', 'runtime'];
// The caller must supply these from the CURRENTLY loaded artifact and runtime.
export const SAVE_ENVELOPE_RESTORE_CONTEXT_FIELDS = ['storyId', 'revision', 'compiledArtifactSha256', 'targetFormatVersion', 'runtime'];
export const SAVE_ENVELOPE_CONTEXT_REQUIRED = 'SAVE_ENVELOPE_CONTEXT_REQUIRED';
export const SAVE_ENVELOPE_CONTEXT_INVALID = 'SAVE_ENVELOPE_CONTEXT_INVALID';

export class SaveEnvelopeError extends Error {
  constructor(code, message, detail) {
    super(code + ': ' + message);
    this.name = 'SaveEnvelopeError';
    this.code = code;
    this.detail = detail || {};
  }
}

const SHA256_K = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

function rotr(value, count) { return (value >>> count) | (value << (32 - count)); }

/** Minimal SHA-256 (UTF-8 text -> lowercase hex), no dependencies. */
export function sha256Hex(text) {
  const data = new TextEncoder().encode(String(text));
  const bitLength = data.length * 8;
  const padded = new Uint8Array(((data.length + 9 + 63) >> 6) << 6);
  padded.set(data);
  padded[data.length] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(padded.length - 8, Math.floor(bitLength / 4294967296));
  view.setUint32(padded.length - 4, bitLength >>> 0);
  const state = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
  const words = new Uint32Array(64);
  for (let offset = 0; offset < padded.length; offset += 64) {
    for (let index = 0; index < 16; index += 1) words[index] = view.getUint32(offset + index * 4);
    for (let index = 16; index < 64; index += 1) {
      const s0 = rotr(words[index - 15], 7) ^ rotr(words[index - 15], 18) ^ (words[index - 15] >>> 3);
      const s1 = rotr(words[index - 2], 17) ^ rotr(words[index - 2], 19) ^ (words[index - 2] >>> 10);
      words[index] = (words[index - 16] + s0 + words[index - 7] + s1) >>> 0;
    }
    let [a, b, c, d, e, f, g, h] = state;
    for (let index = 0; index < 64; index += 1) {
      const s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const ch = (e & f) ^ (~e & g);
      const t1 = (h + s1 + ch + SHA256_K[index] + words[index]) >>> 0;
      const s0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const t2 = (s0 + maj) >>> 0;
      h = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0;
    }
    state[0] = (state[0] + a) >>> 0; state[1] = (state[1] + b) >>> 0;
    state[2] = (state[2] + c) >>> 0; state[3] = (state[3] + d) >>> 0;
    state[4] = (state[4] + e) >>> 0; state[5] = (state[5] + f) >>> 0;
    state[6] = (state[6] + g) >>> 0; state[7] = (state[7] + h) >>> 0;
  }
  let hex = '';
  for (const value of state) hex += value.toString(16).padStart(8, '0');
  return hex;
}

/** Deterministic JSON: object keys sorted recursively, no whitespace. */
export function canonicalJson(value) {
  if (value === null) return 'null';
  const kind = typeof value;
  if (kind === 'boolean') return value ? 'true' : 'false';
  if (kind === 'number') {
    if (!Number.isFinite(value)) throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'non-finite number in envelope payload');
    return JSON.stringify(value);
  }
  if (kind === 'string') return JSON.stringify(value);
  if (Array.isArray(value)) return '[' + value.map(canonicalJson).join(',') + ']';
  if (kind === 'object') {
    const keys = Object.keys(value).sort();
    return '{' + keys.map(key => JSON.stringify(key) + ':' + canonicalJson(value[key])).join(',') + '}';
  }
  throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'unsupported value type in envelope payload: ' + kind);
}

const HEX64 = /^[0-9a-f]{64}$/;
const SCALAR_TYPES = new Set(['boolean', 'number']);

function requireText(value, code, field, maxLength) {
  if (typeof value !== 'string' || !value.trim() || value.length > maxLength) throw new SaveEnvelopeError(code, field + ' must be bounded non-empty text');
  return value;
}

function requireDigest(value, field, code) {
  if (typeof value !== 'string' || !HEX64.test(value)) throw new SaveEnvelopeError(code || 'SAVE_ENVELOPE_SCHEMA_INVALID', field + ' must be a lowercase sha256 digest');
  return value;
}

function requireRuntime(runtime, code, requireFormat) {
  if (!runtime || typeof runtime !== 'object' || Array.isArray(runtime)) throw new SaveEnvelopeError(code, 'runtime identity must be an object');
  requireText(runtime.name, code, 'runtime.name', 80);
  requireText(runtime.version, code, 'runtime.version', 80);
  if (requireFormat || runtime.format != null) requireText(runtime.format, code, 'runtime.format', 80);
  return runtime;
}

/**
 * Validate the complete restore context supplied by the caller from the CURRENT
 * loaded artifact/runtime. This is deliberately independent from the envelope:
 * the save is never allowed to fill in its own expected identity.
 */
function requireRestoreContext(expected) {
  if (expected === undefined || expected === null) {
    throw new SaveEnvelopeError(SAVE_ENVELOPE_CONTEXT_REQUIRED,
      'restore requires the complete current-artifact context (expected: ' + SAVE_ENVELOPE_RESTORE_CONTEXT_FIELDS.join(', ') + ')');
  }
  if (typeof expected !== 'object' || Array.isArray(expected)) {
    throw new SaveEnvelopeError(SAVE_ENVELOPE_CONTEXT_INVALID, 'restore context must be an object');
  }
  requireText(expected.storyId, SAVE_ENVELOPE_CONTEXT_INVALID, 'expected.storyId', 80);
  if (!Number.isInteger(expected.revision) || expected.revision < 1) {
    throw new SaveEnvelopeError(SAVE_ENVELOPE_CONTEXT_INVALID, 'expected.revision must be a positive integer');
  }
  requireDigest(expected.compiledArtifactSha256, 'expected.compiledArtifactSha256', SAVE_ENVELOPE_CONTEXT_INVALID);
  requireText(expected.targetFormatVersion, SAVE_ENVELOPE_CONTEXT_INVALID, 'expected.targetFormatVersion', 40);
  requireRuntime(expected.runtime, SAVE_ENVELOPE_CONTEXT_INVALID, true);
  return expected;
}

function normalizedPayload(envelope) {
  return { schema: envelope.schema, binding: envelope.binding, save: envelope.save };
}

export function computeEnvelopeDigest(envelope) {
  return sha256Hex(canonicalJson(normalizedPayload(envelope)));
}

function looksLikeLegacyInkState(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  if (typeof value.schema === 'string') return false;
  const keys = Object.keys(value);
  return keys.includes('callstack') || keys.includes('currentChoices') || keys.includes('variablesState') || keys.includes('outputStream') || keys.includes('inkSaveVersion');
}

export function describeSaveEnvelope() {
  return {
    schema: SAVE_ENVELOPE_SCHEMA,
    format_version: SAVE_ENVELOPE_FORMAT_VERSION,
    binding_fields: [...SAVE_ENVELOPE_BINDING_FIELDS],
    max_bytes: SAVE_ENVELOPE_MAX_BYTES,
    legacy_policy: SAVE_ENVELOPE_LEGACY_POLICY,
    integrity: 'sha256(canonical-json(schema,binding,save))',
    restore_context_required: true,
    restore_context_fields: [...SAVE_ENVELOPE_RESTORE_CONTEXT_FIELDS],
    restore_context_errors: [SAVE_ENVELOPE_CONTEXT_REQUIRED, SAVE_ENVELOPE_CONTEXT_INVALID],
    restore_context_policy: 'CALLER_MUST_DERIVE_FROM_CURRENT_LOADED_ARTIFACT_AND_RUNTIME_NEVER_FROM_SAVE',
  };
}

/** Create a save envelope for the exact delivered artifact and runtime. */
export function createSaveEnvelope(options) {
  const { story, storyId, revision, compiledArtifactSha256, targetFormatVersion, runtime,
    steps, path, savedAtStep, variables, variablesChangedBeforeSave, migratedFrom, migrationNote } = options || {};
  if (!story || typeof story.state?.ToJson !== 'function') throw new SaveEnvelopeError('SAVE_ENVELOPE_STATE_INVALID', 'story with state.ToJson() is required');
  requireText(storyId, 'SAVE_ENVELOPE_SCHEMA_INVALID', 'story_id', 80);
  if (!Number.isInteger(revision) || revision < 1) throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'revision must be a positive integer');
  requireDigest(compiledArtifactSha256, 'compiled_artifact_sha256');
  requireText(targetFormatVersion, 'SAVE_ENVELOPE_SCHEMA_INVALID', 'target_format_version', 40);
  requireRuntime(runtime, 'SAVE_ENVELOPE_SCHEMA_INVALID', true);
  const stateJson = story.state.ToJson();
  if (typeof stateJson !== 'string' || !stateJson) throw new SaveEnvelopeError('SAVE_ENVELOPE_STATE_INVALID', 'state.ToJson() returned nothing');
  if (new TextEncoder().encode(stateJson).length > SAVE_ENVELOPE_MAX_BYTES) throw new SaveEnvelopeError('SAVE_ENVELOPE_STATE_TOO_LARGE', 'ink state exceeds the envelope size limit');
  const recordedSteps = Array.isArray(steps) ? steps.map(value => String(value)) : [];
  const recordedPath = Array.isArray(path) ? path.map(value => String(value)) : [];
  const recordedVariables = {};
  for (const [name, value] of Object.entries(variables || {})) {
    if (typeof name !== 'string' || !name) throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'variable name must be text');
    if (!SCALAR_TYPES.has(typeof value)) throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'variable ' + name + ' must be a strict boolean or integer scalar');
    if (typeof value === 'number' && !Number.isInteger(value)) throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'variable ' + name + ' must be an integer');
    recordedVariables[name] = value;
  }
  const envelope = {
    schema: SAVE_ENVELOPE_SCHEMA,
    format_version: SAVE_ENVELOPE_FORMAT_VERSION,
    binding: {
      story_id: storyId,
      revision,
      compiled_artifact_sha256: compiledArtifactSha256,
      target_format_version: targetFormatVersion,
      runtime: { name: runtime.name, version: runtime.version, ...(runtime.format ? { format: runtime.format } : {}) },
    },
    save: {
      state_json: stateJson,
      steps: recordedSteps,
      path: recordedPath,
      saved_at_step: Number.isInteger(savedAtStep) ? savedAtStep : recordedPath.length,
      saved_after_choice: recordedSteps.length >= 1,
      variables: recordedVariables,
      variables_changed_before_save: variablesChangedBeforeSave === true,
      created_by: 'poemseed-ink-player/1',
      ...(migratedFrom ? { migrated_from: String(migratedFrom), migration_note: String(migrationNote || '') } : {}),
    },
  };
  envelope.integrity = { algorithm: 'sha256', digest: computeEnvelopeDigest(envelope) };
  const bytes = JSON.stringify(envelope, null, 2) + '\n';
  return { envelope, bytes, sha256: sha256Hex(bytes), digest: envelope.integrity.digest };
}

function parseEnvelopeInput(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'loadSaveEnvelope expects { bytes } or { envelope }');
  if (input.envelope !== undefined) return { envelope: input.envelope };
  if (input.bytes !== undefined) return parseEnvelopeBytes(input.bytes);
  throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'loadSaveEnvelope expects { bytes } or { envelope }');
}

function parseEnvelopeBytes(bytes) {
  if (typeof bytes === 'string') bytes = new TextEncoder().encode(bytes);
  if (!(bytes instanceof Uint8Array)) throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'envelope bytes must be text or Uint8Array');
  if (bytes.length > SAVE_ENVELOPE_MAX_BYTES) throw new SaveEnvelopeError('SAVE_ENVELOPE_TOO_LARGE', 'envelope exceeds the size limit before parsing');
  let text;
  try { text = new TextDecoder('utf-8', { fatal: true }).decode(bytes); }
  catch (error) { throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'envelope is not valid UTF-8'); }
  try { return { envelope: JSON.parse(text), text }; }
  catch (error) { throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'envelope is not valid JSON'); }
}

/** Validate + bind + restore one save envelope; throws typed errors on any mismatch. */
export function loadSaveEnvelope(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'loadSaveEnvelope expects { bytes, story, expected } or { envelope, story, expected }');
  }
  // Trusted context first: no state is parsed or loaded without it.
  const expected = requireRestoreContext(input.expected);
  const { envelope } = parseEnvelopeInput(input);
  if (!envelope || typeof envelope !== 'object' || Array.isArray(envelope)) throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'envelope must be a JSON object');
  if (envelope.schema !== SAVE_ENVELOPE_SCHEMA) {
    if (looksLikeLegacyInkState(envelope)) throw new SaveEnvelopeError('LEGACY_SAVE_ENVELOPE_REQUIRED', 'unbound legacy Ink state is not trusted; migrate it explicitly with an artifact binding', { legacy_policy: SAVE_ENVELOPE_LEGACY_POLICY });
    throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'unsupported save envelope schema: ' + String(envelope.schema));
  }
  if (envelope.format_version !== SAVE_ENVELOPE_FORMAT_VERSION) throw new SaveEnvelopeError('SAVE_ENVELOPE_FORMAT_MISMATCH', 'envelope format ' + String(envelope.format_version) + ' is not supported');
  const binding = envelope.binding, save = envelope.save, integrity = envelope.integrity;
  if (!binding || typeof binding !== 'object') throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'binding is required');
  if (!save || typeof save !== 'object') throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'save payload is required');
  if (!integrity || integrity.algorithm !== 'sha256' || !HEX64.test(String(integrity.digest))) throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'integrity record is invalid');
  requireText(binding.story_id, 'SAVE_ENVELOPE_SCHEMA_INVALID', 'binding.story_id', 80);
  if (!Number.isInteger(binding.revision) || binding.revision < 1) throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'binding.revision must be a positive integer');
  requireDigest(binding.compiled_artifact_sha256, 'binding.compiled_artifact_sha256');
  requireText(binding.target_format_version, 'SAVE_ENVELOPE_SCHEMA_INVALID', 'binding.target_format_version', 40);
  requireRuntime(binding.runtime, 'SAVE_ENVELOPE_SCHEMA_INVALID', true);
  if (typeof save.state_json !== 'string' || !save.state_json) throw new SaveEnvelopeError('SAVE_ENVELOPE_STATE_INVALID', 'save.state_json is required');
  if (new TextEncoder().encode(save.state_json).length > SAVE_ENVELOPE_MAX_BYTES) throw new SaveEnvelopeError('SAVE_ENVELOPE_STATE_TOO_LARGE', 'state_json exceeds the size limit');
  if (typeof save.saved_after_choice !== 'boolean') throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'save.saved_after_choice is required');
  if (typeof save.variables_changed_before_save !== 'boolean') throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'save.variables_changed_before_save is required');
  if (!save.variables || typeof save.variables !== 'object' || Array.isArray(save.variables)) throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'save.variables must be an object');
  for (const [name, value] of Object.entries(save.variables)) {
    if (!SCALAR_TYPES.has(typeof value) || (typeof value === 'number' && !Number.isInteger(value))) throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'save.variables.' + name + ' must be a strict boolean or integer');
  }
  if (!Array.isArray(save.steps) || !Array.isArray(save.path)) throw new SaveEnvelopeError('SAVE_ENVELOPE_SCHEMA_INVALID', 'save.steps and save.path must be arrays');
  const digest = computeEnvelopeDigest(envelope);
  if (digest !== integrity.digest) throw new SaveEnvelopeError('SAVE_ENVELOPE_INTEGRITY_INVALID', 'envelope content does not match its integrity digest', { expected: digest, recorded: integrity.digest });
  if (binding.story_id !== expected.storyId) throw new SaveEnvelopeError('SAVE_ENVELOPE_STORY_MISMATCH', 'save belongs to story ' + binding.story_id + ', expected ' + expected.storyId);
  if (binding.revision !== expected.revision) throw new SaveEnvelopeError('SAVE_ENVELOPE_REVISION_MISMATCH', 'save belongs to revision ' + binding.revision + ', expected ' + expected.revision);
  if (binding.compiled_artifact_sha256 !== expected.compiledArtifactSha256) throw new SaveEnvelopeError('SAVE_ENVELOPE_ARTIFACT_MISMATCH', 'save was created for compiled artifact ' + binding.compiled_artifact_sha256 + ', current artifact is ' + expected.compiledArtifactSha256);
  if (binding.target_format_version !== expected.targetFormatVersion) throw new SaveEnvelopeError('SAVE_ENVELOPE_FORMAT_MISMATCH', 'save target format ' + binding.target_format_version + ' != expected ' + expected.targetFormatVersion);
  if (binding.runtime.name !== expected.runtime.name) throw new SaveEnvelopeError('SAVE_ENVELOPE_RUNTIME_MISMATCH', 'save runtime ' + binding.runtime.name + ' != expected ' + expected.runtime.name);
  if (binding.runtime.version !== expected.runtime.version) throw new SaveEnvelopeError('SAVE_ENVELOPE_RUNTIME_MISMATCH', 'save runtime version ' + binding.runtime.version + ' != expected ' + expected.runtime.version);
  if ((binding.runtime.format || '') !== expected.runtime.format) throw new SaveEnvelopeError('SAVE_ENVELOPE_RUNTIME_MISMATCH', 'save runtime format ' + String(binding.runtime.format) + ' != expected ' + expected.runtime.format);
  const story = input.story;
  if (!story || typeof story.state?.LoadJson !== 'function') throw new SaveEnvelopeError('SAVE_ENVELOPE_STATE_INVALID', 'story with state.LoadJson() is required');
  try { story.state.LoadJson(save.state_json); }
  catch (error) { throw new SaveEnvelopeError('SAVE_ENVELOPE_STATE_INVALID', 'ink state could not be restored: ' + String(error && error.message ? error.message : error)); }
  for (const [name, value] of Object.entries(save.variables)) {
    const observed = story.variablesState.$(name);
    if (observed !== value) throw new SaveEnvelopeError('SAVE_ENVELOPE_STATE_INVALID', 'restored variable ' + name + ' is ' + String(observed) + ', envelope expected ' + String(value));
  }
  return {
    ok: true,
    envelope,
    story,
    binding: envelope.binding,
    steps: save.steps,
    path: save.path,
    saved_at_step: Number.isInteger(save.saved_at_step) ? save.saved_at_step : save.path.length,
    saved_after_choice: save.saved_after_choice,
    variables_changed_before_save: save.variables_changed_before_save,
    variables: save.variables,
  };
}

/** Explicit migration for an unbound legacy state; caller must supply the binding. */
export function migrateLegacySaveEnvelope(input) {
  const { legacyStateJson, storyId, revision, compiledArtifactSha256, targetFormatVersion, runtime, steps, path, variables } = input || {};
  if (typeof legacyStateJson !== 'string' || !legacyStateJson) throw new SaveEnvelopeError('LEGACY_SAVE_INVALID', 'legacy state JSON is required');
  const fake = { state: { ToJson: () => legacyStateJson } };
  return createSaveEnvelope({ story: fake, storyId, revision, compiledArtifactSha256, targetFormatVersion, runtime,
    steps, path, savedAtStep: Array.isArray(path) ? path.length : 0, variables, variablesChangedBeforeSave: true,
    migratedFrom: 'UNBOUND_LEGACY_INK_STATE',
    migrationNote: 'Legacy unbound state was migrated with an explicit caller-supplied binding. It is labelled as migrated, never as system-verified execution.' });
}
