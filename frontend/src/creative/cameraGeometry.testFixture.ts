import { emptyCameraGrammar, type CameraGrammar } from './cameraGrammar';
import type { DirectorCameraEvidence } from '../director/directorCameraEvidence';

export const cameraGeometry = (y = 2): CameraGrammar => ({ ...emptyCameraGrammar(), coordinate_system: 'room-metres',
  character_positions: { a: { x: 0, y: 0 }, b: { x: 4, y: 0 } }, axis: ['a', 'b'], camera_position: { x: 2, y } });
export function cameraEvidence(): DirectorCameraEvidence {
  return { contract: 'studio-director-authored-camera-evidence/1', schema_version: 1,
    evidence_kind: 'SUPPLEMENTARY_AUTHORED_GEOMETRY', model_called: false, visual_analysis: false, auto_modify: false,
    document_snapshot: { id: 'doc-1', version: 3, digest: 'a'.repeat(64) }, source_field: 'director_notes',
    rows: [1, 2].map(n => ({ id: `note-${n}`, number: n, scene_id: 'scene-1', geometry_authored: true, camera_grammar: cameraGeometry(n === 1 ? 2 : -2) })),
    findings: [{ kind: 'AXIS', state: 'AXIS_CROSSING', from_shot_id: 'note-1', to_shot_id: 'note-2', cross_products: ['8', '-8'], message: '明确几何显示越轴；这是可覆盖的建议。' },
      ...[1, 2].map(n => ({ kind: 'SCREEN_DIRECTION' as const, state: 'INSUFFICIENT_EVIDENCE' as const, shot_id: `note-${n}`, message: '信息不足：未提供可计算的移动轨迹、机位或明确屏幕方向。' }))] };
}
