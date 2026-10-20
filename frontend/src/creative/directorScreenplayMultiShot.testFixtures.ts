import captured from './directorScreenplayWire.testFixture.json';
import type { DirectorAllowedSourceMapping, DirectorPendingReceipt, DirectorPreviewReceipt, DirectorReviewSubmission } from './directorModelClient';

/** Constructed protocol fixture, not real-provider execution or quality evidence. */
export function multiShotFixture(maxOutputTokens = 512) {
  const allowed: DirectorAllowedSourceMapping[] = ['scene-a', 'scene-b'].flatMap((scene_id, index) => [1, 2, 3].map(slot => ({
    note_id: `${scene_id}-candidate-${slot}`, scene_id, source_sequence: index ? 9 : 4, slot,
  })));
  // The model may skip a slot. Selected candidates remain in frozen source/slot order.
  const selected = [allowed[0], allowed[2], allowed[3], allowed[4]].map(({ slot: _slot, ...row }, index) => ({ ...row, number: index + 1 }));
  const notes = selected.map((row, index) => {
    const note = structuredClone(captured.pending.receipt.director_notes[0]);
    return { ...note, id: row.note_id, number: row.number, scene_id: row.scene_id, duration_seconds: index + 5,
      planning: { ...note.planning, evidence: note.planning.evidence.map(evidence => ({ ...evidence, scene_id: row.scene_id })) } };
  });
  const preview: DirectorPreviewReceipt = { ...structuredClone(captured.preview.receipt),
    contract: 'DIRECTOR_SCREENPLAY_MODEL_PREVIEW_V3', source_mode: 'SCREENPLAY', local_only: true, reserve_microusd: 0,
    model_called: false, automatic_retry: false, quality_verification: 'NOT_RUN',
    parameters: { ...captured.preview.receipt.parameters, max_output_tokens: maxOutputTokens },
    planning_mode: 'MULTI_SHOT_V1', allowed_source_mapping: structuredClone(allowed),
    prompt: `INDEPENDENT_SCREENPLAY_SHOT_PLAN_V1\n${JSON.stringify({ allowed_source_mapping: allowed })}` };
  const pending: DirectorPendingReceipt = { ...structuredClone(captured.pending.receipt),
    contract: 'DIRECTOR_SCREENPLAY_MODEL_PENDING_REVIEW_V3', director_notes: notes,
    provenance: { ...structuredClone(captured.pending.receipt.provenance), method: 'MODEL_ASSISTED', model_called: true,
      parameters: { ...captured.pending.receipt.provenance.parameters, max_output_tokens: maxOutputTokens },
      synthetic: false, source_mode: 'SCREENPLAY', quality_verification: 'HUMAN_REVIEW_REQUIRED',
      output_contract: 'INDEPENDENT_SCREENPLAY_SHOT_PLAN_V1', allowed_source_mapping: structuredClone(allowed), source_mapping: selected } };
  const submitted: DirectorReviewSubmission = { expected_version: pending.expected_version,
    reviewed_output_digest: pending.output_digest, title: captured.submitted_review.title, director_notes: structuredClone(notes) };
  return { ...structuredClone(captured), preview: { ...structuredClone(captured.preview), receipt: preview },
    pending: { ...structuredClone(captured.pending), receipt: pending }, submitted_review: submitted,
    pending_status: { ...structuredClone(captured.completed_status), receipt: { ...structuredClone(captured.completed_status.receipt), phase: 'PENDING_REVIEW', version: pending.expected_version } } };
}
