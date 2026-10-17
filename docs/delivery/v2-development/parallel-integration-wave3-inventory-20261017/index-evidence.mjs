import fs from 'node:fs';
import crypto from 'node:crypto';
const d = 'docs/delivery/v2-development/parallel-integration-wave3-inventory-20261017';
const hash = b => crypto.createHash('sha256').update(b).digest('hex');
const files = fs.readdirSync(d).filter(p => p !== 'evidence-files.json').sort().map(path => {
  const bytes = fs.readFileSync(d + '/' + path);
  return {path, bytes: bytes.length, sha256: hash(bytes)};
});
const binding = JSON.parse(fs.readFileSync(d + '/compact-source-binding.json'));
const externalPaths = [
  '.runtime/parallel-integration-wave3-inventory/candidate-manifest-v2.json.gz',
  '/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/setup-receipt.json',
  binding.prior_raw_inventory.path,
  'docs/delivery/v2-development/parallel-integration-wave3-20261017/complete-index.json',
  'docs/delivery/v2-development/parallel-integration-wave3-20261017/integration-report.md',
  'docs/delivery/v2-development/parallel-integration-wave3-20261017/independent-terminal-audit-r1.json',
  'docs/delivery/v2-development/parallel-integration-wave3-canvas-supplement-20261017/complete-index.json',
  'docs/delivery/v2-development/parallel-integration-wave3-canvas-supplement-20261017/report.md',
  ...['review', 'candidate', 'confirmation'].flatMap(phase => ['json', 'log'].map(ext =>
    'docs/delivery/v2-development/wave3-integration-inventory-' + phase + '-origin.' + ext))
];
const external_dependencies = externalPaths.map(path => {
  const bytes = fs.readFileSync(path);
  return {path, bytes: bytes.length, sha256: hash(bytes)};
});
fs.writeFileSync(d + '/evidence-files.json', JSON.stringify({files, external_dependencies}, null, 2) + '\n');
