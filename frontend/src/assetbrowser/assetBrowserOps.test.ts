import { describe, expect, it } from 'vitest';
import {
  ASSET_BROWSER_DAY_MS, ASSET_BROWSER_EMPTY_FILTERS, ASSET_BROWSER_MEDIA_KINDS,
  type AssetBrowserAsset, type AssetBrowserFilters, type AssetBrowserReferencedBy, type AssetBrowserRow,
} from './assetBrowserTypes';
import {
  applyFacet, assetBrowserRow, assetBrowserRows, assetDeleteImpact, boundPageSize, checkSendTo, clearFilters,
  compareVersions, countActiveFilters, createdBucket, emptyReferenceCounts, facets, filterRows, hasMoreRows,
  matchesQuery, referenceCounts, referenceIndex, registerModuleReference, rowMatchesFilters, searchableText,
  selectAsset, selectionIsVisible, sendTargetAccepts, sendToReference, sourceVersionImpact, visibleRows,
  withReferenceCounts,
} from './assetBrowserOps';
import { decodeRow, decodeRows, relationshipGraph, sampleAssets } from './assetBrowserFixtures';

const NOW = Date.parse('2026-10-14T12:00:00Z');
const rows = (overrides: Record<string, unknown>[]): AssetBrowserRow[] => assetBrowserRows(decodeRows(overrides), NOW);
const sample = (): AssetBrowserRow[] => assetBrowserRows(sampleAssets(), NOW);
const filters = (patch: Partial<AssetBrowserFilters> = {}): AssetBrowserFilters =>
  ({ ...ASSET_BROWSER_EMPTY_FILTERS, ...patch });

describe('created-time buckets', () => {
  it('derives the bucket from the owner timestamp and never guesses', () => {
    expect(createdBucket('2026-10-14T11:00:00Z', NOW)).toBe('TODAY');
    expect(createdBucket('2026-10-10T11:00:00Z', NOW)).toBe('LAST_7_DAYS');
    expect(createdBucket('2026-10-01T11:00:00Z', NOW)).toBe('LAST_30_DAYS');
    expect(createdBucket('2026-01-01T11:00:00Z', NOW)).toBe('OLDER');
    // 未来时间戳与不可解析的时间都不是"今天"。
    expect(createdBucket('2026-10-20T11:00:00Z', NOW)).toBe('UNRECORDED');
    expect(createdBucket('not-a-date', NOW)).toBe('UNRECORDED');
    expect(ASSET_BROWSER_DAY_MS).toBe(24 * 60 * 60 * 1000);
  });
});

describe('row projection', () => {
  it('starts every row with an unread reference count instead of zero', () => {
    const [row] = rows([{}]);
    expect(row.reference_counts).toBeNull();
    expect(row.created_at_ms).toBe(Date.parse('2026-10-01T00:00:00Z'));
    expect(row.integrity).toBe('VERIFIED');
    expect(row.stale).toBe(false);
    expect(row.media_kind).toBe('image');
  });

  it('keeps missing metadata as unknown rather than defaulting it', () => {
    const [row] = rows([{ provenance: null, tags: [] }]);
    expect(row.integrity).toBeNull();
    expect(row.stale).toBeNull();
    expect(row.license_label).toBeNull();
    expect(row.license_verification).toBeNull();
    expect(row.tags).toEqual([]);
  });

  it('uses parameters.tags only as the owner-declared tag source, never as media kind', () => {
    const [row] = rows([{ id: 'asset-b', kind: 'audio', media_type: 'audio/mpeg', parameters: { tags: ['character'] } }]);
    // `_index_row()` 让 `kind` 保持 owner 的媒体种类：标签不改变它。
    expect(row.media_kind).toBe('audio');
    expect(row.kind).toBe('audio');
    expect(row.tags).toEqual(['character']);
  });
});

describe('facet counts and filtering', () => {
  it('counts every facet from the current row set and keeps zero counts visible', () => {
    const view = facets(sample());
    expect(view.total).toBe(3);
    const image = view.media_kind.find(option => option.value === 'image');
    expect(image?.count).toBe(1);
    expect(image?.label).toBe('图片');
    expect(view.media_kind.find(option => option.value === 'UNKNOWN')?.count).toBe(0);
    expect(view.review_state.find(option => option.value === 'UNREVIEWED')?.count).toBe(3);
    expect(view.tag.find(option => option.value === 'character')?.count).toBe(1);
    expect(view.tag.find(option => option.value === 'UNTAGGED')?.count).toBe(1);
    expect(view.created_bucket.find(option => option.value === 'TODAY')?.count).toBe(1);
    // 引用情况还没读：三行都计入"未核实"，而不是"未被引用"。
    expect(view.reference.find(option => option.value === 'UNVERIFIED')?.count).toBe(3);
    expect(view.reference.find(option => option.value === 'UNREFERENCED')?.count).toBe(0);
    expect(view.reference_unverified).toBe(3);
  });

  it('filters by media kind, tag, review state and time bucket', () => {
    const view = sample();
    expect(filterRows(view, filters({ media_kind: 'image' })).map(row => row.id)).toEqual(['asset-a']);
    expect(filterRows(view, filters({ tag: 'environment' })).map(row => row.id)).toEqual(['asset-b']);
    expect(filterRows(view, filters({ review_state: 'UNREVIEWED' }))).toHaveLength(3);
    expect(filterRows(view, filters({ review_state: 'APPROVED' }))).toHaveLength(0);
    expect(filterRows(view, filters({ created_bucket: 'OLDER' })).map(row => row.id)).toEqual(['asset-c']);
    expect(filterRows(view, filters({ created_bucket: 'TODAY' })).map(row => row.id)).toEqual(['asset-a']);
  });

  it('never treats an unread reference count as zero', () => {
    const unread = sample();
    // 未读时既不匹配 REFERENCED 也不匹配 UNREFERENCED。
    expect(filterRows(unread, filters({ reference: 'REFERENCED' }))).toHaveLength(0);
    expect(filterRows(unread, filters({ reference: 'UNREFERENCED' }))).toHaveLength(0);
    expect(filterRows(unread, filters({ reference: 'UNVERIFIED' }))).toHaveLength(3);

    const index = referenceIndex(relationshipGraph());
    const read = withReferenceCounts(unread, index);
    expect(filterRows(read, filters({ reference: 'REFERENCED' })).map(row => row.id)).toEqual(['asset-a']);
    expect(filterRows(read, filters({ reference: 'UNREFERENCED' })).map(row => row.id)).toEqual(['asset-b', 'asset-c']);
    expect(filterRows(read, filters({ reference: 'UNVERIFIED' }))).toHaveLength(0);
  });

  it('applies facets, clears them and keeps the search term', () => {
    const start = filters({ media_kind: 'image', tag: 'character', review_state: 'APPROVED' });
    expect(countActiveFilters(start)).toBe(3);
    expect(applyFacet(start, 'tag', null).tag).toBeNull();
    const cleared = clearFilters({ ...start, query: 'cover' });
    expect(cleared.query).toBe('cover');
    expect(countActiveFilters(cleared)).toBe(0);
  });
});

describe('search over authorized metadata only', () => {
  it('matches the name and the disclosed metadata', () => {
    const [row] = rows([{ filename: 'cover.png', tags: ['character'] }]);
    expect(matchesQuery(row, 'cover')).toBe(true);
    expect(matchesQuery(row, 'cover.png')).toBe(true);
    expect(matchesQuery(row, 'image/png')).toBe(true);
    expect(matchesQuery(row, '角色')).toBe(true);
    expect(matchesQuery(row, '图片')).toBe(true);
    expect(matchesQuery(row, 'image')).toBe(true);
    expect(matchesQuery(row, '   ')).toBe(true);
    expect(matchesQuery(row, 'shots')).toBe(false);
  });

  it('never reaches into undisclosed parameters, content or paths', () => {
    const asset = decodeRow({ filename: 'cover.png', parameters: { hidden_note: 'secret-plan', prompt: 'a hidden prompt' } });
    const row = assetBrowserRow(asset, NOW);
    const text = searchableText(row);
    expect(text).not.toContain('secret-plan');
    expect(text).not.toContain('a hidden prompt');
    expect(matchesQuery(row, 'secret-plan')).toBe(false);
    expect(matchesQuery(row, 'hidden prompt')).toBe(false);
    // 搜索面是一个纯字符串：搜索本身不会发起任何读取。
    expect(typeof text).toBe('string');
  });

  it('searches the disclosed provenance labels but never invents unavailable ones', () => {
    const [row] = rows([{ filename: 'cover.png', provenance: { integrity: 'VERIFIED', stale: false,
      license: { label: 'AUTHOR_ONLY', source: '', note: '' },
      license_verification: 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION', parents: [], sources: [] } }]);
    expect(matchesQuery(row, 'AUTHOR_ONLY')).toBe(true);
    expect(row.license_label).toBe('AUTHOR_ONLY');
    // 作者声明不等于商用授权：契约里没有"已授权"这种字段可以搜到。
    expect(matchesQuery(row, '商用授权')).toBe(false);
  });
});

describe('reference counts and the referenced-by index', () => {
  it('maps every declared and lineage edge onto the referenced asset', () => {
    const index = referenceIndex(relationshipGraph());
    const onA = index.get('asset-a') ?? [];
    // asset-b 声明引用 + asset-b 的原始来源边。
    expect(onA.map(entry => entry.relationship).sort()).toEqual(['DERIVED_FROM', 'REFERENCES']);
    expect(onA.every(entry => entry.group === 'UNKNOWN')).toBe(true);
    // UNAVAILABLE 边没有可核实的目标 id，因此不会被算进任何资产的引用列表。
    expect([...index.values()].flat().some(entry => entry.id === 'asset-a' && entry.relationship === 'REFERENCES'
      && entry.kind === 'UNKNOWN' && entry.state === 'UNAVAILABLE')).toBe(false);
    // 非资产目标（剧本）仍然被计数，但它属于"谁引用了剧本"，不是"谁引用了素材"。
    expect(index.get('script-1')?.map(entry => entry.id)).toEqual(['asset-c']);
  });

  it('counts by kind, relationship and non-current state', () => {
    const index = referenceIndex(relationshipGraph());
    const counts = referenceCounts(index.get('asset-a') ?? []);
    expect(counts.total).toBe(2);
    expect(counts.by_kind.ASSET).toBe(2);
    expect(counts.by_relationship.DERIVED_FROM).toBe(1);
    expect(counts.by_relationship.REFERENCES).toBe(1);
    expect(counts.not_current).toBe(1);
    expect(emptyReferenceCounts().total).toBe(0);
    expect(emptyReferenceCounts().not_current).toBe(0);
  });

  it('accepts a caller-verified module group and otherwise keeps UNKNOWN', () => {
    const seeded = registerModuleReference(referenceIndex(relationshipGraph()), 'asset-a', {
      id: 'shot-7', kind: 'ASSET', group: 'SHOTS', label: '镜头 7', relationship: 'USED_IN',
      bound_version: 2, bound_digest: 'e'.repeat(64),
    });
    const onA = seeded.get('asset-a') ?? [];
    expect(onA.some(entry => entry.group === 'SHOTS' && entry.id === 'shot-7')).toBe(true);
    // 没有回传的边仍然是未核实，绝不从 id 猜分组。
    expect(onA.filter(entry => entry.group === 'UNKNOWN')).toHaveLength(2);
  });
});

describe('pagination and the shared selection model', () => {
  it('bounds the page size and never fetches unbounded', () => {
    expect(boundPageSize(0)).toBe(8);
    expect(boundPageSize(24)).toBe(24);
    expect(boundPageSize(10_000)).toBe(200);
    expect(boundPageSize(Number.NaN)).toBe(24);
  });

  it('slices only visible rows and reports whether more remain', () => {
    const view = sample();
    expect(visibleRows(view, 2).map(row => row.id)).toEqual(['asset-a', 'asset-b']);
    expect(hasMoreRows(view, 2)).toBe(true);
    expect(hasMoreRows(view, 3)).toBe(false);
  });

  it('shares one selection between grid and list without dropping an off-page choice', () => {
    const selected = selectAsset({ selectedId: null, anchorId: null }, 'asset-c');
    expect(selected.selectedId).toBe('asset-c');
    expect(selectionIsVisible(sample(), 1, selected)).toBe(false);
    expect(selectionIsVisible(sample(), 3, selected)).toBe(true);
    expect(selectAsset(selected, null)).toEqual({ selectedId: null, anchorId: null });
  });
});

describe('send-to reference', () => {
  it('emits only the original asset identity triple', () => {
    const [row] = rows([{ id: 'asset-a', version: 3, sha256: 'f'.repeat(64) }]);
    expect(sendToReference(row)).toEqual({ asset_id: 'asset-a', version: 3, digest: 'f'.repeat(64) });
    expect(Object.keys(sendToReference(row) as object).sort()).toEqual(['asset_id', 'digest', 'version']);
  });

  it('refuses to invent a version', () => {
    const [row] = rows([{ version: 3 }]);
    expect(sendToReference({ ...row, version: null })).toBeNull();
    const verdict = checkSendTo({ ...row, version: null }, 'IMAGE');
    expect(verdict.allowed).toBe(false);
    expect(verdict.allowed === false && verdict.reason).toBe('NO_VERSION');
  });

  it('pre-checks the target media kind without executing anything', () => {
    const view = sample();
    const audio = view.find(row => row.id === 'asset-b') as AssetBrowserRow;
    const toImage = checkSendTo(audio, 'IMAGE');
    expect(toImage.allowed).toBe(false);
    expect(toImage.allowed === false ? toImage.reason : 'ALLOWED').toBe('MEDIA_KIND_MISMATCH');
    expect(checkSendTo(audio, 'TIMELINE').allowed).toBe(true);
    expect(sendTargetAccepts('IMAGE')).toBe('图片');
    expect(sendTargetAccepts('TIMELINE')).toBe('图片 / 视频 / 音频');
    const unknownKind = { ...audio, media_kind: null } as AssetBrowserRow;
    const verdict = checkSendTo(unknownKind, 'TIMELINE');
    expect(verdict.allowed).toBe(false);
    expect(verdict.allowed === false ? verdict.reason : 'ALLOWED').toBe('MEDIA_KIND_UNKNOWN');
  });
});

describe('compareVersions', () => {
  it('reports same / different / unverifiable per field explicitly', () => {
    const left = decodeRow({ version: 2, sha256: 'a'.repeat(64), filename: 'cover.png' });
    const right = decodeRow({ version: 3, sha256: 'b'.repeat(64), filename: 'cover-v3.png' });
    const result = compareVersions(left, right);
    const byField = Object.fromEntries(result.entries.map(entry => [entry.field, entry.verdict]));
    expect(byField.version).toBe('DIFFERENT');
    expect(byField.digest).toBe('DIFFERENT');
    expect(byField.filename).toBe('DIFFERENT');
    expect(byField.kind).toBe('SAME');
    expect(byField.media_type).toBe('SAME');
    expect(byField.license_label).toBe('SAME');
    expect(result.changed).toContain('version');
    expect(result.changed).toContain('digest');
    expect(result.differs).toBe(true);
    expect(result.identical).toBe(false);
    expect(result.content_differs).toBe(true);
    expect(result.same_asset).toBe(true);
    // 每个字段都必须有显式结论，不存在"漏掉"的字段。
    expect(result.entries).toHaveLength(18);
  });

  it('marks a one-sided disclosure as unverifiable instead of "same"', () => {
    const left = decodeRow({ provenance: null });
    const right = decodeRow({ provenance: { integrity: 'VERIFIED', stale: false, origin: 'EXTERNAL_IMPORT',
      license: { label: 'UNSPECIFIED', source: '', note: '' },
      license_verification: 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION', parents: [], sources: [] } });
    const result = compareVersions(left, right);
    const integrity = result.entries.find(entry => entry.field === 'integrity');
    expect(integrity?.verdict).toBe('UNVERIFIABLE');
    expect(integrity?.left).toBeNull();
    expect(integrity?.right).toBe('VERIFIED');
    expect(result.unverifiable).toContain('integrity');
    expect(result.changed).not.toContain('integrity');
    // 没有任何字段被核实为不同 + 有无法核实的字段 ⇒ 不能声称"完全相同"。
    expect(result.differs).toBe(false);
    expect(result.changed).toHaveLength(0);
    expect(result.unverifiable.length).toBeGreaterThan(0);
  });

  it('does not claim content identity when a digest is missing', () => {
    const left = decodeRow({});
    const right = decodeRow({});
    expect(compareVersions(left, right).content_differs).toBe(false);
    expect(compareVersions(left, { ...right, digest: '' }).content_differs).toBeNull();
  });
});

describe('sourceVersionImpact', () => {
  const current = { asset_id: 'asset-a', version: 3, digest: 'a'.repeat(64) };

  it('reports unknown relationships as unverified instead of dropping them', () => {
    const index = referenceIndex(relationshipGraph());
    const impact = sourceVersionImpact(current, index.get('asset-a') ?? []);
    const unknownGroup = impact.groups.find(group => group.group === 'UNKNOWN');
    expect(unknownGroup?.items).toHaveLength(2);
    expect(unknownGroup?.unverified).toBe(2);
    expect(impact.automatic_update).toBe(false);
    expect(impact.unverified_is_not_absent).toBe(true);
    expect(impact.versions_comparable).toBe(true);
  });

  it('flags only the references that need a user decision', () => {
    const entries: AssetBrowserReferencedBy[] = [
      { id: 'asset-b', kind: 'ASSET', group: 'SHOTS', label: '镜头 7', relationship: 'USED_IN', state: 'CURRENT',
        bound_version: 2, bound_digest: 'b'.repeat(64) },
      { id: 'asset-c', kind: 'ASSET', group: 'TIMELINES', label: '主时间线', relationship: 'USED_IN', state: 'CURRENT',
        bound_version: 3, bound_digest: 'a'.repeat(64) },
      { id: 'asset-d', kind: 'ASSET', group: 'NODES', label: '节点', relationship: 'REFERENCES', state: 'UNAVAILABLE',
        bound_version: null, bound_digest: null },
    ];
    const impact = sourceVersionImpact(current, entries);
    const byGroup = (group: string) => impact.groups.find(item => item.group === group);
    expect(byGroup('SHOTS')?.needs_decision).toBe(1);
    expect(byGroup('SHOTS')?.items[0].matches_current).toBe(false);
    expect(byGroup('TIMELINES')?.needs_decision).toBe(0);
    expect(byGroup('TIMELINES')?.items[0].matches_current).toBe(true);
    expect(byGroup('NODES')?.items[0].matches_current).toBeNull();
    expect(byGroup('NODES')?.unverified).toBe(1);
    expect(impact.total).toBe(3);
    // 三条引用都必须出现在分组里：未核实 ≠ 不存在。
    expect(impact.groups.flatMap(group => group.items)).toHaveLength(3);
  });

  it('cannot compare versions when the owner disclosed no bound version', () => {
    const impact = sourceVersionImpact(current, [{ id: 'asset-b', kind: 'ASSET', group: 'UNKNOWN', label: null,
      relationship: 'DERIVED_FROM', state: 'STALE', bound_version: null, bound_digest: null }].map(entry => entry as AssetBrowserReferencedBy));
    expect(impact.versions_comparable).toBe(false);
    expect(impact.groups.flatMap(group => group.items)[0].matches_current).toBeNull();
  });
});

describe('assetDeleteImpact', () => {
  it('never claims a physical delete and refuses to hide unknown references', () => {
    const [row] = rows([{ id: 'asset-a' }]);
    const index = referenceIndex(relationshipGraph());
    const impact = assetDeleteImpact(row, index.get('asset-a') ?? []);
    expect(impact.physical_delete).toBe(false);
    expect(impact.content_removed).toBe(false);
    // 两条引用都会被 owner 视为"仍在使用"。
    expect(impact.blocking_total).toBe(2);
    expect(impact.refusable_by_owner).toBe(true);
    expect(impact.unverified_total).toBe(2);
    expect(impact.message).toContain('软删除');
  });

  it('still reports soft delete semantics when there is no reference at all', () => {
    const [row] = rows([{ id: 'asset-c' }]);
    const impact = assetDeleteImpact(row, []);
    expect(impact.blocking_total).toBe(0);
    expect(impact.refusable_by_owner).toBe(false);
    expect(impact.physical_delete).toBe(false);
    expect(impact.reported.automatic_update).toBe(false);
  });

  it('does not count an already-deleted reference as blocking', () => {
    const [row] = rows([{ id: 'asset-a' }]);
    const impact = assetDeleteImpact(row, [{ id: 'asset-b', kind: 'ASSET', group: 'UNKNOWN', label: null,
      relationship: 'REFERENCES', state: 'DELETED', bound_version: 3, bound_digest: 'a'.repeat(64) }]);
    expect(impact.blocking_total).toBe(0);
    expect(impact.reported.total).toBe(1);
  });
});

describe('row/filter plumbing', () => {
  it('keeps media-kind and tag filters independent of the kind label', () => {
    const view = rows([{ id: 'asset-x', kind: 'other', media_type: 'application/pdf', tags: ['prop'] }]);
    expect(ASSET_BROWSER_MEDIA_KINDS).toEqual(['image', 'video', 'audio']);
    expect(view[0].media_kind).toBeNull();
    expect(rowMatchesFilters(view[0], filters({ media_kind: 'image' }))).toBe(false);
    expect(rowMatchesFilters(view[0], filters({ tag: 'prop' }))).toBe(true);
    const view2 = facets(view);
    expect(view2.media_kind.find(option => option.value === 'UNKNOWN')?.count).toBe(1);
    expect(view2.media_kind.find(option => option.value === 'UNKNOWN')?.label).toBe('未核实');
  });
});
