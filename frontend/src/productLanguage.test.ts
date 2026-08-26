import {describe, expect, it} from 'vitest';
import {
  aiOperationLabel,
  aiOperationLabels,
  authorityKindLabel,
  authorityKindLabels,
  domainRoleLabel,
  domainRoleLabels,
  generationStatusLabel,
  generationStatusLabels,
  permissionLabel,
  permissionLabels,
  revisionReasonLabel,
  revisionReasonLabels,
  scopeKindLabel,
  scopeKindLabels,
} from './productLanguage';

describe('product language', () => {
  it('maps every AI operation and generation state to Chinese product language', () => {
    expect(aiOperationLabels).toEqual({continue: '续写', rewrite: '改写', polish: '润色', brainstorm: '头脑风暴', review: '审阅'});
    expect(generationStatusLabels).toEqual({QUEUED: '等待生成', GENERATING: '生成中', COMPLETED: '生成完成', FAILED: '生成失败', CANCELLED: '已取消', ACCEPTED: '已接受', REJECTED: '已拒绝'});
  });

  it('maps authorization concepts without changing their protocol values', () => {
    expect(domainRoleLabels).toEqual({ADMIN: '管理员', DOMAIN_LEAD: '小说负责人', MEMBER: '成员'});
    expect(permissionLabels).toEqual({'domain.read': '查看小说内容', 'domain.write': '编辑小说内容', 'proposal.create': '创建写作提案', 'proposal.review': '审核写作提案'});
    expect(authorityKindLabels).toEqual({ROLE: '角色权限', DIRECT: '单独授予'});
  });

  it('maps scope and revision semantics', () => {
    expect(scopeKindLabels).toEqual({WORKSPACE: '创作空间', PROJECT: '小说', STORYLINE: '故事线', BRANCH: '创作分支', CHAPTER: '章节'});
    expect(revisionReasonLabels).toEqual({MANUAL_SAVE: '手动保存', AI_ACCEPT: '接受 AI 草稿', RESTORE: '恢复历史版本', CHAPTER_SWITCH: '切换章节时保存', EXPLICIT_CHECKPOINT: '创建版本节点'});
  });

  it('keeps unknown future backend values visible instead of mislabelling them', () => {
    expect(aiOperationLabel('future-operation')).toBe('future-operation');
    expect(generationStatusLabel('PAUSED')).toBe('PAUSED');
    expect(domainRoleLabel('GUEST')).toBe('GUEST');
    expect(permissionLabel('domain.delete')).toBe('domain.delete');
    expect(scopeKindLabel('VOLUME')).toBe('VOLUME');
    expect(revisionReasonLabel('IMPORT')).toBe('IMPORT');
    expect(authorityKindLabel('INHERITED')).toBe('INHERITED');
  });
});
