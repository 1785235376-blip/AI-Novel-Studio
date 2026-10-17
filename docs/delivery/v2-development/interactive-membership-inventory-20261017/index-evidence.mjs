import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import childProcess from 'node:child_process';
const root = process.cwd();
const dir = 'docs/delivery/v2-development';
const indexPath = `${dir}/interactive-membership-evidence-index.json`;
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(path.join(root, file))).digest('hex');
const receiptNames = ['file-origin', 'file', 'ui', 'type', 'build', 'tokens', 'independent-origin', 'independent-file', 'independent-ui'];
const receiptPaths = receiptNames.map(name => `${dir}/interactive-membership-${name}-r1.json`);
const baseline = JSON.parse(fs.readFileSync(path.join(root, receiptPaths[0]), 'utf8')).source_sha256;
const compare = (a, b) => JSON.stringify(Object.entries(a).sort()) === JSON.stringify(Object.entries(b).sort());
const finalReceipts = receiptPaths.map(file => {
  const value = JSON.parse(fs.readFileSync(path.join(root, file), 'utf8'));
  const mismatches = Object.entries(value.source_sha256).filter(([file, digest]) => !fs.existsSync(path.join(root, file)) || hash(file) !== digest).map(([file]) => file);
  const record = { path: file, sha256: hash(file), status: value.status, exit_code: value.exit_code, source_count: Object.keys(value.source_sha256).length, before_after_equal: compare(value.source_sha256_before, value.source_sha256), sources_changed_during_check: value.sources_changed_during_check, source_maps_equal_final: compare(value.source_sha256, baseline), current_source_mismatches: mismatches, log: value.log, log_hash_matches: hash(value.log) === value.log_sha256 };
  if (record.status !== 'PASS' || record.exit_code !== 0 || !record.before_after_equal || record.sources_changed_during_check || !record.source_maps_equal_final || mismatches.length || !record.log_hash_matches) throw new Error(`Invalid final evidence ${file}`);
  return record;
});
const files = [];
const walk = directory => { for (const item of fs.readdirSync(path.join(root, directory), { withFileTypes: true })) { const relative = `${directory}/${item.name}`; if (item.isDirectory()) walk(relative); else files.push(relative); } };
for (const item of fs.readdirSync(path.join(root, dir), { withFileTypes: true })) {
  if (!item.name.startsWith('interactive-membership-')) continue;
  const relative = `${dir}/${item.name}`;
  if (item.isDirectory()) walk(relative); else if (relative !== indexPath) files.push(relative);
}
files.push('docs/INTERACTIVE_MEMBERSHIP_HANDOFF.md');
const sources = ['frontend/src/experimental/InteractiveStoryPanel.tsx', 'frontend/src/experimental/InteractiveStoryPanel.membership.test.tsx', 'tests/test_interactive_membership_handoff.py'];
const result = { generated_utc: new Date().toISOString(), base_head: childProcess.execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(), branch: childProcess.execFileSync('git', ['branch', '--show-current'], { encoding: 'utf8' }).trim(), summary: { primary_file: { passed: 83, postgres_deselected: 45 }, independent_file: { passed: 83, postgres_deselected: 45 }, primary_ui: { suites: 4, passed: 48, new_tests: 25 }, independent_ui: { suites: 4, passed: 48 }, forced_typescript: 'PASS', production_build: 'PASS', token_guard: 'PASS (52 files)', final_source_count: Object.keys(baseline).length, all_nine_final_maps_equal_current: true, real_browser_visual_geometry_accessibility: 'NOT_RUN', native_desktop: 'NOT_RUN', target_engine: 'NOT_RUN', postgres: 'NOT_RUN', build_warning: 'Large chunks', sparse_history: 'All code/tests present; historical docs/delivery excluded; no claim to validate absent historical evidence' }, source_files: sources.map(file => ({ path: file, sha256: hash(file) })), final_receipts: finalReceipts, evidence_files: [...new Set(files)].sort().map(file => ({ path: file, bytes: fs.statSync(path.join(root, file)).size, sha256: hash(file) })), index_self_hash: 'Not included to avoid recursive self-hash' };
fs.writeFileSync(path.join(root, indexPath), `${JSON.stringify(result, null, 2)}\n`);
console.log(JSON.stringify({ index: indexPath, receipts: finalReceipts.length, source_count: Object.keys(baseline).length, evidence_files: result.evidence_files.length, current_sources_verified: true }));
