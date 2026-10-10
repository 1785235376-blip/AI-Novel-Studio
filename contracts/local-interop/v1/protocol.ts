// Generated public Local Interop 1.0 DTOs. Validate Schema + semantics at ingress.
// Advice never grants authority, navigation, model execution or project writes.

export interface AppContextCapsule {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly capsule_id: string;
  readonly source_version: string;
  readonly capsule_hash: string;
  readonly product_id: string;
  readonly product_version: string;
  readonly instance_id: string;
  readonly project_id?: string | null;
  readonly project_version?: string | null;
  readonly workspace_id?: string | null;
  readonly storyline_id?: string | null;
  readonly branch_id?: string | null;
  readonly module: string;
  readonly surface: string;
  readonly chapter_id?: string | null;
  readonly chapter_version?: number | null;
  readonly selection_id?: string | null;
  readonly selection_hash?: string | null;
  readonly task_id?: string | null;
  readonly task_type?: string | null;
  readonly task_status?: "PENDING" | "QUEUED" | "RUNNING" | "WAITING" | "FAILED" | "COMPLETED" | "CANCELLED" | "BLOCKED" | "UNKNOWN" | null;
  readonly runtime_id?: string | null;
  readonly runtime_status?: "READY" | "LOADING" | "UNAVAILABLE" | "ERROR" | "UNKNOWN" | null;
  readonly model_id?: string | null;
  readonly error_code?: string | null;
  readonly privacy_scope?: "LOCAL_ONLY" | "REDACTION_REQUIRED" | "CONSENTED_CLOUD";
  readonly created_at: string;
  readonly expires_at: string;
  readonly evidence?: ReadonlyArray<ContextEvidence>;
  readonly content?: ContextContent;
}

export interface CancelRequest {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly request_id: string;
  readonly session_id?: string | null;
}

export interface CancelResult {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly request_id: string;
  readonly session_id?: string | null;
  readonly status?: "CANCELLED";
}

export interface CapabilityDescriptor {
  readonly capability: "project.context.read" | "project.selection.share" | "project.metadata.read" | "task.status.read" | "task.error.read" | "diagnostics.read" | "model.registry.read" | "model.runtime.status.read" | "tutor.guidance.request" | "tutor.guidance.receive" | "verifier.request" | "verifier.result.receive" | "case.candidate.create" | "handoff.open_feature" | "handoff.open_project" | "handoff.open_task";
  readonly supported?: boolean;
}

export interface CapabilityNegotiation {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly hello_id: string;
  readonly requested_capabilities: ReadonlyArray<string>;
  readonly granted_capabilities?: ReadonlyArray<"project.context.read" | "project.selection.share" | "project.metadata.read" | "task.status.read" | "task.error.read" | "diagnostics.read" | "model.registry.read" | "model.runtime.status.read" | "tutor.guidance.request" | "tutor.guidance.receive" | "verifier.request" | "verifier.result.receive" | "case.candidate.create" | "handoff.open_feature" | "handoff.open_project" | "handoff.open_task">;
}

export interface CapabilityState {
  readonly capability: "project.context.read" | "project.selection.share" | "project.metadata.read" | "task.status.read" | "task.error.read" | "diagnostics.read" | "model.registry.read" | "model.runtime.status.read" | "tutor.guidance.request" | "tutor.guidance.receive" | "verifier.request" | "verifier.result.receive" | "case.candidate.create" | "handoff.open_feature" | "handoff.open_project" | "handoff.open_task";
  readonly available: boolean;
}

export interface CaseCandidate {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly candidate_id: string;
  readonly problem: string;
  readonly environment: CaseEnvironment;
  readonly diagnosis: string;
  readonly guidance: TutorGuidance;
  readonly result: string;
  readonly verification: VerifierResult;
  readonly software_id: string;
  readonly software_version: string;
  readonly evidence?: ReadonlyArray<ContextEvidence>;
  readonly privacy_scope?: "LOCAL_ONLY" | "REDACTION_REQUIRED" | "CONSENTED_CLOUD";
  readonly created_at: string;
}

export interface CaseEnvironment {
  readonly product_id: string;
  readonly product_version: string;
  readonly module: string;
  readonly runtime_id?: string | null;
  readonly model_id?: string | null;
  readonly task_type?: string | null;
}

export interface ContextContent {
  readonly level?: "NONE" | "SELECTED_TEXT" | "CURRENT_CHAPTER" | "PROJECT_CONTEXT";
  readonly text?: string | null;
  readonly consent_id?: string | null;
}

export interface ContextEvidence {
  readonly source_id: string;
  readonly source_version: string;
  readonly locator: string;
  readonly content_hash: string;
  readonly timestamp: string;
  readonly authority: "AUTHORITATIVE" | "CONSTRAINING" | "SUPPORTING" | "ADVISORY";
  readonly privacy?: "LOCAL_ONLY" | "REDACTION_REQUIRED" | "CONSENTED_CLOUD";
}

export interface DiagnosticCapsule {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly diagnostic_id: string;
  readonly source_version: string;
  readonly content_hash: string;
  readonly software_id?: string | null;
  readonly software_version?: string | null;
  readonly feature?: string | null;
  readonly error_code?: string | null;
  readonly task_state?: "PENDING" | "QUEUED" | "RUNNING" | "WAITING" | "FAILED" | "COMPLETED" | "CANCELLED" | "BLOCKED" | "UNKNOWN" | null;
  readonly runtime?: string | null;
  readonly model?: string | null;
  readonly capability_state?: ReadonlyArray<CapabilityState>;
  readonly privacy_scope?: "LOCAL_ONLY" | "REDACTION_REQUIRED" | "CONSENTED_CLOUD";
  readonly created_at: string;
  readonly expires_at: string;
  readonly evidence?: ReadonlyArray<ContextEvidence>;
  readonly sanitized?: true;
}

export interface DiscoveryRecord {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly product_id: string;
  readonly instance_id: string;
  readonly product_version: string;
  readonly protocol_versions?: ReadonlyArray<string>;
  readonly capabilities?: ReadonlyArray<string>;
}

export interface GuidanceReference {
  readonly source_id: string;
  readonly label: string;
  readonly locator: string;
}

export interface GuidanceStep {
  readonly step_id: string;
  readonly instruction: string;
  readonly handoff?: HandoffTarget | null;
}

export interface HandoffRequest {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly request_id: string;
  readonly session_id: string;
  readonly target: HandoffTarget;
  readonly user_gesture_id: string;
}

export interface HandoffResult {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly request_id: string;
  readonly session_id: string;
  readonly status: "OPENED" | "REJECTED";
  readonly error_code?: "PROTOCOL_INCOMPATIBLE" | "PRODUCT_NOT_AVAILABLE" | "CAPABILITY_NOT_SUPPORTED" | "SESSION_REQUIRED" | "SESSION_REVOKED" | "PERMISSION_DENIED" | "CONTEXT_NOT_AUTHORIZED" | "CONTEXT_STALE" | "SOURCE_CHANGED" | "HANDOFF_TARGET_NOT_FOUND" | "TUTOR_UNAVAILABLE" | "VERIFIER_UNAVAILABLE" | "MODEL_NOT_AVAILABLE" | "TRANSPORT_ERROR" | "TIMEOUT" | "CANCELLED" | "INVALID_MESSAGE" | null;
}

export interface HandoffTarget {
  readonly action: "OPEN_FEATURE" | "OPEN_PROJECT" | "OPEN_TASK" | "OPEN_CHAPTER" | "OPEN_SESSION";
  readonly target_product_id: string;
  readonly feature?: string | null;
  readonly project_id?: string | null;
  readonly chapter_id?: string | null;
  readonly task_id?: string | null;
  readonly session_id?: string | null;
  readonly source_version?: string | null;
}

export interface HandshakeHello {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly product: ProductDescriptor;
  readonly transport: "NAMED_PIPE" | "LOOPBACK_HTTP";
  readonly session_nonce: string;
  readonly privacy_mode?: "LOCAL_ONLY" | "REDACTION_REQUIRED" | "CONSENTED_CLOUD";
}

export interface Heartbeat {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly session_id: string;
  readonly sequence: number;
  readonly created_at: string;
}

export interface HelloResult {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly hello_id: string;
  readonly product: ProductDescriptor;
  readonly session_nonce: string;
}

export interface InteropError {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly request_id?: string | null;
  readonly code: "PROTOCOL_INCOMPATIBLE" | "PRODUCT_NOT_AVAILABLE" | "CAPABILITY_NOT_SUPPORTED" | "SESSION_REQUIRED" | "SESSION_REVOKED" | "PERMISSION_DENIED" | "CONTEXT_NOT_AUTHORIZED" | "CONTEXT_STALE" | "SOURCE_CHANGED" | "HANDOFF_TARGET_NOT_FOUND" | "TUTOR_UNAVAILABLE" | "VERIFIER_UNAVAILABLE" | "MODEL_NOT_AVAILABLE" | "TRANSPORT_ERROR" | "TIMEOUT" | "CANCELLED" | "INVALID_MESSAGE";
  readonly message: string;
  readonly retryable?: boolean;
}

export interface InteropEvent {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly event_id: string;
  readonly session_id: string;
  readonly sequence: number;
  readonly event_type: "PROJECT_OPENED" | "PROJECT_CLOSED" | "CHAPTER_OPENED" | "TASK_STARTED" | "TASK_UPDATED" | "TASK_FAILED" | "TASK_COMPLETED" | "TASK_CANCELLED" | "MODEL_CHANGED" | "RUNTIME_AVAILABLE" | "RUNTIME_UNAVAILABLE" | "VALIDATION_REQUIRED" | "EXPORT_FAILED" | "WORKFLOW_BLOCKED";
  readonly created_at: string;
  readonly context: AppContextCapsule;
}

export interface ModelRecommendation {
  readonly runtime_id: string;
  readonly model_id: string;
  readonly reason: string;
  readonly authority?: "ADVISORY";
}

export interface ModelRegistry {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly models?: ReadonlyArray<SharedModelDescriptor>;
  readonly created_at: string;
}

export interface ProductDescriptor {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly product_id: string;
  readonly display_name: string;
  readonly product_version: string;
  readonly instance_id: string;
  readonly product_role: "AI_TUTOR" | "CREATIVE_STUDIO" | "DCC" | "VIDEO_EDITOR" | "GAME_ENGINE" | "IMAGE_TOOL" | "AUDIO_TOOL";
  readonly protocol_versions?: ReadonlyArray<string>;
  readonly capabilities?: ReadonlyArray<string>;
}

export interface SessionDescriptor {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly session_id: string;
  readonly product_id: string;
  readonly instance_id: string;
  readonly peer_product_id: string;
  readonly peer_instance_id: string;
  readonly user_identity: string;
  readonly capabilities: ReadonlyArray<"project.context.read" | "project.selection.share" | "project.metadata.read" | "task.status.read" | "task.error.read" | "diagnostics.read" | "model.registry.read" | "model.runtime.status.read" | "tutor.guidance.request" | "tutor.guidance.receive" | "verifier.request" | "verifier.result.receive" | "case.candidate.create" | "handoff.open_feature" | "handoff.open_project" | "handoff.open_task">;
  readonly nonce: string;
  readonly created_at: string;
  readonly expires_at: string;
  readonly transport: "NAMED_PIPE" | "LOOPBACK_HTTP";
}

export interface SessionOpenRequest {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly hello_id: string;
  readonly session_nonce: string;
  readonly user_identity: string;
}

export interface SessionOpenResult {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly session: SessionDescriptor;
  readonly session_token: string;
}

export interface SharedModelDescriptor {
  readonly runtime_id: string;
  readonly model_id: string;
  readonly family: string;
  readonly modality: ReadonlyArray<"TEXT" | "IMAGE" | "AUDIO" | "VIDEO" | "EMBEDDING" | "MULTIMODAL">;
  readonly runtime_type: string;
  readonly local: boolean;
  readonly declared_capabilities?: ReadonlyArray<string>;
  readonly verified_capabilities?: ReadonlyArray<string>;
  readonly model_version?: string | null;
  readonly model_hash_if_available?: string | null;
  readonly context_window?: number | null;
  readonly compatibility?: ReadonlyArray<string>;
  readonly availability?: "AVAILABLE" | "UNAVAILABLE" | "UNKNOWN";
  readonly last_validated?: string | null;
}

export interface TaskRequirement {
  readonly task_type: string;
  readonly required_modality: ReadonlyArray<"TEXT" | "IMAGE" | "AUDIO" | "VIDEO" | "EMBEDDING" | "MULTIMODAL">;
  readonly estimated_context: number;
  readonly privacy?: "LOCAL_ONLY" | "REDACTION_REQUIRED" | "CONSENTED_CLOUD";
  readonly quality_priority?: number;
  readonly latency_priority?: number;
  readonly cost_priority?: number;
}

export interface TransportRequest {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly operation: "HELLO" | "CAPABILITY_NEGOTIATION" | "SESSION" | "TUTOR" | "DIAGNOSTICS" | "VERIFY" | "HANDOFF" | "HEARTBEAT" | "CANCEL";
  readonly payload: HandshakeHello | CapabilityNegotiation | SessionOpenRequest | TutorRequest | VerifierRequest | HandoffRequest | Heartbeat | CancelRequest;
}

export interface TransportResponse {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly operation: "HELLO" | "CAPABILITY_NEGOTIATION" | "SESSION" | "TUTOR" | "DIAGNOSTICS" | "VERIFY" | "HANDOFF" | "HEARTBEAT" | "CANCEL";
  readonly payload: HelloResult | CapabilityNegotiation | SessionOpenResult | TutorGuidance | VerifierResult | HandoffResult | Heartbeat | CancelResult | InteropError;
}

export interface TutorGuidance {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly request_id: string;
  readonly session_id: string;
  readonly guidance_id: string;
  readonly summary: string;
  readonly diagnosis: string;
  readonly steps?: ReadonlyArray<GuidanceStep>;
  readonly warnings?: ReadonlyArray<string>;
  readonly references?: ReadonlyArray<GuidanceReference>;
  readonly verification_condition?: VerificationCondition | null;
  readonly recommended_model?: ModelRecommendation | null;
  readonly privacy_scope?: "LOCAL_ONLY" | "REDACTION_REQUIRED" | "CONSENTED_CLOUD";
  readonly created_at: string;
  readonly authority?: "ADVISORY";
}

export interface TutorRequest {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly request_id: string;
  readonly session_id: string;
  readonly context: AppContextCapsule;
  readonly question?: string | null;
  readonly diagnostic?: DiagnosticCapsule | null;
  readonly task_requirement?: TaskRequirement | null;
}

export interface VerificationCondition {
  readonly field: "runtime_status" | "task_status" | "project_version" | "chapter_version";
  readonly operator?: "EQ" | "NE" | "GTE";
  readonly expected_value: "PENDING" | "QUEUED" | "RUNNING" | "WAITING" | "FAILED" | "COMPLETED" | "CANCELLED" | "BLOCKED" | "UNKNOWN" | "READY" | "LOADING" | "UNAVAILABLE" | "ERROR" | "UNKNOWN" | string | number;
  readonly source_id: string;
}

export interface VerifierRequest {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly request_id: string;
  readonly session_id: string;
  readonly guidance_id: string;
  readonly condition: VerificationCondition;
  readonly context: AppContextCapsule;
}

export interface VerifierResult {
  readonly protocol_name: "PoemSeed Local Interop";
  readonly protocol_version: "1.0";
  readonly request_id: string;
  readonly session_id: string;
  readonly result_id: string;
  readonly status: "VERIFIED" | "PARTIAL" | "FAILED" | "UNKNOWN";
  readonly reason: string;
  readonly evidence?: ReadonlyArray<ContextEvidence>;
  readonly privacy_scope?: "LOCAL_ONLY" | "REDACTION_REQUIRED" | "CONSENTED_CLOUD";
  readonly created_at: string;
}
