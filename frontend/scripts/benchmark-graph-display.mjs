/** Offline geometry microbenchmark. No backend graph, DOM, browser or model calls. */
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { performance } from 'node:perf_hooks';
import ts from 'typescript';
const source = name => readFileSync(new URL(`../src/creative/${name}.ts`, import.meta.url), 'utf8');
const moduleUrl = value => `data:text/javascript;base64,${Buffer.from(value).toString('base64')}`;
const compile = value => ts.transpileModule(value, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const geometry = source('graphCanvasGeometry'), presentation = source('graphCanvasPresentation');
const { createGraphDisplayIndex, projectGraphDisplay } = await import(moduleUrl(compile(presentation).replace("'./graphCanvasGeometry'", JSON.stringify(moduleUrl(compile(geometry))))));
const definitions = [{ id: 'text_input', inputs: [{ id: 'in', type: 'TEXT' }], outputs: [{ id: 'out', type: 'TEXT' }] }];
const percentile = (values, fraction) => [...values].sort((a, b) => a - b)[Math.floor((values.length - 1) * fraction)];
const results = [];
for (const count of [1000, 10000]) {
  // Pure display DTOs deliberately omit schema/version/parameters/enabled/run data.
  const columns = 40;
  const nodes = Array.from({ length: count }, (_, id) => ({ id: String(id), definition_id: 'text_input', position: { x: (id % columns) * 500, y: Math.floor(id / columns) * 300 } }));
  const edges = nodes.filter((_, id) => id % columns !== columns - 1).map(node => ({ id: `e${node.id}`, source_node_id: node.id, target_node_id: String(Number(node.id) + 1), source_port: 'out', target_port: 'in' }));
  const started = performance.now();
  const index = createGraphDisplayIndex(nodes, edges, definitions);
  const indexMilliseconds = performance.now() - started;
  const size = { width: 1280, height: 720 };
  const home = projectGraphDisplay(index, { x: 0, y: 0, zoom: 1 }, size);
  for (let i = 0; i < 100; i++) projectGraphDisplay(index, { x: -i * 20, y: -i * 10, zoom: 1 }, size);
  const durations = [], nodeCounts = [], edgeCounts = [];
  for (let i = 0; i < 1000; i++) {
    const zoom = [0.35, 0.5, 1, 2.5][i % 4];
    const viewport = { x: -(i % columns) * 500 * zoom, y: -(i % Math.ceil(count / columns)) * 300 * zoom, zoom };
    const start = performance.now(), result = projectGraphDisplay(index, viewport, size);
    durations.push(performance.now() - start); nodeCounts.push(result.nodeIds.size); edgeCounts.push(result.edges.length);
  }
  // Isolated retained-index heap deltas are runtime/GC observations, not browser
  // memory. Report every sample including noise; no heap/FPS acceptance threshold.
  const heapSamples = [];
  const sampleRetainedIndex = () => {
    global.gc(); const before = process.memoryUsage().heapUsed;
    const retained = createGraphDisplayIndex(nodes, edges, definitions);
    global.gc(); const delta = process.memoryUsage().heapUsed - before;
    if (retained.cards.length !== count) throw new Error('Index lost display objects');
    return delta;
  };
  if (global.gc) for (let i = 0; i < 5; i++) heapSamples.push(sampleRetainedIndex());
  results.push({ display_nodes: count, display_edges: edges.length, index_ms: indexMilliseconds,
    viewport_samples: durations.length, projection_ms_median: percentile(durations, 0.5), projection_ms_p95: percentile(durations, 0.95), projection_ms_max: Math.max(...durations),
    home_rendered_cards: home.nodeIds.size, home_rendered_edges: home.edges.length, max_rendered_cards: Math.max(...nodeCounts), max_rendered_edges: Math.max(...edgeCounts),
    retained_index_heap_delta_bytes_samples: heapSamples, accessibility_directory_options: count });
}
console.log(JSON.stringify({ kind: 'offline-display-geometry-microbenchmark', browser_fps: 'NOT_RUN', browser_memory: 'NOT_RUN', backend_execution: 'NOT_RUN',
  note: 'Timing covers projection only, not React/DOM/native select/paint. Heap deltas are noisy Node GC observations; no browser-memory claim. Selected/focused/connection retention can intentionally render all cards.',
  runtime: process.version, platform: process.platform, timestamp: new Date().toISOString(),
  source_sha256: Object.fromEntries([['graphCanvasGeometry.ts', geometry], ['graphCanvasPresentation.ts', presentation]].map(([name, code]) => [name, createHash('sha256').update(code).digest('hex')])), results }, null, 2));
