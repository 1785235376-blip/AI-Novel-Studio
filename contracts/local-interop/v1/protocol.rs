// GENERATED INTERFACE DRAFT. Requires serde derive. No Desktop runtime claim.
// Validate all values against the accompanying JSON Schema before use.
// Serde alone does not enforce bounds, hashes, timestamps, privacy or provenance.
// Optional defaults must be hydrated per the schema before canonical hashing.
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AppContextCapsuleProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AppContextCapsuleProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AppContextCapsuleTaskStatus {
    #[serde(rename = "PENDING")]
    V0,
    #[serde(rename = "QUEUED")]
    V1,
    #[serde(rename = "RUNNING")]
    V2,
    #[serde(rename = "WAITING")]
    V3,
    #[serde(rename = "FAILED")]
    V4,
    #[serde(rename = "COMPLETED")]
    V5,
    #[serde(rename = "CANCELLED")]
    V6,
    #[serde(rename = "BLOCKED")]
    V7,
    #[serde(rename = "UNKNOWN")]
    V8,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AppContextCapsuleRuntimeStatus {
    #[serde(rename = "READY")]
    V0,
    #[serde(rename = "LOADING")]
    V1,
    #[serde(rename = "UNAVAILABLE")]
    V2,
    #[serde(rename = "ERROR")]
    V3,
    #[serde(rename = "UNKNOWN")]
    V4,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AppContextCapsulePrivacyScope {
    #[serde(rename = "LOCAL_ONLY")]
    V0,
    #[serde(rename = "REDACTION_REQUIRED")]
    V1,
    #[serde(rename = "CONSENTED_CLOUD")]
    V2,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CancelRequestProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CancelRequestProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CancelResultProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CancelResultProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CancelResultStatus {
    #[serde(rename = "CANCELLED")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CapabilityDescriptorCapability {
    #[serde(rename = "project.context.read")]
    V0,
    #[serde(rename = "project.selection.share")]
    V1,
    #[serde(rename = "project.metadata.read")]
    V2,
    #[serde(rename = "task.status.read")]
    V3,
    #[serde(rename = "task.error.read")]
    V4,
    #[serde(rename = "diagnostics.read")]
    V5,
    #[serde(rename = "model.registry.read")]
    V6,
    #[serde(rename = "model.runtime.status.read")]
    V7,
    #[serde(rename = "tutor.guidance.request")]
    V8,
    #[serde(rename = "tutor.guidance.receive")]
    V9,
    #[serde(rename = "verifier.request")]
    V10,
    #[serde(rename = "verifier.result.receive")]
    V11,
    #[serde(rename = "case.candidate.create")]
    V12,
    #[serde(rename = "handoff.open_feature")]
    V13,
    #[serde(rename = "handoff.open_project")]
    V14,
    #[serde(rename = "handoff.open_task")]
    V15,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CapabilityNegotiationProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CapabilityNegotiationProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CapabilityNegotiationGrantedCapabilitiesItem {
    #[serde(rename = "project.context.read")]
    V0,
    #[serde(rename = "project.selection.share")]
    V1,
    #[serde(rename = "project.metadata.read")]
    V2,
    #[serde(rename = "task.status.read")]
    V3,
    #[serde(rename = "task.error.read")]
    V4,
    #[serde(rename = "diagnostics.read")]
    V5,
    #[serde(rename = "model.registry.read")]
    V6,
    #[serde(rename = "model.runtime.status.read")]
    V7,
    #[serde(rename = "tutor.guidance.request")]
    V8,
    #[serde(rename = "tutor.guidance.receive")]
    V9,
    #[serde(rename = "verifier.request")]
    V10,
    #[serde(rename = "verifier.result.receive")]
    V11,
    #[serde(rename = "case.candidate.create")]
    V12,
    #[serde(rename = "handoff.open_feature")]
    V13,
    #[serde(rename = "handoff.open_project")]
    V14,
    #[serde(rename = "handoff.open_task")]
    V15,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CapabilityStateCapability {
    #[serde(rename = "project.context.read")]
    V0,
    #[serde(rename = "project.selection.share")]
    V1,
    #[serde(rename = "project.metadata.read")]
    V2,
    #[serde(rename = "task.status.read")]
    V3,
    #[serde(rename = "task.error.read")]
    V4,
    #[serde(rename = "diagnostics.read")]
    V5,
    #[serde(rename = "model.registry.read")]
    V6,
    #[serde(rename = "model.runtime.status.read")]
    V7,
    #[serde(rename = "tutor.guidance.request")]
    V8,
    #[serde(rename = "tutor.guidance.receive")]
    V9,
    #[serde(rename = "verifier.request")]
    V10,
    #[serde(rename = "verifier.result.receive")]
    V11,
    #[serde(rename = "case.candidate.create")]
    V12,
    #[serde(rename = "handoff.open_feature")]
    V13,
    #[serde(rename = "handoff.open_project")]
    V14,
    #[serde(rename = "handoff.open_task")]
    V15,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CaseCandidateProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CaseCandidateProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CaseCandidatePrivacyScope {
    #[serde(rename = "LOCAL_ONLY")]
    V0,
    #[serde(rename = "REDACTION_REQUIRED")]
    V1,
    #[serde(rename = "CONSENTED_CLOUD")]
    V2,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ContextContentLevel {
    #[serde(rename = "NONE")]
    V0,
    #[serde(rename = "SELECTED_TEXT")]
    V1,
    #[serde(rename = "CURRENT_CHAPTER")]
    V2,
    #[serde(rename = "PROJECT_CONTEXT")]
    V3,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ContextEvidenceAuthority {
    #[serde(rename = "AUTHORITATIVE")]
    V0,
    #[serde(rename = "CONSTRAINING")]
    V1,
    #[serde(rename = "SUPPORTING")]
    V2,
    #[serde(rename = "ADVISORY")]
    V3,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ContextEvidencePrivacy {
    #[serde(rename = "LOCAL_ONLY")]
    V0,
    #[serde(rename = "REDACTION_REQUIRED")]
    V1,
    #[serde(rename = "CONSENTED_CLOUD")]
    V2,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DiagnosticCapsuleProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DiagnosticCapsuleProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DiagnosticCapsuleTaskState {
    #[serde(rename = "PENDING")]
    V0,
    #[serde(rename = "QUEUED")]
    V1,
    #[serde(rename = "RUNNING")]
    V2,
    #[serde(rename = "WAITING")]
    V3,
    #[serde(rename = "FAILED")]
    V4,
    #[serde(rename = "COMPLETED")]
    V5,
    #[serde(rename = "CANCELLED")]
    V6,
    #[serde(rename = "BLOCKED")]
    V7,
    #[serde(rename = "UNKNOWN")]
    V8,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DiagnosticCapsulePrivacyScope {
    #[serde(rename = "LOCAL_ONLY")]
    V0,
    #[serde(rename = "REDACTION_REQUIRED")]
    V1,
    #[serde(rename = "CONSENTED_CLOUD")]
    V2,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DiscoveryRecordProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DiscoveryRecordProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HandoffRequestProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HandoffRequestProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HandoffResultProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HandoffResultProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HandoffResultStatus {
    #[serde(rename = "OPENED")]
    V0,
    #[serde(rename = "REJECTED")]
    V1,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HandoffResultErrorCode {
    #[serde(rename = "PROTOCOL_INCOMPATIBLE")]
    V0,
    #[serde(rename = "PRODUCT_NOT_AVAILABLE")]
    V1,
    #[serde(rename = "CAPABILITY_NOT_SUPPORTED")]
    V2,
    #[serde(rename = "SESSION_REQUIRED")]
    V3,
    #[serde(rename = "SESSION_REVOKED")]
    V4,
    #[serde(rename = "PERMISSION_DENIED")]
    V5,
    #[serde(rename = "CONTEXT_NOT_AUTHORIZED")]
    V6,
    #[serde(rename = "CONTEXT_STALE")]
    V7,
    #[serde(rename = "SOURCE_CHANGED")]
    V8,
    #[serde(rename = "HANDOFF_TARGET_NOT_FOUND")]
    V9,
    #[serde(rename = "TUTOR_UNAVAILABLE")]
    V10,
    #[serde(rename = "VERIFIER_UNAVAILABLE")]
    V11,
    #[serde(rename = "MODEL_NOT_AVAILABLE")]
    V12,
    #[serde(rename = "TRANSPORT_ERROR")]
    V13,
    #[serde(rename = "TIMEOUT")]
    V14,
    #[serde(rename = "CANCELLED")]
    V15,
    #[serde(rename = "INVALID_MESSAGE")]
    V16,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HandoffTargetAction {
    #[serde(rename = "OPEN_FEATURE")]
    V0,
    #[serde(rename = "OPEN_PROJECT")]
    V1,
    #[serde(rename = "OPEN_TASK")]
    V2,
    #[serde(rename = "OPEN_CHAPTER")]
    V3,
    #[serde(rename = "OPEN_SESSION")]
    V4,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HandshakeHelloProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HandshakeHelloProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HandshakeHelloTransport {
    #[serde(rename = "NAMED_PIPE")]
    V0,
    #[serde(rename = "LOOPBACK_HTTP")]
    V1,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HandshakeHelloPrivacyMode {
    #[serde(rename = "LOCAL_ONLY")]
    V0,
    #[serde(rename = "REDACTION_REQUIRED")]
    V1,
    #[serde(rename = "CONSENTED_CLOUD")]
    V2,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HeartbeatProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HeartbeatProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HelloResultProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HelloResultProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum InteropErrorProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum InteropErrorProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum InteropErrorCode {
    #[serde(rename = "PROTOCOL_INCOMPATIBLE")]
    V0,
    #[serde(rename = "PRODUCT_NOT_AVAILABLE")]
    V1,
    #[serde(rename = "CAPABILITY_NOT_SUPPORTED")]
    V2,
    #[serde(rename = "SESSION_REQUIRED")]
    V3,
    #[serde(rename = "SESSION_REVOKED")]
    V4,
    #[serde(rename = "PERMISSION_DENIED")]
    V5,
    #[serde(rename = "CONTEXT_NOT_AUTHORIZED")]
    V6,
    #[serde(rename = "CONTEXT_STALE")]
    V7,
    #[serde(rename = "SOURCE_CHANGED")]
    V8,
    #[serde(rename = "HANDOFF_TARGET_NOT_FOUND")]
    V9,
    #[serde(rename = "TUTOR_UNAVAILABLE")]
    V10,
    #[serde(rename = "VERIFIER_UNAVAILABLE")]
    V11,
    #[serde(rename = "MODEL_NOT_AVAILABLE")]
    V12,
    #[serde(rename = "TRANSPORT_ERROR")]
    V13,
    #[serde(rename = "TIMEOUT")]
    V14,
    #[serde(rename = "CANCELLED")]
    V15,
    #[serde(rename = "INVALID_MESSAGE")]
    V16,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum InteropEventProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum InteropEventProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum InteropEventEventType {
    #[serde(rename = "PROJECT_OPENED")]
    V0,
    #[serde(rename = "PROJECT_CLOSED")]
    V1,
    #[serde(rename = "CHAPTER_OPENED")]
    V2,
    #[serde(rename = "TASK_STARTED")]
    V3,
    #[serde(rename = "TASK_UPDATED")]
    V4,
    #[serde(rename = "TASK_FAILED")]
    V5,
    #[serde(rename = "TASK_COMPLETED")]
    V6,
    #[serde(rename = "TASK_CANCELLED")]
    V7,
    #[serde(rename = "MODEL_CHANGED")]
    V8,
    #[serde(rename = "RUNTIME_AVAILABLE")]
    V9,
    #[serde(rename = "RUNTIME_UNAVAILABLE")]
    V10,
    #[serde(rename = "VALIDATION_REQUIRED")]
    V11,
    #[serde(rename = "EXPORT_FAILED")]
    V12,
    #[serde(rename = "WORKFLOW_BLOCKED")]
    V13,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ModelRecommendationAuthority {
    #[serde(rename = "ADVISORY")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ModelRegistryProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ModelRegistryProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ProductDescriptorProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ProductDescriptorProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ProductDescriptorProductRole {
    #[serde(rename = "AI_TUTOR")]
    V0,
    #[serde(rename = "CREATIVE_STUDIO")]
    V1,
    #[serde(rename = "DCC")]
    V2,
    #[serde(rename = "VIDEO_EDITOR")]
    V3,
    #[serde(rename = "GAME_ENGINE")]
    V4,
    #[serde(rename = "IMAGE_TOOL")]
    V5,
    #[serde(rename = "AUDIO_TOOL")]
    V6,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SessionDescriptorProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SessionDescriptorProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SessionDescriptorCapabilitiesItem {
    #[serde(rename = "project.context.read")]
    V0,
    #[serde(rename = "project.selection.share")]
    V1,
    #[serde(rename = "project.metadata.read")]
    V2,
    #[serde(rename = "task.status.read")]
    V3,
    #[serde(rename = "task.error.read")]
    V4,
    #[serde(rename = "diagnostics.read")]
    V5,
    #[serde(rename = "model.registry.read")]
    V6,
    #[serde(rename = "model.runtime.status.read")]
    V7,
    #[serde(rename = "tutor.guidance.request")]
    V8,
    #[serde(rename = "tutor.guidance.receive")]
    V9,
    #[serde(rename = "verifier.request")]
    V10,
    #[serde(rename = "verifier.result.receive")]
    V11,
    #[serde(rename = "case.candidate.create")]
    V12,
    #[serde(rename = "handoff.open_feature")]
    V13,
    #[serde(rename = "handoff.open_project")]
    V14,
    #[serde(rename = "handoff.open_task")]
    V15,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SessionDescriptorTransport {
    #[serde(rename = "NAMED_PIPE")]
    V0,
    #[serde(rename = "LOOPBACK_HTTP")]
    V1,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SessionOpenRequestProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SessionOpenRequestProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SessionOpenResultProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SessionOpenResultProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SharedModelDescriptorModalityItem {
    #[serde(rename = "TEXT")]
    V0,
    #[serde(rename = "IMAGE")]
    V1,
    #[serde(rename = "AUDIO")]
    V2,
    #[serde(rename = "VIDEO")]
    V3,
    #[serde(rename = "EMBEDDING")]
    V4,
    #[serde(rename = "MULTIMODAL")]
    V5,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SharedModelDescriptorAvailability {
    #[serde(rename = "AVAILABLE")]
    V0,
    #[serde(rename = "UNAVAILABLE")]
    V1,
    #[serde(rename = "UNKNOWN")]
    V2,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TaskRequirementRequiredModalityItem {
    #[serde(rename = "TEXT")]
    V0,
    #[serde(rename = "IMAGE")]
    V1,
    #[serde(rename = "AUDIO")]
    V2,
    #[serde(rename = "VIDEO")]
    V3,
    #[serde(rename = "EMBEDDING")]
    V4,
    #[serde(rename = "MULTIMODAL")]
    V5,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TaskRequirementPrivacy {
    #[serde(rename = "LOCAL_ONLY")]
    V0,
    #[serde(rename = "REDACTION_REQUIRED")]
    V1,
    #[serde(rename = "CONSENTED_CLOUD")]
    V2,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TransportRequestProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TransportRequestProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TransportRequestOperation {
    #[serde(rename = "HELLO")]
    V0,
    #[serde(rename = "CAPABILITY_NEGOTIATION")]
    V1,
    #[serde(rename = "SESSION")]
    V2,
    #[serde(rename = "TUTOR")]
    V3,
    #[serde(rename = "DIAGNOSTICS")]
    V4,
    #[serde(rename = "VERIFY")]
    V5,
    #[serde(rename = "HANDOFF")]
    V6,
    #[serde(rename = "HEARTBEAT")]
    V7,
    #[serde(rename = "CANCEL")]
    V8,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum TransportRequestPayload {
    V0(HandshakeHello),
    V1(CapabilityNegotiation),
    V2(SessionOpenRequest),
    V3(TutorRequest),
    V4(VerifierRequest),
    V5(HandoffRequest),
    V6(Heartbeat),
    V7(CancelRequest),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TransportResponseProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TransportResponseProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TransportResponseOperation {
    #[serde(rename = "HELLO")]
    V0,
    #[serde(rename = "CAPABILITY_NEGOTIATION")]
    V1,
    #[serde(rename = "SESSION")]
    V2,
    #[serde(rename = "TUTOR")]
    V3,
    #[serde(rename = "DIAGNOSTICS")]
    V4,
    #[serde(rename = "VERIFY")]
    V5,
    #[serde(rename = "HANDOFF")]
    V6,
    #[serde(rename = "HEARTBEAT")]
    V7,
    #[serde(rename = "CANCEL")]
    V8,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum TransportResponsePayload {
    V0(HelloResult),
    V1(CapabilityNegotiation),
    V2(SessionOpenResult),
    V3(TutorGuidance),
    V4(VerifierResult),
    V5(HandoffResult),
    V6(Heartbeat),
    V7(CancelResult),
    V8(InteropError),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TutorGuidanceProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TutorGuidanceProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TutorGuidancePrivacyScope {
    #[serde(rename = "LOCAL_ONLY")]
    V0,
    #[serde(rename = "REDACTION_REQUIRED")]
    V1,
    #[serde(rename = "CONSENTED_CLOUD")]
    V2,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TutorGuidanceAuthority {
    #[serde(rename = "ADVISORY")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TutorRequestProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TutorRequestProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum VerificationConditionField {
    #[serde(rename = "runtime_status")]
    V0,
    #[serde(rename = "task_status")]
    V1,
    #[serde(rename = "project_version")]
    V2,
    #[serde(rename = "chapter_version")]
    V3,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum VerificationConditionOperator {
    #[serde(rename = "EQ")]
    V0,
    #[serde(rename = "NE")]
    V1,
    #[serde(rename = "GTE")]
    V2,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum VerificationConditionExpectedValueV0 {
    #[serde(rename = "PENDING")]
    V0,
    #[serde(rename = "QUEUED")]
    V1,
    #[serde(rename = "RUNNING")]
    V2,
    #[serde(rename = "WAITING")]
    V3,
    #[serde(rename = "FAILED")]
    V4,
    #[serde(rename = "COMPLETED")]
    V5,
    #[serde(rename = "CANCELLED")]
    V6,
    #[serde(rename = "BLOCKED")]
    V7,
    #[serde(rename = "UNKNOWN")]
    V8,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum VerificationConditionExpectedValueV1 {
    #[serde(rename = "READY")]
    V0,
    #[serde(rename = "LOADING")]
    V1,
    #[serde(rename = "UNAVAILABLE")]
    V2,
    #[serde(rename = "ERROR")]
    V3,
    #[serde(rename = "UNKNOWN")]
    V4,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum VerificationConditionExpectedValue {
    V0(VerificationConditionExpectedValueV0),
    V1(VerificationConditionExpectedValueV1),
    V2(String),
    V3(u64),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum VerifierRequestProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum VerifierRequestProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum VerifierResultProtocolName {
    #[serde(rename = "PoemSeed Local Interop")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum VerifierResultProtocolVersion {
    #[serde(rename = "1.0")]
    V0,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum VerifierResultStatus {
    #[serde(rename = "VERIFIED")]
    V0,
    #[serde(rename = "PARTIAL")]
    V1,
    #[serde(rename = "FAILED")]
    V2,
    #[serde(rename = "UNKNOWN")]
    V3,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum VerifierResultPrivacyScope {
    #[serde(rename = "LOCAL_ONLY")]
    V0,
    #[serde(rename = "REDACTION_REQUIRED")]
    V1,
    #[serde(rename = "CONSENTED_CLOUD")]
    V2,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AppContextCapsule {
    pub protocol_name: AppContextCapsuleProtocolName,
    pub protocol_version: AppContextCapsuleProtocolVersion,
    pub capsule_id: String,
    pub source_version: String,
    pub capsule_hash: String,
    pub product_id: String,
    pub product_version: String,
    pub instance_id: String,
    pub project_id: Option<String>,
    pub project_version: Option<String>,
    pub workspace_id: Option<String>,
    pub storyline_id: Option<String>,
    pub branch_id: Option<String>,
    pub module: String,
    pub surface: String,
    pub chapter_id: Option<String>,
    pub chapter_version: Option<u64>,
    pub selection_id: Option<String>,
    pub selection_hash: Option<String>,
    pub task_id: Option<String>,
    pub task_type: Option<String>,
    pub task_status: Option<AppContextCapsuleTaskStatus>,
    pub runtime_id: Option<String>,
    pub runtime_status: Option<AppContextCapsuleRuntimeStatus>,
    pub model_id: Option<String>,
    pub error_code: Option<String>,
    pub privacy_scope: Option<AppContextCapsulePrivacyScope>,
    pub created_at: String,
    pub expires_at: String,
    pub evidence: Option<Vec<ContextEvidence>>,
    pub content: Option<ContextContent>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CancelRequest {
    pub protocol_name: CancelRequestProtocolName,
    pub protocol_version: CancelRequestProtocolVersion,
    pub request_id: String,
    pub session_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CancelResult {
    pub protocol_name: CancelResultProtocolName,
    pub protocol_version: CancelResultProtocolVersion,
    pub request_id: String,
    pub session_id: Option<String>,
    pub status: Option<CancelResultStatus>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CapabilityDescriptor {
    pub capability: CapabilityDescriptorCapability,
    pub supported: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CapabilityNegotiation {
    pub protocol_name: CapabilityNegotiationProtocolName,
    pub protocol_version: CapabilityNegotiationProtocolVersion,
    pub hello_id: String,
    pub requested_capabilities: Vec<String>,
    pub granted_capabilities: Option<Vec<CapabilityNegotiationGrantedCapabilitiesItem>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CapabilityState {
    pub capability: CapabilityStateCapability,
    pub available: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CaseCandidate {
    pub protocol_name: CaseCandidateProtocolName,
    pub protocol_version: CaseCandidateProtocolVersion,
    pub candidate_id: String,
    pub problem: String,
    pub environment: CaseEnvironment,
    pub diagnosis: String,
    pub guidance: TutorGuidance,
    pub result: String,
    pub verification: VerifierResult,
    pub software_id: String,
    pub software_version: String,
    pub evidence: Option<Vec<ContextEvidence>>,
    pub privacy_scope: Option<CaseCandidatePrivacyScope>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CaseEnvironment {
    pub product_id: String,
    pub product_version: String,
    pub module: String,
    pub runtime_id: Option<String>,
    pub model_id: Option<String>,
    pub task_type: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ContextContent {
    pub level: Option<ContextContentLevel>,
    pub text: Option<String>,
    pub consent_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ContextEvidence {
    pub source_id: String,
    pub source_version: String,
    pub locator: String,
    pub content_hash: String,
    pub timestamp: String,
    pub authority: ContextEvidenceAuthority,
    pub privacy: Option<ContextEvidencePrivacy>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DiagnosticCapsule {
    pub protocol_name: DiagnosticCapsuleProtocolName,
    pub protocol_version: DiagnosticCapsuleProtocolVersion,
    pub diagnostic_id: String,
    pub source_version: String,
    pub content_hash: String,
    pub software_id: Option<String>,
    pub software_version: Option<String>,
    pub feature: Option<String>,
    pub error_code: Option<String>,
    pub task_state: Option<DiagnosticCapsuleTaskState>,
    pub runtime: Option<String>,
    pub model: Option<String>,
    pub capability_state: Option<Vec<CapabilityState>>,
    pub privacy_scope: Option<DiagnosticCapsulePrivacyScope>,
    pub created_at: String,
    pub expires_at: String,
    pub evidence: Option<Vec<ContextEvidence>>,
    pub sanitized: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DiscoveryRecord {
    pub protocol_name: DiscoveryRecordProtocolName,
    pub protocol_version: DiscoveryRecordProtocolVersion,
    pub product_id: String,
    pub instance_id: String,
    pub product_version: String,
    pub protocol_versions: Option<Vec<String>>,
    pub capabilities: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct GuidanceReference {
    pub source_id: String,
    pub label: String,
    pub locator: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct GuidanceStep {
    pub step_id: String,
    pub instruction: String,
    pub handoff: Option<HandoffTarget>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HandoffRequest {
    pub protocol_name: HandoffRequestProtocolName,
    pub protocol_version: HandoffRequestProtocolVersion,
    pub request_id: String,
    pub session_id: String,
    pub target: HandoffTarget,
    pub user_gesture_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HandoffResult {
    pub protocol_name: HandoffResultProtocolName,
    pub protocol_version: HandoffResultProtocolVersion,
    pub request_id: String,
    pub session_id: String,
    pub status: HandoffResultStatus,
    pub error_code: Option<HandoffResultErrorCode>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HandoffTarget {
    pub action: HandoffTargetAction,
    pub target_product_id: String,
    pub feature: Option<String>,
    pub project_id: Option<String>,
    pub chapter_id: Option<String>,
    pub task_id: Option<String>,
    pub session_id: Option<String>,
    pub source_version: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HandshakeHello {
    pub protocol_name: HandshakeHelloProtocolName,
    pub protocol_version: HandshakeHelloProtocolVersion,
    pub product: ProductDescriptor,
    pub transport: HandshakeHelloTransport,
    pub session_nonce: String,
    pub privacy_mode: Option<HandshakeHelloPrivacyMode>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Heartbeat {
    pub protocol_name: HeartbeatProtocolName,
    pub protocol_version: HeartbeatProtocolVersion,
    pub session_id: String,
    pub sequence: u64,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HelloResult {
    pub protocol_name: HelloResultProtocolName,
    pub protocol_version: HelloResultProtocolVersion,
    pub hello_id: String,
    pub product: ProductDescriptor,
    pub session_nonce: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct InteropError {
    pub protocol_name: InteropErrorProtocolName,
    pub protocol_version: InteropErrorProtocolVersion,
    pub request_id: Option<String>,
    pub code: InteropErrorCode,
    pub message: String,
    pub retryable: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct InteropEvent {
    pub protocol_name: InteropEventProtocolName,
    pub protocol_version: InteropEventProtocolVersion,
    pub event_id: String,
    pub session_id: String,
    pub sequence: u64,
    pub event_type: InteropEventEventType,
    pub created_at: String,
    pub context: AppContextCapsule,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ModelRecommendation {
    pub runtime_id: String,
    pub model_id: String,
    pub reason: String,
    pub authority: Option<ModelRecommendationAuthority>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ModelRegistry {
    pub protocol_name: ModelRegistryProtocolName,
    pub protocol_version: ModelRegistryProtocolVersion,
    pub models: Option<Vec<SharedModelDescriptor>>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ProductDescriptor {
    pub protocol_name: ProductDescriptorProtocolName,
    pub protocol_version: ProductDescriptorProtocolVersion,
    pub product_id: String,
    pub display_name: String,
    pub product_version: String,
    pub instance_id: String,
    pub product_role: ProductDescriptorProductRole,
    pub protocol_versions: Option<Vec<String>>,
    pub capabilities: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SessionDescriptor {
    pub protocol_name: SessionDescriptorProtocolName,
    pub protocol_version: SessionDescriptorProtocolVersion,
    pub session_id: String,
    pub product_id: String,
    pub instance_id: String,
    pub peer_product_id: String,
    pub peer_instance_id: String,
    pub user_identity: String,
    pub capabilities: Vec<SessionDescriptorCapabilitiesItem>,
    pub nonce: String,
    pub created_at: String,
    pub expires_at: String,
    pub transport: SessionDescriptorTransport,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SessionOpenRequest {
    pub protocol_name: SessionOpenRequestProtocolName,
    pub protocol_version: SessionOpenRequestProtocolVersion,
    pub hello_id: String,
    pub session_nonce: String,
    pub user_identity: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SessionOpenResult {
    pub protocol_name: SessionOpenResultProtocolName,
    pub protocol_version: SessionOpenResultProtocolVersion,
    pub session: SessionDescriptor,
    pub session_token: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SharedModelDescriptor {
    pub runtime_id: String,
    pub model_id: String,
    pub family: String,
    pub modality: Vec<SharedModelDescriptorModalityItem>,
    pub runtime_type: String,
    pub local: bool,
    pub declared_capabilities: Option<Vec<String>>,
    pub verified_capabilities: Option<Vec<String>>,
    pub model_version: Option<String>,
    pub model_hash_if_available: Option<String>,
    pub context_window: Option<u64>,
    pub compatibility: Option<Vec<String>>,
    pub availability: Option<SharedModelDescriptorAvailability>,
    pub last_validated: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TaskRequirement {
    pub task_type: String,
    pub required_modality: Vec<TaskRequirementRequiredModalityItem>,
    pub estimated_context: u64,
    pub privacy: Option<TaskRequirementPrivacy>,
    pub quality_priority: Option<u64>,
    pub latency_priority: Option<u64>,
    pub cost_priority: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TransportRequest {
    pub protocol_name: TransportRequestProtocolName,
    pub protocol_version: TransportRequestProtocolVersion,
    pub operation: TransportRequestOperation,
    pub payload: TransportRequestPayload,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TransportResponse {
    pub protocol_name: TransportResponseProtocolName,
    pub protocol_version: TransportResponseProtocolVersion,
    pub operation: TransportResponseOperation,
    pub payload: TransportResponsePayload,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TutorGuidance {
    pub protocol_name: TutorGuidanceProtocolName,
    pub protocol_version: TutorGuidanceProtocolVersion,
    pub request_id: String,
    pub session_id: String,
    pub guidance_id: String,
    pub summary: String,
    pub diagnosis: String,
    pub steps: Option<Vec<GuidanceStep>>,
    pub warnings: Option<Vec<String>>,
    pub references: Option<Vec<GuidanceReference>>,
    pub verification_condition: Option<VerificationCondition>,
    pub recommended_model: Option<ModelRecommendation>,
    pub privacy_scope: Option<TutorGuidancePrivacyScope>,
    pub created_at: String,
    pub authority: Option<TutorGuidanceAuthority>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TutorRequest {
    pub protocol_name: TutorRequestProtocolName,
    pub protocol_version: TutorRequestProtocolVersion,
    pub request_id: String,
    pub session_id: String,
    pub context: AppContextCapsule,
    pub question: Option<String>,
    pub diagnostic: Option<DiagnosticCapsule>,
    pub task_requirement: Option<TaskRequirement>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct VerificationCondition {
    pub field: VerificationConditionField,
    pub operator: Option<VerificationConditionOperator>,
    pub expected_value: VerificationConditionExpectedValue,
    pub source_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct VerifierRequest {
    pub protocol_name: VerifierRequestProtocolName,
    pub protocol_version: VerifierRequestProtocolVersion,
    pub request_id: String,
    pub session_id: String,
    pub guidance_id: String,
    pub condition: VerificationCondition,
    pub context: AppContextCapsule,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct VerifierResult {
    pub protocol_name: VerifierResultProtocolName,
    pub protocol_version: VerifierResultProtocolVersion,
    pub request_id: String,
    pub session_id: String,
    pub result_id: String,
    pub status: VerifierResultStatus,
    pub reason: String,
    pub evidence: Option<Vec<ContextEvidence>>,
    pub privacy_scope: Option<VerifierResultPrivacyScope>,
    pub created_at: String,
}
