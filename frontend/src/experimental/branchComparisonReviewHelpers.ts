// Display projection only. Original rich-block diff and merge decisions remain authoritative.
export type BranchReference = { id?: string; version: number; document_digest?: string; branch_id?: string | null; is_archived?: boolean };
export type BranchComparison = { can_apply: boolean; preview_digest: string; source: BranchReference; target: BranchReference; conflicts: { id: string; reason?: string; base?: unknown; ORIGINAL?: unknown; FORK?: unknown }[]; segments: unknown[]; desired_document: unknown };
export const branchSegmentLabels: Record<string, string> = { UNCHANGED: '双方未改动', ORIGINAL_ONLY: '仅当前来源改动', FORK_ONLY: '仅当前分支改动', BOTH_SAME: '双方改动一致', CONFLICT: '双方改动冲突' };
export function branchSegment(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
export function branchBlockExcerpt(value: unknown): { text: string; limited: boolean } {
  if (!Array.isArray(value)) return { text: '未提供此侧正文', limited: false };
  if (!value.length) return { text: '此侧为空（插入或删除边界）', limited: false };
  const stack: unknown[] = value.slice(0, 512).reverse();
  let visited = 0, text = '', limited = value.length > 512;
  while (stack.length && visited < 512 && text.length < 2400) {
    const node = branchSegment(stack.pop()); visited++;
    if (node.type === 'text' && typeof node.text === 'string') {
      const remaining = 2400 - text.length;
      if (node.text.length > remaining) limited = true;
      const chunk = node.text.slice(0, remaining);
      text += /[\uD800-\uDBFF]$/.test(chunk) ? chunk.slice(0, -1) : chunk;
    }
    else if (node.type === 'hardBreak') text += '\n';
    if (Array.isArray(node.content)) {
      const available = Math.max(0, 512 - visited - stack.length);
      if (node.content.length > available) limited = true;
      stack.push(...node.content.slice(0, available).reverse());
    }
    if (node.type === 'paragraph' || node.type === 'heading') text += '\n';
  }
  const points = Array.from(text.trim());
  limited ||= stack.length > 0 || points.length > 600;
  return { text: points.slice(0, 600).join('') || '没有可显示的纯文本；请查看完整富文本块', limited };
}
