/**
 * UX-05 测试用合成回执。
 *
 * 这些对象**不是**真实模型验收证据：它们由既有 `phase4.file-api-storyboard.json`
 * 捕获改写而成，只用来固定本工作区的解码/呈现边界。每一处改写都保持内部一致
 * （版本针、摘要、身份都彼此对得上），否则原 owner 的解码器会（正确地）拒绝它。
 */
import { checkedStoryboardReceipt, checkedDirectorAdvice, type StoryboardReceipt } from '../creative/studioStoryboardContract';
import fixture from '../creative/fixtures/phase4.file-api-storyboard.json';

export const copy = <T,>(value: T): T => structuredClone(value);

export function storyboardReceipt(overrides: {
  approved?: boolean;
  documentVersion?: number;
  directorSource?: { id: string; version: number; digest: string } | null;
  shots?: (row: Record<string, unknown>) => void;
} = {}): StoryboardReceipt {
  const base = copy(fixture) as Record<string, unknown>;
  if (overrides.approved !== undefined) base.approved = overrides.approved;
  if (overrides.documentVersion !== undefined) {
    (base.document_snapshot as Record<string, unknown>).version = overrides.documentVersion;
  }
  if (overrides.directorSource) {
    base.director_sources = [{ ...overrides.directorSource }];
  }
  if (overrides.shots) for (const row of base.shots as Record<string, unknown>[]) overrides.shots(row);
  return checkedStoryboardReceipt(base);
}

/** 带正式视频绑定的合成回执（第二镜头）。 */
export function receiptWithVideo(): StoryboardReceipt {
  return storyboardReceipt({
    shots: row => {
      if (row.shot_id !== 'shot-2') return;
      row.video_result = {
        asset: { asset_id: 'video-asset', version: 1, digest: 'd'.repeat(64), kind: 'video' },
        source_shot: {
          document_snapshot: { ...(copy(fixture) as Record<string, unknown>).document_snapshot as Record<string, unknown> },
          shot_id: row.shot_id, shot_version: row.shot_version, shot_digest: row.shot_digest,
        },
        job: { id: 'video-job', version: 3, request_digest: 'e'.repeat(64), receipt_digest: 'f'.repeat(64) },
      };
    },
  });
}

/** 带"导演备注关联"的合成回执：两个镜头共享同一条备注 id。 */
export function receiptWithDirectorNotes(): StoryboardReceipt {
  return storyboardReceipt({
    shots: row => { row.shot = { ...(row.shot as Record<string, unknown>), director_note_ids: ['note-1'] }; },
  });
}

/**
 * 合成导演调度建议回执。刻意**不**复用 `phase4.file-api-director-advice.json`：
 * 那份捕获与当前解码器不兼容（它在这里被 `checkedDirectorAdvice` 拒绝），而我们
 * 不想为了迁就它去放宽既有契约。这里手写一份形状正确、内容无害的对象，并当场
 * 交给同一个解码器验证——它不构成任何真实模型验收证据。
 */
export const directorAdvice = () => checkedDirectorAdvice({
  contract: 'studio-director-advice/1',
  document_snapshot: { id: 'director-doc', version: 2, digest: 'c'.repeat(64) },
  notes: [{
    note_id: 'note-1', scene_id: 'scene-1',
    camera: { shot_size: 'MEDIUM', angle: 'EYE_LEVEL', movement: 'STATIC', lens: '50mm', composition: '左侧留白' },
    visual_style: { color: '冷蓝', lighting: '柔光主光', material: '拉丝金属', style: '水墨插画' },
    rhythm: { pacing: '对白后停顿', duration_seconds: 5, transition: '动作切换' },
  }],
  advice_only: true, automatic_apply: false, model_called: false, product_acceptance: 'LOCAL_REQUIRED',
}, 'director-doc');

/** 原 DIRECTOR 文档（`GET /documents/{rid}`）的合成载荷，形状与 `CreativeDocument` 一致。 */
export function directorDocument(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 'director-doc', version: 2, mode: 'DIRECTOR', title: '合成导演文档', status: 'DRAFT',
    created_at: '', updated_at: '', actor_id: 'synthetic-author', source_evidence: {},
    source_chapter_ids: [], source_independent: true, scenes: [], shots: [], video_plan: null,
    source_documents: {}, visual_target: null,
    director_notes: [{
      id: 'note-1', scene_id: 'scene-1', number: 1, note: '先核对场景目的',
      shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC',
      duration_seconds: 5, emotion: '克制', pacing: '对白后停顿', performance: '收着演', blocking: '待人工确认',
    }],
    ...overrides,
  };
}

/** 原 `GET /director-proposals` 的一条待审建议（形状取自 `creative/client.ts` 的 `DirectorProposal`）。 */
export function directorProposal(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 'proposal-1', version: 1, status: 'NEEDS_REVIEW', source_document_id: 'director-doc',
    source_version: 2, title: '合成导演方案', director_notes: [{
      id: 'note-2', scene_id: 'scene-1', number: 1, note: '待审建议：先核对场景目的',
      shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5,
      emotion: '', pacing: '待审建议：对白后保留反应停顿', performance: '', blocking: '待人工确认',
    }],
    output_digest: 'a'.repeat(64),
    provenance: { method: 'RULE_ASSISTED', model_called: false, quality_verification: 'HUMAN_REVIEW_REQUIRED' },
    ...overrides,
  };
}
