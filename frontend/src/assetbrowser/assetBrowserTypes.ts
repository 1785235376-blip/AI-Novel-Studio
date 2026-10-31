/**
 * UX-03 素材浏览器 / Asset Browser —— 冻结词表、数据形状与有界取值。
 *
 * 这个目录是**消费者**。下面每一个字段都逐条来自真实原 owner，本文件不新增
 * 第二个资产 owner、第二个版本 owner、第二个关联 owner，也不复制磁盘扫描：
 *
 * - 资产列表 / 单资产 DTO 抄自 `frontend/src/creative/studioClient.ts` 的
 *   `assets()` 与 `asset()`（它们是既有消费者 `IndependentStudioWorkspace.tsx`
 *   的读取入口），其服务端投影是
 *   `app/creative/workspace.py::IndependentWorkspaceService._view()` →
 *   `app/services/asset_library_service.py::AssetLibraryService.public()`
 *   （`public()` 剥掉 `_required_features` / `_owner_actor_id` /
 *   `_origin_provenance` / `_project_binding` / `_text_result_origin` /
 *   `_text_result_review` / `_text_execution_receipt` / `_studio_result_origin` /
 *   `_manual_mask_origin`，并且总是剥掉
 *   `parameters.asset_relationships_v2`、在 A09 关闭时剥掉
 *   `parameters.asset_lineage_v2`；本消费者因此**看不到**审核标记，也**不能**
 *   用它去猜审核状态）。
 * - `review_state` 抄自 `workspace.py::_index_row()`：它只从 owner 自己存的
 *   `_text_result_review.status` 取值，且只在 `{DRAFT, APPROVED, REJECTED}` 内，
 *   其余一律 `None`。`_index_row()` 明确写了「media candidate review is job-level
 *   and deliberately not invented here」，所以这里同样**绝不**用生成任务的状态
 *   去补一个审核结论：没有 owner 标记就是 `UNREVIEWED`。
 * - `review_status` 的元数据来源是 `GET /projects/{nid}/studio/assets/{aid}/mask`
 *   所在路由表里同级的 `_index_row()`（`workspace.py::asset_index()`，被
 *   `production_workflow.py` 用作聚合投影）。素材浏览器**不**新增索引端点，
 *   只在单资产 `asset()` 响应里读取 owner 已经给到的 `parameters`；
 *   `_index_row()` 的 `review_status` 因此只在**调用方显式注入索引**时使用
 *   （见 `AssetBrowserIndexEntry`）。
 * - `integrity` / `stale` / `license` / `origin` / `declaration_history_versions`
 *   抄自 `workspace.py::_production_provenance()` 与
 *   `app/experimental/production_lineage.py::_project_asset()`：两个生产者都写
 *   `integrity ∈ {VERIFIED, DELETED, CONTENT_UNAVAILABLE}`、
 *   `license_verification = 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION'`。
 *   作者声明**不是**法律核验，也**不是**任何云端许可：界面据此只能显示
 *   「作者声明」。
 * - `parents[].state` / `sources[].state` 抄自同两个生产者：
 *   `{CURRENT, STALE, DELETED, UNAVAILABLE, UNVERIFIED}`。`UNVERIFIED` 是
 *   owner 自己承认「来源没核实」，界面必须显示**未核实**而不是猜成当前。
 * - 关系抄自 `app/creative/workspace_relationships.py::AssetRelationshipAdapter`
 *   （`project()` / `graph()`）：`type` ∈
 *   `{SOURCE_OF, DERIVED_FROM, REFERENCES, USED_IN, ALTERNATE_VERSION,
 *   APPROVED_FOR, LINKED_CONTEXT}`（`app/creative/workspace_models.py::RelationshipKind`），
 *   `target.kind` ∈ `{ASSET, CHAPTER, SCREENPLAY}`，`state ∈
 *   {CURRENT, STALE, DELETED, UNAVAILABLE}`，并且每条关系都带
 *   `semantics = 'DECLARED_LINK_NOT_RIGHTS_GRANT_OR_EXECUTION'`。
 *   关系是**声明**：不授权、不生成、不执行。
 * - 删除语义抄自 `workspace.py::lifecycle()`：有子引用（`source_asset_ids`、
 *   生产来源、任一 `target.kind == 'ASSET'` 的未移除关系）时 owner 直接
 *   `ValueError("CREATIVE_ASSET_IN_USE")` 拒绝；`storage()` 自己声明
 *   `physical_cleanup_available: False`。所以本模块**没有**物理删除，也不存在
 *   「无安全删除时仍然删文件」的路径：删除永远是 owner 的软删除 + 回收站。
 * - 传输错误的机器码抄自 `workspace_api.py::invoke()` / `access()`：
 *   `CREATIVE_AUTHORITY_INVALID`、`CREATIVE_AUTHORITY_CHANGED`（403）、
 *   `CREATIVE_STORAGE_LOW_SPACE` / `CREATIVE_STORAGE_UNAVAILABLE`（507），
 *   以及 `studioClient.ts` 自己的 `STUDIO_RESPONSE_SCOPE_MISMATCH`。
 */

/* ------------------------------------------------------------ 媒体 / 审核词表 */

/** 原 owner 的媒体种类（`asset_library_service.py::import_asset` 的 `kind` 分支）。 */
export const ASSET_BROWSER_MEDIA_KINDS = ['image', 'video', 'audio'] as const;
export type AssetBrowserMediaKind = typeof ASSET_BROWSER_MEDIA_KINDS[number];
export const ASSET_BROWSER_MEDIA_KIND_LABELS: Readonly<Record<AssetBrowserMediaKind, string>> = Object.freeze({
  image: '图片', video: '视频', audio: '音频',
});

/**
 * 作者声明的用途标签。这些只是**标签**：`workspace.py::_index_row()` 让
 * `kind` 保持 owner 的媒体种类，`public()` 也不会因为标签改写 `media_type`。
 * 因此界面必须保证「打标签不改变媒体种类」。
 */
export const ASSET_BROWSER_TAGS = [
  ['character', '角色'], ['environment', '环境'], ['prop', '道具'],
] as const;
export type AssetBrowserTag = typeof ASSET_BROWSER_TAGS[number][0];
export const ASSET_BROWSER_TAG_LABELS: Readonly<Record<AssetBrowserTag, string>> = Object.freeze(
  Object.fromEntries(ASSET_BROWSER_TAGS) as Record<AssetBrowserTag, string>,
);

/**
 * 审核状态：`_index_row()` 的 `review_status` 三种取值 + 没有 owner 标记的
 * `UNREVIEWED`。`UNREVIEWED` **不是**「未通过」，也不是「草稿」。
 */
export const ASSET_BROWSER_REVIEW_STATES = ['UNREVIEWED', 'DRAFT', 'APPROVED', 'REJECTED'] as const;
export type AssetBrowserReviewState = typeof ASSET_BROWSER_REVIEW_STATES[number];
export const ASSET_BROWSER_REVIEW_LABELS: Readonly<Record<AssetBrowserReviewState, string>> = Object.freeze({
  UNREVIEWED: '无审核标记', DRAFT: '待审核草稿', APPROVED: '已批准', REJECTED: '已驳回',
});
/** `_index_row()` 真正会写进 `review_status` 的三个值（`UNREVIEWED` 是"没有"）。 */
export const ASSET_BROWSER_OWNER_REVIEW_STATUSES = ['DRAFT', 'APPROVED', 'REJECTED'] as const;

/** `_production_provenance()` / `_project_asset()` 写出的 `integrity`。 */
export const ASSET_BROWSER_INTEGRITY_STATES = ['VERIFIED', 'DELETED', 'CONTENT_UNAVAILABLE'] as const;
export type AssetBrowserIntegrity = typeof ASSET_BROWSER_INTEGRITY_STATES[number];
export const ASSET_BROWSER_INTEGRITY_LABELS: Readonly<Record<AssetBrowserIntegrity, string>> = Object.freeze({
  VERIFIED: '内容与摘要一致', DELETED: '已删除', CONTENT_UNAVAILABLE: '内容不可读',
});

/** 来源状态。`UNVERIFIED` 是 owner 自己承认未核实，界面显示 未核实。 */
export const ASSET_BROWSER_SOURCE_STATES = ['CURRENT', 'STALE', 'DELETED', 'UNAVAILABLE', 'UNVERIFIED'] as const;
export type AssetBrowserSourceState = typeof ASSET_BROWSER_SOURCE_STATES[number];
export const ASSET_BROWSER_SOURCE_STATE_LABELS: Readonly<Record<AssetBrowserSourceState, string>> = Object.freeze({
  CURRENT: '当前', STALE: '已过期', DELETED: '已删除', UNAVAILABLE: '不可用或无权访问', UNVERIFIED: '未核实',
});
/** 唯一表示「owner 没有给出可核实的结论」。绝不猜成 CURRENT。 */
export const ASSET_BROWSER_UNVERIFIED = '未核实' as const;

/** `workspace_relationships.py::MAX_RELATIONSHIPS`；owner 自己的单资产上限。 */
export const ASSET_BROWSER_RELATION_LIMIT = 100;

/* ------------------------------------------------------------------ 关系词表 */

export const ASSET_BROWSER_RELATIONSHIP_TYPES = [
  'SOURCE_OF', 'DERIVED_FROM', 'REFERENCES', 'USED_IN', 'ALTERNATE_VERSION', 'APPROVED_FOR', 'LINKED_CONTEXT',
] as const;
export type AssetBrowserRelationshipType = typeof ASSET_BROWSER_RELATIONSHIP_TYPES[number];
export const ASSET_BROWSER_RELATIONSHIP_LABELS: Readonly<Record<AssetBrowserRelationshipType, string>> = Object.freeze({
  SOURCE_OF: '作为来源', DERIVED_FROM: '派生自', REFERENCES: '参考', USED_IN: '用于',
  ALTERNATE_VERSION: '备选版本', APPROVED_FOR: '审核适用', LINKED_CONTEXT: '关联上下文',
});

export const ASSET_BROWSER_RELATIONSHIP_REFERENCE_KINDS = ['ASSET', 'CHAPTER', 'SCREENPLAY'] as const;
export type AssetBrowserRelationshipReferenceKind = typeof ASSET_BROWSER_RELATIONSHIP_REFERENCE_KINDS[number];

export const ASSET_BROWSER_RELATIONSHIP_STATES = ['CURRENT', 'STALE', 'DELETED', 'UNAVAILABLE'] as const;
export type AssetBrowserRelationshipState = typeof ASSET_BROWSER_RELATIONSHIP_STATES[number];

/** 每条关系的原 owner 语义声明：只是声明，不是授权、不是执行。 */
export const ASSET_BROWSER_RELATIONSHIP_SEMANTICS = 'DECLARED_LINK_NOT_RIGHTS_GRANT_OR_EXECUTION' as const;

/* ----------------------------------------------------- 引用（被谁使用）归类 */

/**
 * 引用方缺少可核实身份时的唯一取值。绝不从 UUID 猜出镜头编号或模块。
 */
export const ASSET_BROWSER_REFERENCE_UNKNOWN_KIND = 'UNKNOWN' as const;

/** 界面按 kind 分组时使用的稳定顺序（未知关系固定排在最后）。 */
export const ASSET_BROWSER_REFERENCE_KINDS = ['ASSET', 'CHAPTER', 'SCREENPLAY', ASSET_BROWSER_REFERENCE_UNKNOWN_KIND] as const;
export type AssetBrowserReferenceKind = typeof ASSET_BROWSER_REFERENCE_KINDS[number];
export const ASSET_BROWSER_REFERENCE_KIND_LABELS: Readonly<Record<AssetBrowserReferenceKind, string>> = Object.freeze({
  ASSET: '资产', CHAPTER: '章节', SCREENPLAY: '剧本', UNKNOWN: '未核实',
});

/** 引用状态：只有 owner 的四种关系状态 + 未核实。 */
export const ASSET_BROWSER_REFERENCE_STATES = ['CURRENT', 'STALE', 'DELETED', 'UNAVAILABLE', 'UNVERIFIED'] as const;
export type AssetBrowserReferenceState = typeof ASSET_BROWSER_REFERENCE_STATES[number];

/** 「被哪些镜头 / 节点 / 时间线使用」的三种可核实的分组，外加未知。 */
export const ASSET_BROWSER_IMPACT_GROUPS = ['SHOTS', 'NODES', 'TIMELINES', 'UNKNOWN'] as const;
export type AssetBrowserImpactGroup = typeof ASSET_BROWSER_IMPACT_GROUPS[number];
export const ASSET_BROWSER_IMPACT_GROUP_LABELS: Readonly<Record<AssetBrowserImpactGroup, string>> = Object.freeze({
  SHOTS: '镜头', NODES: '节点', TIMELINES: '时间线', UNKNOWN: '未核实',
});

/* ------------------------------------------------------------ 送到别的模块 */

/** `AssetSendToPanel` 只允许这四个目标；它们**不是**执行入口。 */
export const ASSET_BROWSER_SEND_TARGETS = ['IMAGE', 'VIDEO', 'STORYBOARD', 'TIMELINE'] as const;
export type AssetBrowserSendTarget = typeof ASSET_BROWSER_SEND_TARGETS[number];
export const ASSET_BROWSER_SEND_TARGET_LABELS: Readonly<Record<AssetBrowserSendTarget, string>> = Object.freeze({
  IMAGE: '图片模块', VIDEO: '视频模块', STORYBOARD: '分镜模块', TIMELINE: '时间线模块',
});
export const ASSET_BROWSER_SEND_TARGET_HINTS: Readonly<Record<AssetBrowserSendTarget, string>> = Object.freeze({
  IMAGE: '作为图片来源引用。只发出原始 ID / 版本 / 摘要，由图片模块自己决定是否使用。',
  VIDEO: '作为视频来源引用。不复制原文件，也不自动开始生成。',
  STORYBOARD: '作为分镜参考引用。不会自动写入任何镜头。',
  TIMELINE: '作为时间线素材引用。不会自动加入任何轨道。',
});

/**
 * 目标模块可接受的媒体种类。来源是各模块自己的输入端口
 * （`studioGraphClient.ts` 的 `image_reference` / `video_generate` /
 * `storyboard_shot` / `timeline_export` 端口与 `media_review` 的 ASSET_REF）。
 * 这里只做**预检**，真正的准入仍由目标模块自己决定。
 */
export const ASSET_BROWSER_SEND_TARGET_KINDS: Readonly<Record<AssetBrowserSendTarget, readonly AssetBrowserMediaKind[]>> =
  Object.freeze({
    IMAGE: Object.freeze(['image'] as const),
    VIDEO: Object.freeze(['image', 'video', 'audio'] as const),
    STORYBOARD: Object.freeze(['image'] as const),
    TIMELINE: Object.freeze(['image', 'video', 'audio'] as const),
  });

/**
 * 送往别的模块时固定的「不复制原文」声明，与
 * `studioClient.ts::StudioReferences` 的 `read_only: true` / `content_copied: false`
 * 同一语义。
 */
export const ASSET_BROWSER_REFERENCE_IS_NOT_A_COPY = 'reference_only_no_content_copied' as const;

/**
 * 传参引用：原资产 ID / 版本 / 摘要三元组。这是**唯一**允许跨模块传递的载荷；
 * 不做内容复制、不生成第二个原资产、不触发目标模块执行。
 */
export type AssetBrowserReference = { asset_id: string; version: number; digest: string };

/* ------------------------------------------------------------------ 数据形状 */

export type AssetBrowserProvenanceParent = {
  kind: 'PARENT';
  id: string | null;
  label: string | null;
  version: number | null;
  digest: string | null;
  state: AssetBrowserSourceState;
};

export type AssetBrowserProvenanceSource = {
  kind: 'SOURCE';
  id: string | null;
  version: number | null;
  digest: string | null;
  state: AssetBrowserSourceState;
};

/**
 * 只有 owner 真的给到的字段；缺失一律 `null`，**不**补默认值。
 */
export type AssetBrowserProvenanceView = {
  origin: string | null;
  /** Saved owner disclosure only; neither a current route nor execution authority. */
  producer: { provider_id: string | null; model_id: string | null } | null;
  integrity: AssetBrowserIntegrity | null;
  stale: boolean | null;
  /** 作者自己的许可声明文案（`license.label`）。永远配 `author declaration` 说明。 */
  license_label: string | null;
  license_source: string | null;
  /** 只在 owner 逐字返回 `AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION` 时非 `null`。 */
  license_verification: typeof ASSET_BROWSER_AUTHOR_DECLARATION | null;
  operation: string | null;
  parents: AssetBrowserProvenanceParent[];
  sources: AssetBrowserProvenanceSource[];
  declaration_history_versions: number[];
};

/** owner 自己的许可声明标记；**不是**法律核验，也**不是**云端许可。 */
export const ASSET_BROWSER_AUTHOR_DECLARATION = 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION' as const;

/** 单资产的完整读取结果（`asset()` 的投影）。 */
export type AssetBrowserAsset = {
  id: string;
  filename: string;
  /** owner 的媒体种类；非三种标准取值时保留原字符串。 */
  kind: string;
  media_kind: AssetBrowserMediaKind | null;
  media_type: string;
  size: number;
  digest: string;
  created_at: string;
  updated_at: string | null;
  /** `_row()` 要求 `version` 是 ≥1 的安全整数；不合规时这里是 `null`（不猜）。 */
  version: number | null;
  branch_id: string | null;
  deleted: boolean;
  /** owner 的审核标记；目录列表通常没有，因此是 `UNREVIEWED`。 */
  review_state: AssetBrowserReviewState;
  tags: AssetBrowserTag[];
  provenance: AssetBrowserProvenanceView | null;
  /** owner 披露的参数；未披露时为 `null`（不伪造、不补空对象）。 */
  parameters: Readonly<Record<string, unknown>> | null;
};

/**
 * 列表 / 网格共用的一行。它**只**包含 owner 已经投影出来的可授权元数据；
 * 搜索绝不会越过这些字段去打开内容或扫描磁盘。
 */
export type AssetBrowserRow = {
  id: string;
  filename: string;
  kind: string;
  media_kind: AssetBrowserMediaKind | null;
  media_type: string;
  size: number | null;
  digest: string;
  version: number | null;
  review_state: AssetBrowserReviewState;
  created_at: string;
  /** `null` 表示 owner 没有给出时间；不补 `0`，也不按当前时间排序。 */
  created_at_ms: number | null;
  created_bucket: AssetBrowserCreatedBucket;
  tags: AssetBrowserTag[];
  integrity: AssetBrowserIntegrity | null;
  stale: boolean | null;
  license_label: string | null;
  license_verification: typeof ASSET_BROWSER_AUTHOR_DECLARATION | null;
  deleted: boolean;
  /** 引用计数；`null` 表示关系投影不可读 —— 界面显示未核实，绝不显示 0。 */
  reference_counts: AssetBrowserReferenceCounts | null;
};

export type AssetBrowserReferenceCounts = {
  /** 未移除关系的总数（只统计 `target.kind` 已是可核实种类的引用）。 */
  total: number;
  by_kind: Readonly<Record<AssetBrowserReferenceKind, number>>;
  by_relationship: Readonly<Record<AssetBrowserRelationshipType, number>>;
  /** 其中处于 `STALE` / `DELETED` / `UNAVAILABLE` 的条数。 */
  not_current: number;
};

export const ASSET_BROWSER_CREATED_BUCKETS = [
  'UNRECORDED', 'TODAY', 'LAST_7_DAYS', 'LAST_30_DAYS', 'OLDER',
] as const;
export type AssetBrowserCreatedBucket = typeof ASSET_BROWSER_CREATED_BUCKETS[number];
export const ASSET_BROWSER_CREATED_BUCKET_LABELS: Readonly<Record<AssetBrowserCreatedBucket, string>> = Object.freeze({
  UNRECORDED: '未记录时间', TODAY: '今天', LAST_7_DAYS: '近 7 天', LAST_30_DAYS: '近 30 天', OLDER: '更早',
});
export const ASSET_BROWSER_DAY_MS = 24 * 60 * 60 * 1000;

/* ------------------------------------------------------------------ 过滤面 */

export type AssetBrowserFilters = {
  /** 本地子串搜索：只搜文件名与已授权元数据，绝不打开内容。 */
  query: string;
  /** `null` = 全部；取值来自 `ASSET_BROWSER_MEDIA_KINDS`。 */
  media_kind: AssetBrowserMediaKind | null;
  /** `null` = 全部；取值来自 `ASSET_BROWSER_TAGS`。 */
  tag: AssetBrowserTag | null;
  /** `null` = 全部；取值来自 `ASSET_BROWSER_REVIEW_STATES`。 */
  review_state: AssetBrowserReviewState | null;
  /** `null` = 全部；取值来自 `ASSET_BROWSER_CREATED_BUCKETS`。 */
  created_bucket: AssetBrowserCreatedBucket | null;
  /**
   * `null` = 全部。`REFERENCED` / `UNREFERENCED` 只作用于**已读取**引用计数的行；
   * `UNVERIFIED` 只选那些引用情况尚不可核实的行。引用计数不可读时不会被算成 0。
   */
  reference: AssetBrowserReferenceFilter | null;
};

export const ASSET_BROWSER_EMPTY_FILTERS: AssetBrowserFilters = Object.freeze({
  query: '', media_kind: null, tag: null, review_state: null, created_bucket: null, reference: null,
});

/** 每个面各自的取值与计数。计数永远由**当前行集合**重新推导。 */
export type AssetBrowserFacetOption<T extends string> = { value: T; label: string; count: number };
export type AssetBrowserFacets = {
  media_kind: AssetBrowserFacetOption<AssetBrowserMediaKind | 'UNKNOWN'>[];
  tag: AssetBrowserFacetOption<AssetBrowserTag | 'UNTAGGED'>[];
  review_state: AssetBrowserFacetOption<AssetBrowserReviewState>[];
  created_bucket: AssetBrowserFacetOption<AssetBrowserCreatedBucket>[];
  /** 引用面：`REFERENCED` / `UNREFERENCED` / `UNVERIFIED`（计数不可读时）。 */
  reference: AssetBrowserFacetOption<AssetBrowserReferenceFilter>[];
  /** 参与统计的行数。 */
  total: number;
  /** 引用计数不可读的行数：这些行会被计入 `UNVERIFIED`，而不是被算成 0。 */
  reference_unverified: number;
};

export const ASSET_BROWSER_REFERENCE_FILTERS = ['REFERENCED', 'UNREFERENCED', 'UNVERIFIED'] as const;
export type AssetBrowserReferenceFilter = typeof ASSET_BROWSER_REFERENCE_FILTERS[number];
export const ASSET_BROWSER_REFERENCE_FILTER_LABELS: Readonly<Record<AssetBrowserReferenceFilter, string>> = Object.freeze({
  REFERENCED: '已被引用', UNREFERENCED: '未被引用', UNVERIFIED: '引用情况未核实',
});

/* ------------------------------------------------------------------ 对比结果 */

export type AssetBrowserCompareField =
  | 'id' | 'filename' | 'kind' | 'media_type' | 'size' | 'digest' | 'version'
  | 'created_at' | 'review_state' | 'tags' | 'origin' | 'integrity' | 'stale'
  | 'license_label' | 'license_verification' | 'operation' | 'parents' | 'sources';

export const ASSET_BROWSER_COMPARE_FIELDS: readonly AssetBrowserCompareField[] = Object.freeze([
  'id', 'filename', 'kind', 'media_type', 'size', 'digest', 'version', 'created_at', 'review_state', 'tags',
  'origin', 'integrity', 'stale', 'license_label', 'license_verification', 'operation', 'parents', 'sources',
]);

export const ASSET_BROWSER_COMPARE_FIELD_LABELS: Readonly<Record<AssetBrowserCompareField, string>> = Object.freeze({
  id: '资产 ID', filename: '文件名', kind: '种类', media_type: '媒体类型', size: '字节数', digest: 'SHA-256',
  version: '版本', created_at: '创建时间', review_state: '审核标记', tags: '用途标签', origin: '来源',
  integrity: '完整性', stale: '来源是否过期', license_label: '作者许可声明', license_verification: '许可核验标记',
  operation: '处理操作', parents: '父资产', sources: '章节来源',
});

/** 一个字段的对比结论：同 / 不同 / 无法对比（任一侧未披露）。 */
export type AssetBrowserCompareVerdict = 'SAME' | 'DIFFERENT' | 'UNVERIFIABLE';

export type AssetBrowserCompareEntry = {
  field: AssetBrowserCompareField;
  label: string;
  verdict: AssetBrowserCompareVerdict;
  /** 展示用的有界文本；未披露一侧为 `null`。 */
  left: string | null;
  right: string | null;
};

export type AssetBrowserCompareResult = {
  left_id: string;
  right_id: string;
  /** 同一资产 ID 的不同版本：`true` 时界面必须说明"这是同一个资产的版本对比"。 */
  same_asset: boolean;
  entries: AssetBrowserCompareEntry[];
  changed: AssetBrowserCompareField[];
  unverifiable: AssetBrowserCompareField[];
  identical: boolean;
  /** 至少有一个字段被核实为不同。 */
  differs: boolean;
  /** 双方 `digest` 都被披露且不同（内容确实不同）。 */
  content_differs: boolean | null;
};

/* ------------------------------------------------------------------ 影响面 */

/** 「被哪些镜头 / 节点 / 时间线使用」的一条引用。 */
export type AssetBrowserReferencedBy = {
  /** owner 的引用方 id；`null` 表示这条关系没有可核实的引用方。 */
  id: string | null;
  /** owner 的引用方种类；不可核实时为 `UNKNOWN`（界面显示未核实）。 */
  kind: AssetBrowserReferenceKind;
  /**
   * 引用方属于镜头 / 节点 / 时间线中的哪一组。owner 的关系投影**没有**这个信息，
   * 因此默认是 `UNKNOWN`（未核实）；只有目标模块自己回传时才是具体分组。
   */
  group: AssetBrowserImpactGroup;
  label: string | null;
  relationship: AssetBrowserRelationshipType;
  state: AssetBrowserReferenceState;
  /** 引用**当时**绑定的版本 / 摘要；owner 没给就是 `null`。 */
  bound_version: number | null;
  bound_digest: string | null;
};

export type AssetBrowserImpactEntry = AssetBrowserReferencedBy & {
  /** 按镜头 / 节点 / 时间线分组（无法核实时归入 UNKNOWN）。 */
  group: AssetBrowserImpactGroup;
  /** 这条引用绑定的是否正是当前版本。无法核实时 `null`。 */
  matches_current: boolean | null;
};

export type AssetBrowserImpactGroupView = {
  group: AssetBrowserImpactGroup;
  label: string;
  items: AssetBrowserImpactEntry[];
  /** 需要用户重新确认才能跟随新版本的条数。 */
  needs_decision: number;
  /** 无法核实的条数（引用方或绑定版本不可读）。 */
  unverified: number;
};

export type AssetBrowserImpact = {
  source: { asset_id: string; version: number | null; digest: string };
  groups: AssetBrowserImpactGroupView[];
  total: number;
  /** 老 vs 新的差异是否可核实：有没有旧版本的绑定信息。 */
  versions_comparable: boolean;
  /** 只有用户显式选择才会更新绑定；这里从不自动更新任何镜头 / 节点 / 时间线。 */
  automatic_update: false;
  /** 未知关系一律显示未核实。 */
  unverified_is_not_absent: true;
};

/**
 * 删除前的可用影响面报告。
 *
 * owner（`workspace.py::lifecycle()`）在有子引用时直接拒绝并抛
 * `CREATIVE_ASSET_IN_USE`；`storage()` 自己声明 `physical_cleanup_available: false`，
 * 删除是软删除 + 回收站。因此：
 *
 * - `blocking`：会被 owner 判定为"仍在使用"的引用（未删除的引用方）。
 * - `reported`：全部引用，包含无法核实的那部分。
 * - `physical_delete: false` 与 `content_removed: false` 是硬事实：界面因此不可能
 *   声称"没有安全删除时仍然删除了用户文件"。
 *
 * 这里没有任何删除动作；真正的删除只能由用户通过既有 owner 接口发起。
 */
export type AssetBrowserDeleteImpact = {
  asset: { asset_id: string; version: number | null; digest: string; filename: string };
  reported: AssetBrowserImpact;
  blocking: AssetBrowserImpactEntry[];
  blocking_total: number;
  unverified_total: number;
  /** owner 的删除是软删除 + 回收站。 */
  physical_delete: false;
  /** 本报告不会移除任何内容。 */
  content_removed: false;
  /** 有阻塞引用时 owner 会拒绝删除。 */
  refusable_by_owner: boolean;
  message: string;
};

/* ------------------------------------------------------------------ 界面状态 */

/** 显式数据面状态：`EMPTY` 只表示"读成功且真的没有内容"，绝不吞掉 `DENIED`。 */
export const ASSET_BROWSER_SURFACE_STATES = ['IDLE', 'LOADING', 'READY', 'EMPTY', 'DENIED', 'FAILED'] as const;
export type AssetBrowserSurfaceState = typeof ASSET_BROWSER_SURFACE_STATES[number];
export type AssetBrowserProblem = { code: string; message: string };

/** 网格 / 列表共用同一个选择模型（只有一个 `selectedId`）。 */
export type AssetBrowserViewMode = 'GRID' | 'LIST';
export type AssetBrowserLayout = {
  mode: AssetBrowserViewMode;
  page_size: number;
  visible: number;
};

/* ------------------------------------------------------------------ 客户端 */

/** 与 `productionWorkflowClient.ts` / `taskCenterClient.ts` 同一个注入形状。 */
export type AssetBrowserClient = {
  listAssets: (signal?: AbortSignal) => Promise<AssetBrowserAsset[]>;
  readAsset: (assetId: string, signal?: AbortSignal) => Promise<AssetBrowserAsset>;
  /**
   * 既有关系投影（`GET /projects/{nid}/studio/relationships`）。它属于
   * `AssetRelationshipAdapter`，本模块只读，不新增第二个关系 owner。
   */
  readRelationships: (signal?: AbortSignal) => Promise<AssetBrowserRelationshipGraph>;
  /**
   * 既有下载入口（`GET /projects/{nid}/studio/assets/{aid}/download`）。
   * 缩略图与预览只在需要时调用一次；绝不预取整库。
   */
  downloadAsset?: (assetId: string, signal?: AbortSignal) => Promise<Blob>;
};

export type AssetBrowserRelationshipNode = {
  id: string;
  /** owner 的节点种类；关系图里只有资产节点。 */
  kind: 'ASSET';
  asset_kind: string;
  label: string;
  version: number;
  digest: string;
};

export type AssetBrowserRelationshipEdge =
  | {
      owner: 'ASSET_RELATIONSHIPS';
      id: string;
      from: string;
      type: AssetBrowserRelationshipType;
      state: AssetBrowserRelationshipState;
      /** `UNAVAILABLE` 时 owner 只给一句话，不泄露目标。 */
      target: {
        kind: AssetBrowserRelationshipReferenceKind | null;
        id: string | null;
        version: number | null;
        digest: string | null;
        label: string | null;
        deleted: boolean | null;
      };
      /** 关联**当时**绑定的目标（`expected`）；`UNAVAILABLE` 边没有。 */
      expected: {
        kind: AssetBrowserRelationshipReferenceKind | null;
        id: string | null;
        version: number | null;
        digest: string | null;
      } | null;
      reason: string | null;
      created_by: string | null;
      created_at: string | null;
      semantics: typeof ASSET_BROWSER_RELATIONSHIP_SEMANTICS;
    }
  | {
      owner: 'ASSET_LINEAGE';
      id: string;
      from: string;
      type: 'DERIVED_FROM';
      state: AssetBrowserRelationshipState;
      /** 原始来源边的目标只可能是资产（`workspace_relationships.py::graph()`）。 */
      target: {
        kind: 'ASSET' | null;
        id: string | null;
        version: number | null;
        digest: string | null;
        label: string | null;
        deleted: boolean | null;
      };
      expected: null;
      reason: null;
      created_by: null;
      created_at: null;
      semantics: typeof ASSET_BROWSER_RELATIONSHIP_SEMANTICS;
    };

export type AssetBrowserRelationshipGraph = {
  /** owner 自己的图种类标记；消费者原样保留。 */
  graph_kind: 'ASSET_RELATIONSHIPS';
  nodes: AssetBrowserRelationshipNode[];
  edges: AssetBrowserRelationshipEdge[];
  /** owner 自己声明的事实，界面据此禁止"执行 / 知识图谱 / 自动重生成"的任何暗示。 */
  executable: false;
  knowledge_graph: false;
  automatic_regeneration: false;
};

/* ------------------------------------------------------------------ 有界取值 */

export const ASSET_BROWSER_BOUNDS = Object.freeze({
  project_id: 240,
  asset_id: 240,
  filename: 255,
  media_type: 160,
  kind: 40,
  origin: 40,
  producer_id: 240,
  label: 4096,
  digest: 64,
  timestamp: 64,
  license_label: 160,
  license_source: 500,
  license_note: 2000,
  operation: 160,
  tag: 64,
  tags: 32,
  relationship_id: 240,
  actor: 240,
  reason: 1000,
  /** 前端一次最多接受的行数；超出即拒绝，绝不静默截断成"完整清单"。 */
  list_items: 500,
  graph_nodes: 500,
  graph_edges: 2000,
  /**
   * 关系图的边上限：每个节点最多 `MAX_RELATIONSHIPS` 条声明关系，另加每个
   * `source_asset_ids` 一条原始来源边。owner 自己的两个上限都在服务端生效，
   * 这里只是**消费者**侧的有界读取，超过就拒绝而不是截断。
   */
  graph_edge_ceiling: 20000,
  provenance_parents: 200,
  provenance_sources: 200,
  declaration_history: 200,
  parameters_depth: 4,
  parameters_entries: 64,
  parameters_string: 2000,
  page_size_min: 8,
  page_size_default: 24,
  page_size_max: 200,
  /** 搜索词上限（owner 的 `q` 是 160；这里本地过滤同样有界）。 */
  query: 160,
} as const);

/** 稳定机器码：界面文案按码映射，绝不直接渲染服务端正文。 */
export const ASSET_BROWSER_ERROR_CODES = Object.freeze({
  /** 列表 / 关系图响应形状不合法。 */
  listInvalid: 'ASSET_BROWSER_LIST_INVALID',
  detailInvalid: 'ASSET_BROWSER_DETAIL_INVALID',
  relationshipsInvalid: 'ASSET_BROWSER_RELATIONSHIPS_INVALID',
  /** 返回的项目 / 分支与当前工作区不一致。 */
  scopeMismatch: 'ASSET_BROWSER_SCOPE_MISMATCH',
  /** 本地就拒绝的读取请求（项目标识或资产标识不可用）。 */
  readLocalInvalid: 'ASSET_BROWSER_READ_LOCAL_INVALID',
  /** 本地就拒绝的搜索词。 */
  queryLocalInvalid: 'ASSET_BROWSER_QUERY_LOCAL_INVALID',
  /** owner 自己抛出的码（这里只换成有界中文文案）。 */
  authorityInvalid: 'CREATIVE_AUTHORITY_INVALID',
  authorityChanged: 'CREATIVE_AUTHORITY_CHANGED',
  storageLowSpace: 'CREATIVE_STORAGE_LOW_SPACE',
  storageUnavailable: 'CREATIVE_STORAGE_UNAVAILABLE',
  assetInUse: 'CREATIVE_ASSET_IN_USE',
  assetVersionInvalid: 'CREATIVE_ASSET_VERSION_INVALID',
  studioScopeMismatch: 'STUDIO_RESPONSE_SCOPE_MISMATCH',
  studioResponseInvalid: 'STUDIO_RESPONSE_INVALID',
  studioRequestFailed: 'STUDIO_REQUEST_FAILED',
  studioNetworkFailed: 'STUDIO_NETWORK_FAILED',
} as const);

/** 界面自己说的话（有界、可测）。 */
export const ASSET_BROWSER_NOTICES = Object.freeze({
  readFailure: '素材库读取失败，请稍后重新核对。',
  detailFailure: '资产详情读取失败；当前选择保持，未切换到其他资产。',
  /** 拒绝读取**不是**空素材库。 */
  deniedIsNotEmpty: '当前会话无权读取此素材库；这不是"暂无素材"。',
  notFoundIsNotEmpty: '素材库当前不可用（记录不存在或功能未启用）；这不是"暂无素材"。',
  empty: '此项目当前没有可读取的素材。',
  noMatch: '当前筛选没有匹配的素材；已读取的素材仍然保留。',
  relationshipUnreadable: '引用关系当前不可读，引用情况显示为未核实，不会当作"未被引用"。',
  pageBounded: '只显示已读取的前若干条；继续加载会再读取下一页，绝不一次拉取全部高清素材。',
  thumbnailOnDemand: '缩略图只在需要时按原下载接口读取，不预取整库。',
  previewFailed: '预览读取失败；当前选择保持不变。',
  noPhysicalDelete: '删除由原资产 owner 执行"软删除 + 回收站"，不会物理删除你的文件。',
  deleteInUse: '此素材仍被其他内容引用，原 owner 会拒绝删除；请先处理引用。',
  notACopy: '传参只携带原资产 ID / 版本 / SHA-256，不复制内容，也不会生成第二个原资产。',
  noAutoUpdate: '新的来源版本只显示差异；只有你明确选择才会更新绑定，绝不自动更新所有任务 / 镜头 / 片段。',
  unverified: '未核实',
  licenseIsDeclaration: '许可是作者声明，不是法律核验，也不代表任何云端授权。',
} as const);
