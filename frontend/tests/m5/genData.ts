// [HERMIA-FE-20261025 M5] Evidence kind: mock backend built from the repo's SYNTHETIC wire fixtures (no real provider, no model inference).
import {writeFileSync} from 'node:fs';
import audio from '../../src/creative/canvasAudioTrimTask.testFixtures';
import {tasksResponse, projectedTask} from '../../src/taskcenter/taskCenterFixtures';
const A: any = structuredClone(audio);
const P = A.canvas.project_id as string;
export const SCOPE = {workspaceId: 'ws1', projectId: P, storylineId: 's1', branchId: 'b1'};
const collab = {mode: 'collaboration', novel_id: P, workspace_id: 'ws1', storyline_id: 's1', branch_id: 'b1'};
const fix = (v: any): any => Array.isArray(v) ? v.map(fix) : v && typeof v === 'object'
  ? (v.mode === 'local' && v.novel_id === P ? {...collab} : Object.fromEntries(Object.entries(v).map(([k, x]) => [k, k === 'branch_id' && x === null ? 'b1' : fix(x)]))) : v;
const D = fix(A);
const digest = 'ab'.repeat(32);
// second job: an image job with a provider so the param editor has a real (synthetic) provider description. Never executed.
const cmd = {operation_id: 'm5.image.t2i', request_id: 'm5-param-request', provider_id: 'local', model_id: 'synthetic-model', prompt: '雾港清晨（模拟）', parameters: {},
  license_note: 'synthetic test', allow_cloud: false, source_snapshots: []};
const provider = {operation_id: 'm5.image.t2i', provider_id: 'local', model_id: 'synthetic-model', local: true, route_digest: digest, capability: 'IMAGE', supported_parameters: [],
  readiness: 'CONFIGURED_NOT_VERIFIED', image_capabilities: {recipe_id: 'comfy-sd-checkpoint-v1', reference_limit: 1, reference_semantics: 'SINGLE_IMAGE_INITIALIZATION', mask_semantics: null, structural_only: true, inference_verified: false}};
const imageJob = {contract: 'studio-production-job/1', id: 'm5-image-job', branch_id: 'b1', version: 2, request_id: cmd.request_id, request_digest: digest, receipt_digest: null,
  timeline_snapshot: null, product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false, remote_compute_may_continue: false, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
  novel_id: P, owner: 'image', operation_id: 'm5.image.t2i', status: 'AWAITING_REVIEW', provider: {local: true, provider_id: 'local', model_id: 'synthetic-model', route_digest: digest},
  command: cmd, sources: cmd.source_snapshots, execution_recipe: {contract: 'studio-execution-recipe/1', operation_id: 'm5.image.t2i', recipe_digest: digest, automatic_fallback: false, adapter: 'COMFYUI_BUILTIN_IMAGE', image_recipe_id: 'comfy-sd-checkpoint-v1', reference_weights: [], reference_semantics: 'WEIGHTED_PIXEL_INITIALIZATION', mask_semantics: null},
  output_candidate: null, approved_asset_version: null};
const out = {P, SCOPE, bootstrap: {actor: {actor_id: 'u-m5', session_id: 'sess-m5', client_id: 'c-m5'}, scope: {workspace_id: 'ws1', project_id: P, storyline_id: 's1', branch_id: 'b1'}, capabilities: {}},
  novels: [{id: P, title: '演示 A（模拟）', genre: '', chapter_count: 0, word_count: 0, status: 'Writing'}, {id: 'proj-b', title: '演示 B（模拟）', genre: '', chapter_count: 0, word_count: 0, status: 'Writing'}],
  tasks: tasksResponse({items: [projectedTask()]}), jobs: [D.approved, imageJob], providers: [provider],
  canvas: D.returned, history: D.history, assets: [D.source, D.output], restored: D.restored, raw: D};
writeFileSync(new URL('./mockData.json', import.meta.url), JSON.stringify(out, null, 1));
console.log('wrote', P, Object.keys(D));
