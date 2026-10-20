import { newDocument, newScene, type CreativeDocument } from './types';
import type { ImagePreview, ImageStatus, ImagePending, ImageReview } from './directorImageClient';
export const imageSnapshot = { id: 'director', version: 2, digest: 'b'.repeat(64) };
export const imageTarget = { document_id: 'director', version: 2, digest: imageSnapshot.digest, scene_id: 'scene' };
export const imageSourceDocument: CreativeDocument = { ...newDocument('DIRECTOR'), source_independent: true, id: 'director', version: 2, status: 'DRAFT', title: '原导演',
  created_at: '', updated_at: '', actor_id: 'actor', source_evidence: {}, scenes: [{ ...newScene(1), id: 'scene', heading: '原场景' }] };
export const imageAsset = { id: 'image', filename: 'source.png', version: 3, sha256: 'a'.repeat(64), kind: 'image', media_type: 'image/png', size: 128, novel_id: 'project', created_at: '', updated_at: '' };
export const imageRegistration = { provider_id: 'local:vision', model_id: 'vision', display_name: '现有 VISION 注册' };
export const imageAdvice = { observations: ['私密模型描述'], suggestions: ['私密机位建议'], uncertainty: '无法确认场景深度' };
export const imagePreview: ImagePreview = { id: 'proposal', version: 1, preview_digest: 'c'.repeat(64), target: imageTarget,
  asset: { asset_id: imageAsset.id, version: imageAsset.version, sha256: imageAsset.sha256 }, ...imageRegistration, prompt: '私密完整提示', parameters: { max_output_tokens: 512, temperature: 0 } };
export const imageStatus: ImageStatus = { id: 'proposal', version: 2, status: 'DISPATCHED', job_id: 'job', job_status: 'COMPLETED', can_cancel: false, target_document_id: 'director', target_scene_id: 'scene' };
export const imagePending: ImagePending = { id: 'proposal', version: 3, target: imageTarget, terminal_digest: 'd'.repeat(64), accounting_version: 7, advice: imageAdvice };
export const imageReview: ImageReview = { proposal_id: 'proposal', proposal_version: 3, target: imageTarget, terminal_digest: 'd'.repeat(64), accounting_digest: 'e'.repeat(64), declared_microusd: 0, advice: imageAdvice };
export const imageSourceWire = { contract: 'CREATIVE_DIRECTOR_IMAGE_SOURCE_V3', source_kind: 'IMAGE', project_id: 'project', project_incarnation: 'file:owner', actor_id: 'actor',
  scope: { mode: 'local', novel_id: 'project' }, asset: imagePreview.asset, media_type: 'image/png', byte_count: 128, width: 2, height: 2, orientation: 'IDENTITY_ONLY', transformation: 'NONE_EXACT_ASSET_BYTES' };
export const imagePreviewWire = { id: 'proposal', version: 1, status: 'PREVIEW', preview_digest: imagePreview.preview_digest, model_called: false, measurement_verified: false, observations_verified: false,
  preview: { source: imageSourceWire, target: imageTarget, provider_id: imageRegistration.provider_id, model_id: imageRegistration.model_id, route_digest: 'f'.repeat(64), prompt: imagePreview.prompt, parameters: imagePreview.parameters } };
export const imageStatusWire = { ...imageStatus, automatic_retry: false, content_freshness: 'NOT_CHECKED' };
export const imageCapabilitiesWire = { contract: 'DIRECTOR_IMAGE_CAPABILITIES_V3', enabled: true, registered_choices: [imageRegistration], local_only: true, automatic_retry: false,
  automatic_fallback: false, measurement_verified: false, observations_verified: false, recovery_available: true, vision_registration_required: true };
export const imagePendingWire = { id: 'proposal', version: 3, status: 'PENDING_REVIEW', accounting_version: 7,
  pending: { contract: 'DIRECTOR_IMAGE_PENDING_V3', terminal_digest: imagePending.terminal_digest, source: imageSourceWire, target: imageTarget, advice: { contract: 'DIRECTOR_IMAGE_ADVICE_V3', ...imageAdvice },
    accounting_status: 'UNKNOWN_UPSTREAM', adoption_available: false, adoption_blocker: 'DIRECTOR_IMAGE_ADOPTION_NOT_INTEGRATED', observations_verified: false, quality_verification: 'HUMAN_REVIEW_REQUIRED' } };
export const imageReviewWire = { contract: 'DIRECTOR_IMAGE_REVIEW_V1', ...imageReview, advice: { contract: 'DIRECTOR_IMAGE_ADVICE_V3', ...imageAdvice }, declared_microusd: undefined,
  accounting: { contract: 'DIRECTOR_IMAGE_COST_DECLARATION_RECEIPT_V3', declared_microusd: 0, cost_state: 'HUMAN_DECLARED_LOCAL_COST', measurement_verified: false },
  measurement_verified: false, observations_verified: false, adoption_available: true, human_review_required: true };
delete imageReviewWire.declared_microusd;
