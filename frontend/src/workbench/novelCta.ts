/**
 * [HERMIA-FE-20261022 N-UX-08] Novel writer primary CTA state machine
 * (LUMEN_NOVEL_IA §3 / gap G-NOV-03).
 * Single solid primary: adopt draft > continuity warning > continue writing > pick chapter.
 * Labels are author language only — 继续写 / 采用草稿 / 看一致性.
 */
export type NovelCtaKind = 'adopt' | 'continuity' | 'continue' | 'pick-chapter';

export interface NovelCtaInput {
  draftReady: boolean;
  continuityWarningCount?: number;
  hasChapter: boolean;
}

export interface NovelCtaDecision {
  kind: NovelCtaKind;
  label: string;
}

/** Count open continuity findings honestly — RESOLVED excluded; empty/error → 0 (no fake warnings). */
export function countOpenContinuityWarnings(
  findings: Array<{status?: string} | null | undefined> | null | undefined,
): number {
  if (!findings?.length) return 0;
  return findings.filter(row => {
    if (!row) return false;
    return String(row.status || '').toUpperCase() !== 'RESOLVED';
  }).length;
}

export function decideNovelPrimaryCta(input: NovelCtaInput): NovelCtaDecision {
  if (input.draftReady) return {kind: 'adopt', label: '采用草稿'};
  if ((input.continuityWarningCount ?? 0) > 0) return {kind: 'continuity', label: '看一致性'};
  if (input.hasChapter) return {kind: 'continue', label: '继续写'};
  return {kind: 'pick-chapter', label: '在左侧选择或新建章节'};
}
