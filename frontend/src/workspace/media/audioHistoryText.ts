// [HERMIA-FE-CONTRACTS G-AUD-5] zh-only (no i18n layer on this base). Backend semantics:
// POST /studio/assets/{id}/restore is UNDELETE (version increments), not a rollback; only Timeline has version history.
export const AUDIO_HISTORY_TEXT = {
  assetRestore: '撤销删除',
  assetRestoreHint: '“撤销删除”只是把回收站里的资产放回来，不是回到旧版本。',
  timelineOnly: '只有时间线有版本历史，可以在时间线里查看并恢复到某个版本。',
  assetHistory: '单个素材的版本历史暂不支持。',
} as const;
