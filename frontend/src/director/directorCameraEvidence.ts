import { validCameraGrammar, type CameraGrammar } from '../creative/cameraGrammar';
import { checkedPlanningSnapshot, type PlanningSnapshot } from '../creative/studioProductionGraphContract';

export type CameraFinding = {
  kind: 'AXIS' | 'SCREEN_DIRECTION' | 'REPEATED_FRAMING' | 'SHOT_RHYTHM' | 'CONTINUITY';
  state: 'INSUFFICIENT_EVIDENCE' | 'INTENTIONAL_OVERRIDE' | 'AXIS_CROSSING' | 'SAME_SIDE' | 'CONSISTENT' | 'DIRECTION_MISMATCH' | 'REVIEW_SUGGESTION';
  message: string; shot_id?: string; from_shot_id?: string; to_shot_id?: string;
  cross_products?: string[]; computed?: string; projection?: string;
  evidence?: { fields?: { shot_size: string; camera_angle: string; camera_motion: string };
    estimated_duration_seconds?: number[]; review_threshold_ratio?: 3; declared_screen_directions?: string[] };
};
export type DirectorCameraEvidence = {
  contract: 'studio-director-authored-camera-evidence/1'; schema_version: 1;
  evidence_kind: 'SUPPLEMENTARY_AUTHORED_GEOMETRY'; model_called: false; visual_analysis: false; auto_modify: false;
  document_snapshot: PlanningSnapshot; source_field: 'director_notes' | 'shots';
  rows: { id: string; number: number; scene_id: string; geometry_authored: boolean; camera_grammar: CameraGrammar | null }[];
  findings: CameraFinding[];
};
export function checkedDirectorCameraEvidence(value: unknown, document: { id: string; version: number; mode: string }, invalid: () => never): DirectorCameraEvidence {
  const record = (v: unknown): Record<string, unknown> => { if (!v || typeof v !== 'object' || Array.isArray(v)) invalid(); return v as Record<string, unknown>; };
  const closed = (v: Record<string, unknown>, keys: string[]) => { if (Object.keys(v).length !== keys.length || keys.some(k => !Object.hasOwn(v, k))) invalid(); };
  const text = (v: unknown, max = 240): string => { if (typeof v !== 'string' || !v.trim() || Array.from(v).length > max) invalid(); return v as string; };
  const array = (v: unknown, max: number): unknown[] => { if (!Array.isArray(v) || v.length > max) invalid(); return v as unknown[]; };
  const literal = (v: unknown, allowed: string[]) => { if (typeof v !== 'string' || !allowed.includes(v)) invalid(); };
  const rational = (v: unknown) => { if (!/^-?\d+(?:\/[1-9]\d*)?$/.test(text(v, 4000))) invalid(); };
  const row = record(value);
  closed(row, ['contract', 'schema_version', 'evidence_kind', 'model_called', 'visual_analysis', 'auto_modify', 'document_snapshot', 'source_field', 'rows', 'findings']);
  if (row.contract !== 'studio-director-authored-camera-evidence/1' || row.schema_version !== 1 || row.evidence_kind !== 'SUPPLEMENTARY_AUTHORED_GEOMETRY'
    || row.model_called !== false || row.visual_analysis !== false || row.auto_modify !== false
    || row.source_field !== (document.mode === 'DIRECTOR' ? 'director_notes' : 'shots')) invalid();
  const pin = checkedPlanningSnapshot(row.document_snapshot);
  if (pin.id !== document.id || pin.version !== document.version) invalid();
  const rows = array(row.rows, 200).map(v => {
    const r = record(v); closed(r, ['id', 'number', 'scene_id', 'geometry_authored', 'camera_grammar']);
    text(r.id); text(r.scene_id);
    if (!Number.isSafeInteger(r.number) || Number(r.number) < 1 || Number(r.number) > 10000 || typeof r.geometry_authored !== 'boolean'
      || r.geometry_authored !== (r.camera_grammar !== null) || r.camera_grammar !== null && !validCameraGrammar(r.camera_grammar)) invalid();
    return r as DirectorCameraEvidence['rows'][number];
  });
  if (!rows.some(r => r.geometry_authored) || new Set(rows.map(r => r.id)).size !== rows.length
    || rows.some((r, index) => index > 0 && r.number <= rows[index - 1].number)) invalid();
  const findings = array(row.findings, 1000).map(v => {
    const f = record(v); text(f.message, 4000);
    literal(f.kind, ['AXIS', 'SCREEN_DIRECTION', 'REPEATED_FRAMING', 'SHOT_RHYTHM', 'CONTINUITY']);
    if (f.kind === 'SCREEN_DIRECTION') {
      if (!rows.some(r => r.id === f.shot_id)) invalid();
      literal(f.state, ['INSUFFICIENT_EVIDENCE', 'CONSISTENT', 'DIRECTION_MISMATCH']);
      closed(f, ['kind', 'state', 'message', 'shot_id', ...(f.state === 'INSUFFICIENT_EVIDENCE' ? [] : ['computed', 'projection'])]);
      if (f.state !== 'INSUFFICIENT_EVIDENCE') { literal(f.computed, ['LEFT_TO_RIGHT', 'RIGHT_TO_LEFT', 'STATIONARY']); rational(f.projection); }
    } else {
      const index = rows.findIndex(r => r.id === f.from_shot_id);
      if (index < 0 || rows[index + 1]?.id !== f.to_shot_id) invalid();
      const keys = ['kind', 'state', 'message', 'from_shot_id', 'to_shot_id'];
      if (f.kind === 'AXIS') {
        literal(f.state, ['INSUFFICIENT_EVIDENCE', 'INTENTIONAL_OVERRIDE', 'AXIS_CROSSING', 'SAME_SIDE']);
        closed(f, [...keys, ...(f.state === 'INSUFFICIENT_EVIDENCE' ? [] : ['cross_products'])]);
        if (f.state !== 'INSUFFICIENT_EVIDENCE') { const cross = array(f.cross_products, 2); if (cross.length !== 2 || rows[index].scene_id !== rows[index + 1].scene_id) invalid(); cross.forEach(rational); }
        if (f.state === 'INTENTIONAL_OVERRIDE' && (!rows[index + 1].camera_grammar?.intentional_axis_crossing || !rows[index + 1].camera_grammar?.override_reason.trim())) invalid();
      } else {
        closed(f, [...keys, 'evidence']);
        if (rows[index].scene_id !== rows[index + 1].scene_id) invalid();
        const e = record(f.evidence);
        if (f.kind === 'REPEATED_FRAMING') {
          literal(f.state, ['REVIEW_SUGGESTION', 'INTENTIONAL_OVERRIDE']); closed(e, ['fields']); const fields = record(e.fields);
          closed(fields, ['shot_size', 'camera_angle', 'camera_motion']); Object.values(fields).forEach(v => text(v, 80));
          if (f.state === 'INTENTIONAL_OVERRIDE' && !rows[index + 1].camera_grammar?.intentions.includes('JUMP_CUT')) invalid();
        } else if (f.kind === 'SHOT_RHYTHM') {
          if (f.state !== 'REVIEW_SUGGESTION') invalid(); closed(e, ['estimated_duration_seconds', 'review_threshold_ratio']);
          const durations = array(e.estimated_duration_seconds, 2);
          if (e.review_threshold_ratio !== 3 || durations.length !== 2 || durations.some(v => !Number.isSafeInteger(v) || Number(v) < 1 || Number(v) > 600)) invalid();
        } else {
          if (f.state !== 'REVIEW_SUGGESTION') invalid(); closed(e, ['declared_screen_directions']);
          const directions = array(e.declared_screen_directions, 2); if (directions.length !== 2) invalid(); directions.forEach(v => literal(v, ['LEFT_TO_RIGHT', 'RIGHT_TO_LEFT']));
        }
      }
    }
    return f as CameraFinding;
  });
  // Every original row and adjacent pair must have its primary geometry result.
  if (findings.filter(f => f.kind === 'AXIS').length !== Math.max(rows.length - 1, 0)
    || findings.filter(f => f.kind === 'SCREEN_DIRECTION').length !== rows.length
    || new Set(findings.map(f => [f.kind, f.shot_id, f.from_shot_id, f.to_shot_id].join('\0'))).size !== findings.length) invalid();
  return { ...row, document_snapshot: pin, rows, findings } as DirectorCameraEvidence;
}
