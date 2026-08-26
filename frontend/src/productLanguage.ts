export type AiOperation = 'continue' | 'rewrite' | 'polish' | 'brainstorm' | 'review';
export type GenerationStatus = 'QUEUED' | 'GENERATING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'ACCEPTED' | 'REJECTED';
export type DomainRole = 'ADMIN' | 'DOMAIN_LEAD' | 'MEMBER';
export type PermissionName = 'domain.read' | 'domain.write' | 'proposal.create' | 'proposal.review';
export type ScopeKind = 'WORKSPACE' | 'PROJECT' | 'STORYLINE' | 'BRANCH' | 'CHAPTER';
export type RevisionReason = 'MANUAL_SAVE' | 'AI_ACCEPT' | 'RESTORE' | 'CHAPTER_SWITCH' | 'EXPLICIT_CHECKPOINT';
export type AuthorityKind = 'ROLE' | 'DIRECT';

export const aiOperationLabels: Record<AiOperation, string> = {
  continue: '续写',
  rewrite: '改写',
  polish: '润色',
  brainstorm: '头脑风暴',
  review: '审阅',
};

export const generationStatusLabels: Record<GenerationStatus, string> = {
  QUEUED: '等待生成',
  GENERATING: '生成中',
  COMPLETED: '生成完成',
  FAILED: '生成失败',
  CANCELLED: '已取消',
  ACCEPTED: '已接受',
  REJECTED: '已拒绝',
};

export const domainRoleLabels: Record<DomainRole, string> = {
  ADMIN: '管理员',
  DOMAIN_LEAD: '小说负责人',
  MEMBER: '成员',
};

export const permissionLabels: Record<PermissionName, string> = {
  'domain.read': '查看小说内容',
  'domain.write': '编辑小说内容',
  'proposal.create': '创建写作提案',
  'proposal.review': '审核写作提案',
};

export const scopeKindLabels: Record<ScopeKind, string> = {
  WORKSPACE: '创作空间',
  PROJECT: '小说',
  STORYLINE: '故事线',
  BRANCH: '创作分支',
  CHAPTER: '章节',
};

export const revisionReasonLabels: Record<RevisionReason, string> = {
  MANUAL_SAVE: '手动保存',
  AI_ACCEPT: '接受 AI 草稿',
  RESTORE: '恢复历史版本',
  CHAPTER_SWITCH: '切换章节时保存',
  EXPLICIT_CHECKPOINT: '创建版本节点',
};

export const authorityKindLabels: Record<AuthorityKind, string> = {
  ROLE: '角色权限',
  DIRECT: '单独授予',
};

function mappedLabel<T extends string>(labels: Readonly<Record<T, string>>, value: string): string {
  return Object.prototype.hasOwnProperty.call(labels, value) ? labels[value as T] : value;
}

export const aiOperationLabel = (value: string) => mappedLabel(aiOperationLabels, value);
export const generationStatusLabel = (value: string) => mappedLabel(generationStatusLabels, value);
export const domainRoleLabel = (value: string) => mappedLabel(domainRoleLabels, value);
export const permissionLabel = (value: string) => mappedLabel(permissionLabels, value);
export const scopeKindLabel = (value: string) => mappedLabel(scopeKindLabels, value);
export const revisionReasonLabel = (value: string) => mappedLabel(revisionReasonLabels, value);
export const authorityKindLabel = (value: string) => mappedLabel(authorityKindLabels, value);
