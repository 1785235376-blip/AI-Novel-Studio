/**
 * R3-U Prompt Workspace —— 契约常量与类型。
 *
 * 这里**没有**第二套资产/版本/审核系统：前端只消费 R3-W 已经冻结的写入契约，
 * 以及 Round 3 只读投影。
 */

/**
 * 生产者契约常量。以**真实后端响应**为准（`scripts/capture_prompt_contract_fixture.py`
 * 会重新采集），library 与 detail 是**两个不同的**常量，不能共用一个。
 */
export const PROMPT_CONTRACT = 'studio-prompt-library/1';
export const PROMPT_DETAIL_CONTRACT = 'studio-prompt-detail/1';
export const PROMPT_REVISION_BODY_CONTRACT = 'prompt-revision-body/1';

/** 采集时生产者在用的全部契约字面值，用于拒绝未知契约而不是静默接受。 */
export const KNOWN_PROMPT_CONTRACTS = [
  PROMPT_CONTRACT, PROMPT_DETAIL_CONTRACT, PROMPT_REVISION_BODY_CONTRACT,
] as const;

/** 绑定行的核实来源。`INDEX_SUPPLIED` 只是“索引里查到了”，**不是**已审批或保存时校验。 */
export const BINDING_VERIFICATIONS = ['INDEX_SUPPLIED', 'UNKNOWN'] as const;
export type BindingVerification = (typeof BINDING_VERIFICATIONS)[number];

/** 未知（后端明确标注的 UNKNOWN）永远不等于空字符串。 */
export const UNKNOWN = 'UNKNOWN';

export const PROMPT_BOUNDS = {
  identifier: 240,
  fieldCount: 64,
  versions: 2000,
  bindings: 500,
  anomalies: 200,
  /** 正文的最长字节数（与 owner 的 64 KiB 上限一致）。 */
  textBytes: 64 * 1024,
} as const;

export const PROMPT_ERROR_CODES = {
  responseInvalid: 'PROMPT_RESPONSE_INVALID',
  scopeMismatch: 'PROMPT_SCOPE_MISMATCH',
  conflict: 'PROMPT_CONFLICT',
  unknownOutcome: 'PROMPT_OUTCOME_UNKNOWN',
} as const;

/** 正文状态。TRUNCATED / UNDECODABLE / REDACTED 都不是“完整正文”。 */
export type BodyState = 'COMPLETE' | 'TRUNCATED' | 'UNDECODABLE' | 'REDACTED' | 'DELETED' | 'UNAVAILABLE';

export type PromptBody = {
  state: BodyState;
  /** 只有 COMPLETE 才是完整正文；其它状态一律为预览、脱敏或不可读。 */
  value: string | null;
  digest: string | null;
  truncated: boolean;
  decodable: boolean;
  originalLength: number | null;
  fetch: string;
};

export type PromptField = {
  field: string;
  label: string;
  value: unknown;
  authored: boolean;
  state: 'KNOWN' | 'UNKNOWN';
};

export type PromptVersionRow = {
  assetId: string;
  revision: number;
  assetVersion: number | null;
  changeNote: string | null;
  changeReason: string | null;
  previousAssetId: string | null;
  redacted: boolean;
  available: boolean;
};

export type PromptBindingRow = {
  /** 绑定类别，例如 CHARACTER，由生产者给出。 */
  kind: string;
  id: string;
  resolution: 'KNOWN' | 'UNKNOWN';
  /** 核实来源；`INDEX_SUPPLIED` 仅表示索引中存在该目标。 */
  verification: BindingVerification;
};
export type PromptBindings = {
  characters: PromptBindingRow[];
  scenes: PromptBindingRow[];
  shots: PromptBindingRow[];
  assets: PromptBindingRow[];
  /** 整组绑定的核实来源，与行级字段一致。 */
  verification: BindingVerification;
};

/** R3-U2 单修订正文读取的返回契约。 */
export type PromptRevisionBody = {
  familyId: string;
  assetId: string;
  revision: number;
  assetVersion: number | null;
  state: BodyState;
  value: string | null;
  truncated: boolean;
  decodable: boolean;
  digest: string | null;
  digestOf: string | null;
  originalLength: number | null;
  available: boolean;
  /** 与 owner 记录的原字节 SHA-256 一致才为 true。 */
  verified: boolean;
  readComplete: boolean;
};

export type PromptAnomaly = { kind: string; detail: string };

export type PromptEntry = {
  familyId: string;
  headAssetId: string;
  revision: number;
  assetVersion: number | null;
  purpose: string;
  origin: string;
  reviewStatus: 'DRAFT' | 'APPROVED';
  approved: boolean;
  redacted: boolean;
  body: PromptBody;
  bindings: PromptBindings;
  unresolvedBindings: string[];
  referenceAssetIds: string[];
  outputAssetIds: string[];
  anomalies: PromptAnomaly[];
  versions: PromptVersionRow[];
  fields: PromptField[];
  /** 家族链是否完整可读；false 时“最新版本”不是权威结论。 */
  historyComplete: boolean;
  readComplete: boolean;
};

export type PromptLibrary = {
  entries: PromptEntry[];
  promptCount: number;
  revisionCount: number;
  malformedCount: number;
  conflicted: { assetId: string; familyId: string; revision: number }[];
  conflictedCount: number;
  scannedAssets: number;
  projectedFamilies: number;
  limit: number | null;
  truncated: boolean;
  hasMore: boolean;
  totalKnown: boolean;
  readComplete: boolean;
};

/** R3-W 写入回执。`asset_id` 属于回执，**不是** library entry 的字段。 */
export type PromptReceipt = {
  familyId: string;
  assetId: string;
  revision: number;
  assetVersion: number | null;
  textDigest: string;
  idempotentReplay: boolean;
  previousAssetId: string | null;
};

/** R3-W 白名单冲突体。后端只允许这些字段跨过边界。 */
export type PromptConflict = {
  code: string;
  familyId: string | null;
  revision: number | null;
  expectedRevision: number | null;
  currentRevision: number | null;
  retryable: boolean;
};

export type PromptCreateRequest = {
  text: string;
  negative_prompt: string;
  purpose: 'IMAGE' | 'VIDEO' | 'AUDIO' | 'TEXT';
  origin: 'MANUAL' | 'AI_GENERATED' | 'IMPORTED';
  model_reference: string;
  parameters: Record<string, unknown>;
  seed: number | null;
  character_ids: string[];
  scene_ids: string[];
  shot_ids: string[];
  reference_asset_ids: string[];
  change_note: string;
  change_reason: string;
  redacted: boolean;
  request_id: string;
};

export type PromptRevisionRequest = PromptCreateRequest & {
  expected_previous_asset_id: string;
  expected_revision: number;
};

export type PromptWorkspaceClient = {
  readLibrary(signal?: AbortSignal): Promise<PromptLibrary>;
  readFamily(familyId: string, signal?: AbortSignal): Promise<PromptEntry>;
  /** R3-U2：单个修订的**真实**正文，只有它才能支撑真正的正文比较。 */
  readRevisionBody(familyId: string, assetId: string, signal?: AbortSignal): Promise<PromptRevisionBody>;
  createPrompt(body: PromptCreateRequest): Promise<PromptReceipt>;
  saveRevision(familyId: string, body: PromptRevisionRequest): Promise<PromptReceipt>;
  approveRevision(familyId: string, assetId: string, expectedVersion: number): Promise<unknown>;
};
