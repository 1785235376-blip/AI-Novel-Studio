/**
 * UX-09 统一导出与工程交接 —— 冻结词表、有界常量与共享类型。
 *
 * 这个目录是**消费者**：它不新增第二套导出引擎、任务调度器或互操作协议。下面每一条
 * 字面量都逐条来自真实原 owner，改动前请先改后端：
 *
 * - `DELIVERY_JOB_STATUSES` / `DELIVERY_RECEIPT_KEYS` 抄自
 *   `app/services/export_job_service.py::ExportJobService.STATUSES`（`queued` /
 *   `running` / `succeeded` / `failed` / `cancelled`）与 `_normalise_job()` /
 *   `public()` 实际会写进本地队列、并经 `app/api.py` 的 `/api/exports` 暴露的字段。
 *   `_normalise_job()` 先把历史记录补全成**固定键集**，所以这里的严格解码器可以逐键
 *   核对；`public()` 只移除 `snapshot` / `idempotency_key` / `artifact`（结果体里的
 *   `content` / `content_base64` 同样不下发）。
 * - `DELIVERY_PACKAGE_FORMATS` 抄自 `app/services/export_resource_snapshot.py::
 *   PACKAGE_FORMATS`（`screenplay-package` / `shot-list-package` / `storyboard-package`）。
 * - `DELIVERY_FORMAT_IDS` 抄自 `ExportJobService.SUPPORTED` 的**规范写法**：原 owner
 *   在 `create()` 里先把 `md→markdown`、`text→txt`、`word→docx`、
 *   `screenplay-standard→screenplay-fountain` 归一化，因此别名不是独立格式：`SUPPORTED`
 *   的 18 个取值归一化后只剩下面 14 个规范 id（另加一条 `script-txt` 通用脚本格式，
 *   它由 `app/creative/script_export.py` 持有，不属于 `/api/exports`）。
 * - `DELIVERY_ITEM_BYTES_LIMIT` / `DELIVERY_PACKAGE_BYTES_LIMIT` 抄自
 *   `app/export_formats.py::MAX_RESOURCE_BYTES`（25 MiB）与
 *   `MAX_PACKAGE_RESOURCE_BYTES`（64 MiB）；`DELIVERY_RESULT_BYTES_LIMIT` 抄自
 *   `ExportJobService.MAX_RESULT_BYTES`（64 MiB）。原 owner 是唯一的限额权威，
 *   本目录**只复述、不上调**（`sizeAndLimitsReport()` 会显式拒绝任何抬升）。
 * - `ExportJobService._recover_on_startup()` 是原 owner 自己的恢复语义：进程重启时把
 *   `queued`/`running` 重新排队并 `recovery_count += 1`。本目录因此**永远不重新派发**；
 *   回执丢失时只按同一 `Idempotency-Key`/`format` 重新**读取**原任务
 *   （`create()` 对同 key 的重复调用会直接返回同一条记录，见
 *   `tests/test_export_jobs.py::test_export_job_is_durable_idempotent_and_completes`）。
 * - 行业格式的适用对象（哪些格式属于文字/剧本/镜头/分镜）来自由
 *   `app/creative/screenplay_export.py`、`app/creative/script_export.py` 与
 *   `screenplay-package` 资源快照共同定义的写入面；`DELIVERY_FORMAT_KINDS` 是这份
 *   映射的显式转写，**不是**新的能力声明 —— 它只能让界面少一个可选项。
 * - 工程交接（handover）的既有概念来自 `frontend/src/interop/*`（PoemSeed Local
 *   Interop 1.0，语义**冻结**）：`interop/client.ts::HandoffTarget` + `/handoff` 是
 *   "把操作者送到某处"的既有协议，本目录**不重定义、不修改**它，也不借用它的名字。
 *   这里的 `HandoverManifest` 只描述"本次交接包里放了什么、排斥了什么"，是一份纯
 *   数据清单，没有传输、没有会话、没有权限协商。
 *
 * **刻意不复制的东西**：`ExportJobService.SUPPORTED`（真实可用性由原 owner 在 `create()`
 * 里判定；前端复述一份就等于造第二个验收标准）、原 owner 的 store 路径与凭据、
 * 任何模型清单或依赖目录清单。模型/依赖/凭据/他项目对象的排斥规则写在
 * `deliveryOps.ts` 里，用的是**排斥**（默认不放行）而不是允许清单的补集。
 */

/* ------------------------------------------------------------------ 回执状态 */

/** `ExportJobService.STATUSES` 的逐条转写。原 owner 之外的状态一律不猜测。 */
export const DELIVERY_JOB_STATUSES = ['queued', 'running', 'succeeded', 'failed', 'cancelled'] as const;
export type DeliveryJobStatus = typeof DELIVERY_JOB_STATUSES[number];
export const DELIVERY_JOB_STATUS_LABELS: Readonly<Record<DeliveryJobStatus, string>> = Object.freeze({
  queued: '排队中', running: '处理中', succeeded: '已完成', failed: '失败', cancelled: '已取消',
});

/**
 * 界面只区分三件事：请求已经离开本机（`DISPATCHED`）、**本机没有拿到任何回执**
 * （`UNKNOWN`，绝不当作成功）、回执确实回来了（`RETURNED`，再由原 owner 的状态说话）。
 */
export const DELIVERY_RECEIPT_STATES = ['UNKNOWN', 'DISPATCHED', 'RETURNED'] as const;
export type DeliveryReceiptState = typeof DELIVERY_RECEIPT_STATES[number];
export const DELIVERY_RECEIPT_STATE_LABELS: Readonly<Record<DeliveryReceiptState, string>> = Object.freeze({
  UNKNOWN: '回执未知',
  DISPATCHED: '已派发，结果未确认',
  RETURNED: '回执已返回',
});

/** 恢复动作的机器码：每一个都只**读取**，没有任何一个是再次派发。 */
export const DELIVERY_RECOVERY_CODES = [
  'REREAD_BY_IDEMPOTENCY_KEY',
  'REREAD_ORIGINAL_JOB',
  'ORIGINAL_OWNER_RETRY_ENDPOINT',
  'NO_ACTION_REQUIRED',
] as const;
export type DeliveryRecoveryCode = typeof DELIVERY_RECOVERY_CODES[number];

/* ------------------------------------------------------------------ 导出格式 */

/**
 * `ExportJobService.SUPPORTED` 归一化之后的 15 个规范格式 id。
 * 字母序固定，便于解码时逐项核对。
 */
export const DELIVERY_FORMAT_IDS = [
  'docx', 'epub', 'json', 'markdown', 'pdf', 'screenplay', 'screenplay-docx',
  'screenplay-fountain', 'screenplay-package', 'shot-list', 'shot-list-package',
  'storyboard', 'storyboard-package', 'txt',
] as const;
export type DeliveryFormatId =
  | typeof DELIVERY_FORMAT_IDS[number]
  /** `app/creative/script_export.py` 的通用脚本格式（独立于 `/api/exports`，由创意面板持有）。 */
  | 'script-txt';

/** `export_resource_snapshot.py::PACKAGE_FORMATS`：这三条要冻结资源负载。 */
export const DELIVERY_PACKAGE_FORMATS: readonly DeliveryFormatId[] = Object.freeze([
  'screenplay-package', 'shot-list-package', 'storyboard-package',
]);

/** 原 owner 自己声明的字节/条目上限。本目录只复述。 */
export const DELIVERY_ITEM_BYTES_LIMIT = 25 * 1024 * 1024;
export const DELIVERY_PACKAGE_BYTES_LIMIT = 64 * 1024 * 1024;
export const DELIVERY_MANIFEST_ITEM_LIMIT = 500;

/* ------------------------------------------------------------------ 项目内对象 */

/**
 * 可以单独导出的对象种类。`timeline` 对应时间线的既有导出面板
 * （`StudioTimelineExportPanel.tsx` / `studioTimelineExportTypes.ts`）。
 */
export const DELIVERY_ITEM_KINDS = ['text', 'image', 'audio', 'video', 'screenplay', 'timeline'] as const;
export type DeliveryItemKind = typeof DELIVERY_ITEM_KINDS[number];
export const DELIVERY_ITEM_KIND_LABELS: Readonly<Record<DeliveryItemKind, string>> = Object.freeze({
  text: '文本', image: '图片', audio: '音频', video: '视频', screenplay: '剧本', timeline: '时间线',
});

/** 对象与身份的可见性。`DENIED` 的对象永远不会进入交接包。 */
export const DELIVERY_ITEM_VISIBILITIES = ['VISIBLE', 'DENIED', 'BLOCKED'] as const;
export type DeliveryItemVisibility = typeof DELIVERY_ITEM_VISIBILITIES[number];

/**
 * `DELIVERY_FORMAT_IDS` 的适用对象。空白项（`audio` / `video`）是**原 owner 当前的真实
 * 状态**：' 没有任何 `/api/exports` 格式声明能写出音视频。界面据此给出明确拒绝，
 * 而不是伪造一个可用的导出。
 */
export const DELIVERY_FORMAT_KINDS: Readonly<Record<DeliveryFormatId, readonly DeliveryItemKind[]>> = Object.freeze({
  txt: ['text'],
  markdown: ['text', 'screenplay'],
  json: ['text', 'screenplay', 'timeline'],
  docx: ['text', 'screenplay'],
  pdf: ['text', 'screenplay'],
  epub: ['text', 'screenplay'],
  screenplay: ['screenplay'],
  'screenplay-fountain': ['screenplay'],
  'screenplay-docx': ['screenplay'],
  'screenplay-package': ['screenplay'],
  'shot-list': ['timeline'],
  'shot-list-package': ['timeline'],
  storyboard: ['timeline', 'image'],
  'storyboard-package': ['timeline'],
  'script-txt': ['screenplay'],
});

/* ------------------------------------------------------------------ 排斥规则词表 */

/** 依赖/构建目录：任何一段路径命中即拒绝进入交接包。 */
export const DELIVERY_FORBIDDEN_PATH_SEGMENTS = Object.freeze([
  'node_modules', '__pycache__', '.git', '.svn', '.hg', 'dist', 'build', 'out', 'target',
  '.venv', 'venv', 'site-packages', '.cache', '.pytest_cache', '.mypy_cache', '.ruff_cache',
  '.next', '.turbo', '.parcel-cache', 'coverage', 'htmlcov', '.runtime',
] as const);

/** 模型/权重/编译产物后缀：这些是工程依赖，不是可交付对象。 */
export const DELIVERY_FORBIDDEN_EXTENSIONS = Object.freeze([
  'gguf', 'safetensors', 'ckpt', 'pt', 'pth', 'onnx', 'mlmodel', 'mlpackage', 'h5', 'pb',
  'tflite', 'engine', 'plan', 'bin', 'so', 'dll', 'dylib', 'pyd', 'pyc', 'whl', 'node', 'ko',
] as const);

/** 凭据/密钥名字线索：键名或路径命中即拒绝（本目录**从不**读取凭据内容）。 */
export const DELIVERY_SECRET_NAME_HINTS = Object.freeze([
  'password', 'passwd', 'secret', 'token', 'api_key', 'apikey', 'access_key', 'private_key',
  'credential', 'auth', 'cookie', 'session_key', 'keychain', 'keystore', 'id_rsa', 'id_ed25519',
  'netrc', 'npmrc', 'pypirc', 'env', 'secrets', 'vault', '.pem', '.p12', '.pfx', '.key', '.jks',
] as const);

/** 媒体类型里一眼可见的密钥/模型线索（原 owner 不会下发这些，仍然拒绝）。 */
export const DELIVERY_FORBIDDEN_MEDIA_TYPES = Object.freeze([
  'application/x-pem-file', 'application/pkcs12', 'application/x-pkcs12',
  'application/octet-stream', 'application/x-model', 'application/x-gguf',
] as const);

/* ------------------------------------------------------------------ 机器码 */

/**
 * 传输层必须回传的稳定机器码；界面文案按码映射，绝不直接渲染服务端正文。
 * 与 `productionWorkflowContract.ts` / `taskCenterTypes.ts` 同一形状。
 */
export const DELIVERY_CODES = Object.freeze({
  responseInvalid: 'DELIVERY_RESPONSE_INVALID',
  scopeMismatch: 'DELIVERY_SCOPE_MISMATCH',
  readFailed: 'DELIVERY_READ_FAILED',
  receiptInvalid: 'DELIVERY_RECEIPT_INVALID',
  receiptUnknown: 'DELIVERY_RECEIPT_UNKNOWN',
  itemInvalid: 'DELIVERY_ITEM_INVALID',
  itemForeignProject: 'DELIVERY_ITEM_FOREIGN_PROJECT',
  itemNotExportable: 'DELIVERY_ITEM_NOT_EXPORTABLE',
  itemKindUnavailable: 'DELIVERY_ITEM_KIND_UNAVAILABLE',
  formatUnknown: 'DELIVERY_FORMAT_UNKNOWN',
  formatNotApplicable: 'DELIVERY_FORMAT_NOT_APPLICABLE',
  pathUnsafe: 'DELIVERY_PATH_UNSAFE',
  pathForbidden: 'DELIVERY_PATH_FORBIDDEN',
  modelArtifact: 'DELIVERY_MODEL_ARTIFACT',
  secretBearing: 'DELIVERY_SECRET_BEARING',
  manifestOverflow: 'DELIVERY_MANIFEST_OVERFLOW',
  itemTooLarge: 'DELIVERY_ITEM_TOO_LARGE',
  packageTooLarge: 'DELIVERY_PACKAGE_TOO_LARGE',
  limitRaiseRefused: 'DELIVERY_LIMIT_RAISE_REFUSED',
  itemDuplicate: 'DELIVERY_ITEM_DUPLICATE',
  // 原 owner / 传输层会真实抛出的码，客户端只负责换成有界的用户文案。
  notCancellable: 'EXPORT_NOT_CANCELLABLE',
  notRetryable: 'EXPORT_NOT_RETRYABLE',
  scopeForbidden: 'EXPORT_SCOPE_FORBIDDEN',
} as const);

/** 交接包排斥原因：全部是稳定机器码，与 `DELIVERY_CODES` 一一对应。 */
export const DELIVERY_EXCLUSION_REASONS = [
  'FOREIGN_PROJECT', 'IDENTITY_INVALID', 'PATH_UNSAFE', 'PATH_FORBIDDEN', 'SECRET_BEARING',
  'MODEL_ARTIFACT', 'KIND_NOT_ENTITLED', 'MEDIA_TYPE_FORBIDDEN', 'VERSION_MISSING',
  'DIGEST_MISSING', 'DIGEST_INVALID', 'SIZE_INVALID', 'ITEM_TOO_LARGE', 'VISIBILITY_NOT_EXPORTABLE',
  'DUPLICATE_ITEM', 'ENTITLEMENT_DENIED',
] as const;
export type DeliveryExclusionReason = typeof DELIVERY_EXCLUSION_REASONS[number];
export const DELIVERY_EXCLUSION_REASON_LABELS: Readonly<Record<DeliveryExclusionReason, string>> = Object.freeze({
  FOREIGN_PROJECT: '该对象属于其他项目，不会进入本项目的交接包。',
  IDENTITY_INVALID: '对象标识不符合原 owner 的标识语法，未进入交接包。',
  PATH_UNSAFE: '对象路径不是项目内的安全相对路径（绝对路径、盘符、`..` 或控制字符），未进入交接包。',
  PATH_FORBIDDEN: '对象位于依赖/构建/缓存目录，属于工程内部文件，未进入交接包。',
  SECRET_BEARING: '对象名字或媒体类型像凭据/密钥，未进入交接包（本目录从不读取凭据内容）。',
  MODEL_ARTIFACT: '对象是模型权重或编译产物，属于工程依赖，未进入交接包。',
  KIND_NOT_ENTITLED: '当前身份没有导出这一类对象的权利，未进入交接包。',
  MEDIA_TYPE_FORBIDDEN: '对象媒体类型不允许出现在交接包，未进入交接包。',
  VERSION_MISSING: '对象没有可引用的版本号，无法证明交接的是哪一版，未进入交接包。',
  DIGEST_MISSING: '对象没有可核对的摘要，无法证明交接内容未被改动，未进入交接包。',
  DIGEST_INVALID: '对象摘要不是合法的 SHA-256 十六进制，未进入交接包。',
  SIZE_INVALID: '对象字节数缺失或非法，无法核对限额，未进入交接包。',
  ITEM_TOO_LARGE: '对象单独超过原 owner 的单文件字节上限，未进入交接包。',
  VISIBILITY_NOT_EXPORTABLE: '该对象当前对本次身份不可见或已被阻塞，未进入交接包。',
  DUPLICATE_ITEM: '同一次选择里出现了重复的对象 id，只保留第一次出现的那一项。',
  ENTITLEMENT_DENIED: '当前身份没有被授予导出权利，整个交接包为空。',
});

export const DELIVERY_NOTICES = Object.freeze({
  opOnly: '本目录不创建导出任务：派发、重试与取消始终由原导出 owner 执行。',
  readOnlyRecovery: '恢复只会重新读取原回执（同一 idempotency key），绝不再次派发。',
  receiptUnknown: '本机没有拿到回执，这不等于成功，也不等于失败；请重新读取原回执核对。',
  receiptNotSuccess: '回执已返回，但原 owner 的状态才是唯一结论；失败与取消都不会被显示成完成。',
  singleItemIndependent: '单个对象可独立导出，不依赖项目其余部分是否完成。',
  limitsAreOwnerDeclared: '这里的字节与条目上限来自原导出 owner，界面不能上调。',
  emptyIsNotDenied: '读成功且确实没有内容才会显示为空；被拒绝的读取始终显示为无权限。',
  executionIsNotDelivery: '原任务完成只表示文件已生成，验收与发行仍由原 owner 负责。',
} as const);

/* ------------------------------------------------------------------ 取值语法 */

/** 项目/分支标识：与 `productionWorkflowContract.ts` 的 `identity()` 同语法。 */
export const DELIVERY_IDENTITY_TOKEN = /^[A-Za-z0-9][A-Za-z0-9:._-]*$/;
/** `ExportJobService` 的 UUID4 回执 id。 */
export const DELIVERY_JOB_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
/** 对象 id：`export_resource_snapshot.py::FrozenExportResources.get` 的资产 id 语法。 */
export const DELIVERY_ITEM_ID = /^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,254}$/;
/** SHA-256 十六进制摘要（小写）。 */
export const DELIVERY_DIGEST = /^[a-f0-9]{64}$/;
/** 一段安全的项目内相对路径：不允许 `..`、盘符、UNC、控制字符。 */
export const DELIVERY_SAFE_PATH = /^[A-Za-z0-9_@][A-Za-z0-9_@ .+-]{0,120}(?:\/[A-Za-z0-9_@][A-Za-z0-9_@ .+-]{0,120})*$/;
/** 幂等键语法：与原 owner 的 `Idempotency-Key` 头一致（有界可见字符）。 */
export const DELIVERY_IDEMPOTENCY_KEY = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;

export const DELIVERY_BOUNDS = Object.freeze({
  project_id: 240, label: 120, id: 255, media_type: 120, path: 512, path_segments: 12,
  digest: 64, message: 300, format: 64, idempotency_key: 128, timestamp: 64, reason: 64,
} as const);

/* ------------------------------------------------------------------ 数据形状 */

/** 与 `productionWorkflowTypes.ts::ProductionWorkflowScope` 同一形状。 */
export type DeliveryScope = {
  mode: 'local' | 'collaboration';
  novel_id: string;
  workspace_id?: string | null;
  project_id?: string | null;
  storyline_id?: string | null;
  branch_id?: string | null;
};

/** 当前身份被授予的导出权利。它只能**减少**可选项，永远不会制造权利。 */
export type DeliveryEntitlements = {
  /** 当前会话项目；任何其他项目的对象都会被排斥。 */
  project_id: string;
  identity: string;
  /** 身份是否被授予导出权利（复核后的结论，不是提示）。 */
  can_export: boolean;
  /** 身份可导出的对象种类；空数组表示没有任何一类可导出。 */
  item_kinds: DeliveryItemKind[];
  /** 身份允许使用的格式；空数组表示一个都不能用。 */
  formats: DeliveryFormatId[];
  /** 原 owner 声明的单文件上限（只复述）。 */
  max_item_bytes: number;
  /** 原 owner 声明的整包上限（只复述）。 */
  max_package_bytes: number;
  /** 一次选择最多包含多少条。 */
  max_items: number;
};

/** 原 owner 可能附带的来源版本信息；键值都是有界标量。 */
export type DeliverySourceVersion = { key: string; value: string | number };

/**
 * 一个候选对象。除了下面的字段，其余一律不读；`payload` 存在时只用于兼容未知形态，
 * 且**永远**不会进入交接包（`handoverManifest` 只取显式字段）。
 */
export type DeliveryItem = {
  id: string;
  /** 对象自述所属项目；必须与当前会话项目一致。 */
  novel_id: string | null;
  kind: DeliveryItemKind | null;
  media_type: string | null;
  /** 项目内相对路径；`null` 表示原 owner 没有披露路径（保持缺失）。 */
  path: string | null;
  /** 原 owner 声明的版本号；缺失保持 `null`，绝不补 1。 */
  version: number | null;
  /** 原 owner 声明的 SHA-256；缺失保持 `null`。 */
  digest: string | null;
  size_bytes: number | null;
  visibility: DeliveryItemVisibility | null;
  /** 面向操作者的来源说明（有界）。 */
  source: string | null;
  /** 原 owner 是否自述该对象含凭据；为 `true` 时永远拒绝。 */
  contains_secret?: boolean;
  /** 未知的额外事实：原样保留但从不渲染，也从不进入交接包。 */
  payload?: DeliveryJson;
};

export type DeliveryJson = string | number | boolean | null | DeliveryJson[] | { [key: string]: DeliveryJson };

/* ------------------------------------------------------------------ 回执 */

/** 原 owner 的失败详情（`_run()` 写入的 `error`）。 */
export type DeliveryReceiptError = { code: string; message: string };

/** 缺失资源（`resource_manifest.missing`）。不完整资源包永远不会被当成完整交付。 */
export type DeliveryMissingResource = { id: string; reason: string | null };

/** 已经返回的导出回执。字段逐条对应 `_normalise_job()` + `public()` 的下发键。 */
export type DeliveryReceipt = {
  id: string;
  project_id: string;
  format: string;
  status: DeliveryJobStatus;
  /** 原 owner 未定义的状态码：`status` 会是 `null`，界面按"结果未知"呈现。 */
  raw_status: string | null;
  created_at: string;
  updated_at: string;
  progress: number;
  progress_message: string;
  attempt: number;
  retry_of: string | null;
  /** 原 owner 的恢复计数（`_recover_on_startup()`）。它证明原 owner 已经重排过队。 */
  recovery_count: number;
  snapshot_id: string | null;
  captured_at: string | null;
  source_versions: DeliverySourceVersion[];
  missing_resources: DeliveryMissingResource[];
  /** 只有 `succeeded` 且原 owner 下发了文件名时才存在。 */
  result_filename: string | null;
  /** 只有 `succeeded` 时才有意义；`null` 表示原 owner 没有给出可用文件名。 */
  error: DeliveryReceiptError | null;
};

/** `/api/exports` 的一页历史。 */
export type DeliveryReceiptPage = {
  items: DeliveryReceipt[];
  next_offset: number | null;
};

/**
 * 已经离开本机的导出请求。**只有原 owner 能派发**：这个记录只用来在回执丢失时
 * 按同一个幂等键重新读取，绝不是"可重放的命令"。
 */
export type DeliveryRequest = {
  /** 原 owner 归一化后的规范格式。 */
  format: DeliveryFormatId;
  /** 派发时使用的幂等键；原 owner 在 24 小时内会对它去重。 */
  idempotency_key: string;
  /** 派发时声明的分支（本地模式为 `null`）。 */
  branch_id: string | null;
  /** 派发时刻（原 owner 的时间戳，原样保留）。 */
  requested_at: string;
};

/** 一次导出尝试的完整记录：请求 + 可能拿不到的回执。 */
export type DeliveryAttempt = {
  project_id: string;
  request: DeliveryRequest;
  /** `null` 表示本机没有拿到回执 —— 这**不是**成功。 */
  receipt: DeliveryReceipt | null;
};

/* ------------------------------------------------------------------ 恢复计划 */

/** 恢复只允许读取。方法被冻结成 `GET`，结构上不可能再从本目录派发。 */
export type DeliveryReadPlan = {
  method: 'GET';
  path: string;
  /** 原请求的键，用于在返回页里找回**同一条**原任务。 */
  match: { format: string; idempotency_key: string; branch_id: string | null };
};

export type DeliveryRecovery = {
  state: DeliveryReceiptState;
  code: DeliveryRecoveryCode;
  /** 面向操作者的中文说明（有界）。 */
  instruction: string;
  /**
   * 原请求的**只读**复原：把当初的参数原样交回，供操作者/原 owner 核对。
   * 它带着 `dispatched: false`，本目录没有任何函数会把它变成新的派发；
   * 连请求记录都没有时为 `null`（缺失即缺失，不伪造一个请求）。
   */
  original_request: (DeliveryRequest & { dispatched: false }) | null;
  /** 本目录唯一能执行的恢复：重新读取原回执。 */
  read: DeliveryReadPlan | null;
  /** 原 owner 自己的重试端点（只展示；本目录从不调用它）。 */
  owner_retry_path: string | null;
  /** 只有原 owner 的状态确实成功时才为 `true`。 */
  confirmed_success: boolean;
};

/* ------------------------------------------------------------------ 限额报告 */

export type DeliveryLimitFact = {
  code: 'ITEM_BYTES' | 'PACKAGE_BYTES' | 'ITEM_COUNT';
  limit: number;
  observed: number;
  /** `true` 表示已经到达/超过上限，本次选择会被拒绝。 */
  exceeded: boolean;
  label: string;
};

export type DeliverySizeLimitsReport = {
  /** 选中对象的条数（已去重）。 */
  items: number;
  /** 已核对的字节合计；只要有对象字节缺失就不给出合计（`null`）。 */
  total_bytes: number | null;
  /** 字节缺失（`size_bytes === null`）的对象 id；它们无法核对限额。 */
  unmeasured: string[];
  limits: DeliveryLimitFact[];
  /** `EXCEEDED` 时整包被拒绝；`UNMEASURED` 表示有对象无法核对，不得当成通过。 */
  verdict: 'WITHIN_LIMITS' | 'EXCEEDED' | 'UNMEASURED';
  /** 无论哪种结论都为 `true`：本目录不会为了装下而放宽上限。 */
  limits_raised: false;
  /** 因为超限而被拒绝的对象 id。 */
  refused_items: string[];
};

/* ------------------------------------------------------------------ 界面状态 */

/** 显式数据面状态：`EMPTY` 只表示"读成功且真的没有内容"，绝不吞掉 `DENIED`。 */
export type DeliverySurfaceState = 'IDLE' | 'LOADING' | 'READY' | 'EMPTY' | 'DENIED' | 'FAILED';
export type DeliveryProblem = { code: string; message: string };

/* ------------------------------------------------------------------ 客户端与冻结 props */

export type DeliveryClient = {
  /** `/api/exports?novel_id=...` 的历史页。 */
  readReceipts: (signal?: AbortSignal) => Promise<DeliveryReceiptPage>;
  /** `/api/exports/{id}` 的单个回执。 */
  readReceipt: (jobId: string, signal?: AbortSignal) => Promise<DeliveryReceipt>;
};

/** 交接包中的一条：只包含可核对的最小事实。 */
export type HandoverEntry = {
  id: string;
  kind: DeliveryItemKind;
  version: number;
  digest: string;
  size_bytes: number;
  media_type: string | null;
  path: string | null;
};

export type HandoverExclusion = {
  id: string | null;
  kind: DeliveryItemKind | null;
  reason: DeliveryExclusionReason;
  code: string;
  message: string;
};

/** 工程交接包清单：纯数据，没有传输、没有会话、没有权限协商。 */
export type HandoverManifest = {
  project_id: string;
  identity: string;
  generated_from: 'SELECTION';
  entries: HandoverEntry[];
  excluded: HandoverExclusion[];
  total_bytes: number | null;
  /** 交接包只包含被显式勾选且身份有权导出的对象。 */
  explicitly_selected: true;
  /** 结构上不可能包含模型、依赖目录、凭据或他项目对象。 */
  contains_models: false;
  contains_dependencies: false;
  contains_credentials: false;
  contains_foreign_project_objects: false;
};

/** 导出可用性判定：拒绝与成功在类型上互斥，拒绝永远没有 `receipt`。 */
export type DeliveryItemExportDecision =
  | { state: 'EXPORTABLE'; item_id: string; kind: DeliveryItemKind; format: DeliveryFormatId; independent_of_project_completion: true }
  | {
      state: 'REFUSED'; item_id: string | null; kind: DeliveryItemKind | null;
      code: string; message: string; reason: DeliveryExclusionReason | null;
      available_formats: DeliveryFormatId[];
    };

export type DeliveryFormatRefusal = {
  state: 'REFUSED';
  code: string;
  message: string;
  requested_format: string;
  available_formats: DeliveryFormatId[];
};
