// Browser-to-Host projection only; the frozen Interop schema stays unchanged.
// A label grants nothing: the Host resolves against live exact-scope owner rows.
export type ChapterScope = { workspace_id: string; project_id: string; storyline_id: string; branch_id: string };
const wireId = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;

export async function chapterWireId(scope: ChapterScope | undefined, nativeId: string): Promise<string> {
  if (nativeId.match(wireId)?.[0] === nativeId) return nativeId;
  if (!nativeId || !scope || !Object.values(scope).every(value => typeof value === 'string' && value.length > 0))
    throw new Error('CHAPTER_SCOPE_REQUIRED');
  // Canonical tuple shared with app/local_interop/chapter_ids.py. Full SHA-256,
  // no numeric aliases, reversible encodings, cached identities or persistence.
  const value = JSON.stringify(['studio-chapter-v1', scope.workspace_id, scope.project_id, scope.storyline_id, scope.branch_id, nativeId]);
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return `chapter-${Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, '0')).join('')}`;
}
