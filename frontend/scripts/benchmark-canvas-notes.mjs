/** Offline bounded note authoring/projection measurement. No browser or execution graph. */
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { performance } from 'node:perf_hooks';
import ts from 'typescript';
const sources = new Map(), urls = new Map();
function moduleUrl(name) {
  if (urls.has(name)) return urls.get(name);
  const source = readFileSync(new URL(`../src/creative/${name}.ts`, import.meta.url), 'utf8');
  sources.set(name, source);
  const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
    .replace(/from ['"]\.\/([^'"]+)['"]/g, (_match, dependency) => `from '${moduleUrl(dependency)}'`);
  const url = `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`; urls.set(name, url); return url;
}
const { visibleGraphNotes, withGraphNotes, graphNoteDefinitionBytes } = await import(moduleUrl('graphCanvasNotes'));
const notes = Array.from({ length: 128 }, (_, i) => ({ id: `note_${i}`, text: `Scene ${i}: verify continuity, revise transitions, keep human review. 🎬`, position: { x: (i % 16) * 500, y: Math.floor(i / 16) * 300 } }));
const definition = withGraphNotes({ schema_version: 1, title: 'Independent display notes', nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } }, notes);
if (!definition) throw new Error('Bounded authoring rejected fixture');
const durations = [], counts = [], heapSamples = [];
for (let i = 0; i < 1200; i++) {
  const camera = { x: -(i % 16) * 500, y: -(i % 8) * 300, zoom: [0.35, 1, 2.5][i % 3] };
  const start = performance.now(), shown = visibleGraphNotes(notes, camera, { width: 1280, height: 720 }, null);
  if (i >= 200) { durations.push(performance.now() - start); counts.push(shown.length); }
}
if (global.gc) for (let i = 0; i < 5; i++) {
  global.gc(); const before = process.memoryUsage().heapUsed;
  const copy = structuredClone(definition); global.gc(); heapSamples.push(process.memoryUsage().heapUsed - before);
  if (copy.presentation.notes.length !== 128) throw new Error('Lost notes');
}
durations.sort((a,b) => a-b);
console.log(JSON.stringify({ timestamp: new Date().toISOString(), kind: 'bounded-note-Node-only-microbenchmark', runtime: process.version,
  persisted_shape_notes: 128, execution_nodes: 0, execution_edges: 0, samples: durations.length,
  utf8_json_bytes: Buffer.byteLength(JSON.stringify(definition)), conservative_authoring_bytes: graphNoteDefinitionBytes(definition),
  unicode_text_total: notes.reduce((sum, n) => sum + Array.from(n.text).length, 0),
  projection_ms_median: durations[500], projection_ms_p95: durations[950], projection_ms_max: durations.at(-1),
  mounted_projection_max: Math.max(...counts), heap_delta_bytes_samples: heapSamples,
  browser_fps: 'NOT_RUN', browser_memory: 'NOT_RUN', thousand_persisted_objects: 'PARTIAL: capped at 128 notes under original 96000-byte owner limit',
  caveat: 'Includes creating a disposable index and projection; excludes React/DOM/paint. Node heap deltas are noisy, not browser acceptance. Directory has at most 128 options.',
  source_sha256: Object.fromEntries([...sources].map(([name, code]) => [`${name}.ts`, createHash('sha256').update(code).digest('hex')])) }, null, 2));
