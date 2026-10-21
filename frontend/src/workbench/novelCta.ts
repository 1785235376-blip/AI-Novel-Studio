/**
 * [HERMIA-FE-20261022 N-UX-03] Novel writer primary CTA state machine (LUMEN_NOVEL_IA §3 / gap §5).
 * Single solid primary: adopt draft > continuity warning > continue writing > pick chapter.
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

export function decideNovelPrimaryCta(input: NovelCtaInput): NovelCtaDecision {
  if (input.draftReady) return {kind: 'adopt', label: '采用草稿'};
  if ((input.continuityWarningCount ?? 0) > 0) return {kind: 'continuity', label: '看一致性'};
  if (input.hasChapter) return {kind: 'continue', label: '继续写'};
  return {kind: 'pick-chapter', label: '在左侧选择或新建章节'};
}
