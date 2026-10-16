// Reproducible byte/gzip measurement. This is not a startup latency benchmark.
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
const [dist = 'dist', baselinePath, outputPath] = process.argv.slice(2);
const files = fs.readdirSync(path.join(dist, 'assets')).sort().map(file => {
  const bytes = fs.readFileSync(path.join(dist, 'assets', file));
  return { file, bytes: bytes.length, gzip_bytes: zlib.gzipSync(bytes).length };
});
function summarize(rows) {
  const group = pattern => {
    const selected = rows.filter(row => pattern.test(row.file));
    return { files: selected.map(row => row.file), bytes: selected.reduce((total, row) => total + row.bytes, 0), gzip_bytes: selected.reduce((total, row) => total + row.gzip_bytes, 0) };
  };
  return {
    html_bootstrap_js: group(/^(?:index|react-vendor|query-vendor)-.*\.js$/),
    html_bootstrap_css: group(/^index-.*\.css$/),
    app_route_js: group(/^App-.*\.js$/),
    app_route_css: group(/^App-.*\.css$/),
    tutor_deferred_js: group(/^LocalTutorIntegration-.*\.js$/),
    tutor_deferred_css: group(/^LocalTutorIntegration-.*\.css$/),
  };
}
const current = summarize(files);
const baseline = baselinePath ? summarize(JSON.parse(fs.readFileSync(baselinePath, 'utf8')).files) : undefined;
const comparison = baseline ? Object.fromEntries(Object.entries(current).map(([name, value]) => [name, { before: baseline[name], after: value, byte_delta: value.bytes - baseline[name].bytes, gzip_byte_delta: value.gzip_bytes - baseline[name].gzip_bytes }])) : undefined;
const result = { measurement: 'built file bytes and gzip bytes, not runtime startup timing', baseline_sha: baselinePath ? JSON.parse(fs.readFileSync(baselinePath, 'utf8')).baseline : undefined, files, current, comparison, startup_timing: 'NOT_RUN' };
const json = JSON.stringify(result, null, 2) + '\n';
if (outputPath) fs.writeFileSync(outputPath, json); else process.stdout.write(json);
