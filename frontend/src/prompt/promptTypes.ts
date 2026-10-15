/**
 * R3-U Prompt Workspace —— 契约常量与类型。
 *
 * 这里**没有**第二套资产/版本/审核系统：前端只消费 R3-W 已经冻结的写入契约，
 * 以及 Round 3 只读投影。
 */

export const PROMPT_CONTRACT = 'prompt-library/1';
export const PROMPT_DETAIL_CONTRACT = 'prompt-library/1';

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

export type PromptBindingRow = { id: string; resolution: 'KNOWN' | 'UNKNOWN'; label: string | null };
export type PromptBindings = {
  characters: PromptBindingRow[];
  scenes: PromptBindingRow[];
  shots: PromptBindingRow[];
  assets: PromptBindingRow[];
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
  createPrompt(body: PromptCreateRequest): Promise<PromptReceipt>;
  saveRevision(familyId: string, body: PromptRevisionRequest): Promise<PromptReceipt>;
  approveRevision(familyId: string, assetId: string, expectedVersion: number): Promise<unknown>;
};
