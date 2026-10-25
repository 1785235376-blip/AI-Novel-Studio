// [HERMIA-FE-20261025 M5] Stateful MOCK backend (evidence kind: mock). Writes are only accepted when the harness has
// explicitly armed that exact write (allowWrite) right before the user-confirm click; any other non-GET is blocked + logged.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
const canonical = v => Array.isArray(v) ? '[' + v.map(canonical).join(',') + ']' : v !== null && typeof v === 'object'
  ? '{' + Object.keys(v).sort().map(k => JSON.stringify(k) + ':' + canonical(v[k])).join(',') + '}' : JSON.stringify(v);
const hash = s => createHash('sha256').update(s).digest('hex');
export function createBackend() {
  const d = JSON.parse(readFileSync(new URL('./mockData.json', import.meta.url), 'utf8'));
  const st = {mode: 'ok', armed: new Set(), log: [], blocked: [], canvas: structuredClone(d.raw.canvas), hist: [structuredClone(d.raw.canvas)], jobs: structuredClone(d.jobs)};
  const P = d.P, prod = `/api/projects/${P}/studio/production`, cv = `/api/projects/${P}/studio/canvas-views`;
  const historyBody = () => ({project_id: P, scope: st.canvas.scope, id: st.canvas.id, incarnation: d.raw.history.incarnation, current_version: st.canvas.version,
    current_definition_digest: st.canvas.definition_digest, restore_policy: 'CURRENT_METADATA_ONLY', execution_authority: false, binary_content_verified: false,
    items: st.hist.map(r => ({version: r.version, definition: r.definition, definition_digest: r.definition_digest, reference_states: r.reference_states,
      created_at: r.created_at, updated_at: r.updated_at, can_restore: r.version !== st.canvas.version}))});
  const commit = def => { const r = {...structuredClone(st.canvas), version: st.canvas.version + 1, definition: def, definition_digest: hash(canonical(def))};
    st.canvas = r; st.hist.push(structuredClone(r)); return r; };
  function handle(method, url, body) {
    const u = new URL(url, 'http://x'), p = u.pathname; st.log.push(`${method} ${p}${u.search}`);
    if (method !== 'GET') {
      const key = `${method} ${p}`;
      if (!st.armed.has(key)) { st.blocked.push(key); return [409, {detail: 'M5 harness: unconfirmed write blocked'}]; }
      st.armed.delete(key);
      if (p === `${cv}/${st.canvas.id}` && method === 'PUT') return [200, commit(body.definition)];
      if (p === `${cv}/${st.canvas.id}/restore`) { const t = st.hist.find(h => h.version === body.restore_version); return [200, commit(structuredClone(t.definition))]; }
      if (p === `${prod}/preview` && method === 'POST') { // MOCK preview: echoes the command, never calls any model
        const job = st.jobs.find(j => j.operation_id === body.operation_id) ?? st.jobs[0];
        return [200, {contract: 'studio-production-preview/1', novel_id: P, branch_id: st.canvas.scope?.branch_id ?? 'b1', request_id: body.request_id, operation_id: body.operation_id,
          preview_digest: hash('pv' + canonical(body)), request_digest: hash('rq' + canonical(body)), command: structuredClone(body),
          provider: {provider_id: body.provider_id ?? 'local', model_id: body.model_id ?? 'mock', local: true, route_digest: hash('route')}, sources: [],
          execution_recipe: structuredClone(job.execution_recipe), product_acceptance: 'LOCAL_REQUIRED', execution_available: true, automatic_dispatch: false,
          output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW'}];
      }
      return [404, {detail: 'nf'}];
    }
    if (st.mode === 'revoked' && p.startsWith('/api/') && p !== '/api/novels') return [403, {detail: 'forbidden', code: 'FORBIDDEN'}];
    if (st.mode === 'unknown' && (p.startsWith(prod) || p.includes('/experimental/workspace/tasks'))) return [503, {detail: 'unavailable'}];
    if (p === '/api/novels') return [200, st.mode === 'gone' ? d.novels.slice(1) : d.novels];
    if (/^\/api\/novels\/[^/]+\/chapters$/.test(p)) return [200, []];
    if (p.endsWith('/bootstrap') && p.startsWith('/api/collaboration/')) return [200, d.bootstrap];
    if (p === `/api/novels/${P}/experimental/workspace/tasks`) return [200, d.tasks];
    if (p === `${prod}/jobs`) return [200, {items: st.jobs}];
    const m = p.match(new RegExp(`^${prod}/jobs/([a-z]+)/([^/]+)$`)); if (m) { const j = st.jobs.find(x => x.owner === m[1] && x.id === decodeURIComponent(m[2])); return j ? [200, j] : [404, {detail: 'nf'}]; }
    if (p === `${prod}/providers`) return [200, {items: d.providers, health_probed: false, credentials_read: false}];
    if (p === `${cv}/${st.canvas.id}`) return [200, st.canvas];
    if (p === `${cv}/${st.canvas.id}/history`) return [200, historyBody()];
    if (p === `/api/projects/${P}/studio/assets`) return [200, {items: d.assets}];
    return [404, {detail: 'nf'}];
  }
  return {d, st, handle, arm: k => st.armed.add(k)};
}
