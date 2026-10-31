// [HERMIA-FE-20261025 VERA-620963bf MF] 白名单裁定（option b）：普通模式只对后端 app/ 中“字面文案”的 code 显示服务端 message；
// 其余（str(exc)、动态 exc.code、未知 code）一律按 code/状态码友好文案，原文只进专业模式 technical。
// 本文件包含：app/ 契约扫描、Vera 20 条短绕过 × 三条路径、4 条合法文案、C2 / E2 变异击杀用例。
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as A from "./api";
import { ApiError, api, apiErrorView, call, setApiErrorShellMode } from "./api";
import { setLocale } from "./i18n";
import { registerApiErrorTranslator } from "./apiErrorMode";
import { t as tr } from "./i18n";
import { zhCN } from "./i18n/zh-CN";

const APP = resolve(__dirname, "../../app");
// [HERMIA-FE-20261025 VERA-e471dc76 P2-1] 契约扫描改用 Python ast（scripts/scan_error_codes.py），替代 regex+500 字符窗口：
// 覆盖跨行 "x" + str(exc)、隐式拼接 "x" f"{exc}"、dict(code=,message=)、任意键序、自定义异常/helper 构造 Foo("CODE", 变量)。
// 规格说明：旧 regex 的“同一行 str(exc)/f\"\" 即判动态”会把 AUDIO_PARAMETER_UNSUPPORTED 等误判为动态；ast 不再误判，但这些 code 仍保守留在名单外。
const SCANNER = resolve(__dirname, "../scripts/scan_error_codes.py");
type Scan = { literal: Record<string, string[]>; dynamic: Record<string, string[]>; unknown: string[]; enums: Record<string, string[]> };
// [HERMIA-FE-20261031] Windows 环境通常没有 python3 别名；优先显式 PYTHON，其次按平台回退。
const PYTHON = process.env.PYTHON ?? (process.platform === "win32" ? "python" : "python3");
const runScanner = (args: string[]): any => JSON.parse(execFileSync(PYTHON, [SCANNER, ...args], { encoding: "utf8", maxBuffer: 256 << 20 }));
const scanDir = (dir: string): Scan => runScanner([dir]);
// [HERMIA-FE-20261025 VERA-fbe029c4 P3] 缺少 python3 时不再在 collect 阶段整文件消失（692 例从计数中蒸发）：
// 扫描失败被记录，下方 "python3 scanner is available" 用例显式失败，其余契约用例同样显式失败；与扫描无关的用例照常运行。
let SCAN: Scan | undefined, SCAN_ERROR: string | undefined;
try { SCAN = scanDir(APP); } catch (e) { SCAN_ERROR = String((e as Error)?.message ?? e); }
const scan = (): Scan => { if (!SCAN) throw new Error(`backend contract scanner unavailable (python3 required): ${SCAN_ERROR}`); return SCAN; };
const WL: ReadonlySet<string> = (A as any).LITERAL_MESSAGE_CODES ?? new Set();
// [HERMIA-FE-20261025 VERA-fbe029c4 WL1d] 独立的人工审计期望清单（不从实现派生）：增删/等量替换名单成员都必须同时改这里。
const EXPECTED_WL = ["AUDIOBOOK_CONCATENATION_UNAVAILABLE", "AUDIOBOOK_SEGMENT_LIMIT", "AUDIOBOOK_SUBTITLES_UNAVAILABLE", "AUDIO_GENERATION_FAILED", "AUDIO_IMPORT_FAILED", "AUDIO_PARAMETER_UNSUPPORTED", "CANON_RECOVERY_REQUIRED", "CHAPTER_ARCHIVE_REQUIRED", "CHAPTER_REQUIRED", "CLOUD_PROMPT_REVIEW_REQUIRED", "CREATION_RECORD_LOCAL_ONLY", "EMOTION_DISCONTINUITY", "EXPORT_CANCELLED", "EXPORT_NOT_CANCELLABLE", "EXPORT_NOT_READY", "EXPORT_NOT_RETRYABLE", "EXPORT_RESULT_INVALID", "FORK_STALE_OR_CONFLICT", "IMAGE_EDIT_FAILED", "IMAGE_EDIT_PROVIDER_UNSUPPORTED", "IMAGE_IMPORT_FAILED", "IMAGE_PROVIDER_REQUEST_FAILED", "IMAGE_PROVIDER_UNAVAILABLE", "IMAGE_REFERENCE_URI_UNSAFE", "IMPORT_CLOUD_EXCERPT_CONFIRMATION_REQUIRED", "IMPORT_SOURCE_CHANGED", "IMPORT_SOURCE_RESTRICTED", "IMPORT_SOURCE_REVIEW_REQUIRED", "INVALID_EXPECTED_VERSION", "INVALID_VIDEO_PROVIDER_CONFIG", "KNOWLEDGE_REVIEW_SOURCE_EMPTY", "LEGACY_MEDIA_SCOPE_UNAVAILABLE", "LOCATION_JUMP", "NODE_EXECUTION_FAILED", "PLANNING_TARGET_CONFLICT", "PLANNING_VERSION_CONFLICT", "PLUGIN_HOST_ADMIN_REQUIRED", "PORTABLE_CHAPTER_VERSION_CONFLICT", "PRECONDITION_REQUIRED", "PREFERENCE_SHARE_CHANGED", "PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED", "REALTIME_VERSION_OR_SOURCE_CONFLICT", "SPEECH_PROVIDER_UNAVAILABLE", "SPEECH_SYNTHESIS_FAILED", "SYNC_STALE_OR_CONFLICT", "TIME_JUMP_CUT", "UNREVIEWED_CHAT_CONTEXT", "UNSUPPORTED_PROVIDER", "VISION_ANALYZE_FAILED", "WORKFLOW_EXECUTION_PROVENANCE_REQUIRED", "WORKFLOW_NODE_FAILED", "WORKFLOW_PROJECT_CHANGED"];
// 已审计的“code 不可证明 + 非字面 message”站点（exc.code 通用处理器等）。新增此类站点即契约失败，需人工审计后再加入。
const AUDITED_UNKNOWN = [
   "adaptation_api.py::create_adaptation_router::text if text.isupper() else 'ADAPTATION_INVALID'",
   "api.py::agent_chat::exc.code.value",
   "api.py::ai_analyze_import_knowledge::exc.code.value",
   "api.py::cancel_audiobook_job::exc.code",
   "api.py::capability_guard::exc.code",
   "api.py::execute_audiobook_job::exc.code",
   "api.py::export_audiobook_chapter::exc.code",
   "api.py::guard::exc.code",
   "api.py::local_text_runtime_diagnostics::exc.code.value",
   "api.py::plugin_catalog_guard::exc.code",
   "api.py::queue_audiobook_chapter::exc.code",
   "api.py::queue_audiobook_segments::exc.code",
   "api.py::retry_audiobook_job::exc.code",
   "api.py::update_chapter::exc.code",
   "collaboration_admin.py::_error::code",
   "collaboration_api.py::_error::code",
   "creative/director_intent.py::project_shot_card::projected_camera['classification']['camera_motion']",
   "creative/director_intent.py::project_shot_card::projected_camera['classification']['composition']",
   "creative/director_intent.py::project_shot_card::projected_camera['classification']['lens']",
   "creative/prompt_authoring.py::public::self.code",
   "experimental/director.py::camera_checks::**item",
   "experimental/interactive_export_contract.py::artifact_evidence::found",
   "experimental/interactive_godot_export.py::_analysis_issue::'GODOT_RUNTIME_ANALYSIS:' + str(issue.get('code', 'UNKNOWN'))[:90]",
   "experimental/interactive_targets/ink/current_artifact.py::_issue_records::code",
   "experimental/reader_preflight.py::preflight::code",
   "experimental/revision_intelligence_api.py::create_revision_intelligence_router::exc.code",
   "experimental/story_simulator.py::violation::code",
   "experimental/voice_direction_api.py::create_voice_direction_router::exc.code",
   "experimental/world.py::continuity::code",
   "local_interop/api.py::error_response::code",
   "main.py::unified_http_error::code",
   "packaging/bootstrap_api.py::create_packaged_bootstrap_router::exc.code"
  ];
// 契约本体：真实 app/ 与变异副本共用同一个判定函数（变异是否被杀，看的就是这个函数）。
function contractViolations(s: Scan, wl: ReadonlySet<string> = WL): string[] {
  const v: string[] = [];
  for (const c of wl) {
    if (!s.literal[c]) v.push(`WL code has no literal site: ${c}`);
    if (s.dynamic[c]) v.push(`WL code has dynamic site: ${c} @ ${s.dynamic[c].join(", ")}`);
    if (/^HTTP_/.test(c)) v.push(`HTTP_n whitelisted: ${c}`);
  }
  // [HERMIA-FE-20261025 VERA-fbe029c4 §2] RuntimeErrorCode（ModelRuntimeError，jobs.py:770 为 str(exc)）永不进白名单。
  for (const c of s.enums.RuntimeErrorCode ?? []) if (wl.has(c)) v.push(`RuntimeErrorCode whitelisted: ${c}`);
  if (!(s.enums.RuntimeErrorCode ?? []).length) v.push("RuntimeErrorCode enum not found by scanner");
  for (const u of s.unknown) if (!AUDITED_UNKNOWN.includes(u)) v.push(`unaudited unprovable-code site: ${u}`);
  return v;
}

describe("contract: whitelist vs backend app/ (read-only scan)", () => {
  it("python3 scanner is available (explicit failure instead of silently dropping the suite)", () => {
    expect(SCAN_ERROR).toBeUndefined();
    expect(SCAN).toBeDefined();
  });
  it("scanner sees the str(exc) codes Vera listed (sanity)", () => {
    const { dynamic } = scan();
    for (const c of ["WORKBENCH_INVALID", "PLANNING_INVALID", "INVALID_ASSET_REQUEST", "ASSET_IDEMPOTENCY_CONFLICT", "INVALID_CAPABILITY_REQUEST", "CREATION_RECORD_NOT_AVAILABLE", "IMPORT_AI_REVIEW_INVALID", "SOURCE_PRIVACY_REVIEW_REQUIRED", "EXPERIMENTAL_SOURCE_STALE", "INVALID_PROVIDER_CONFIG", "ASSET_INTEGRITY_FAILED", "IMAGE_EDIT_INVALID", "INVALID_WORKER_CONFIG", "EXPERIMENTAL_INVALID"]) expect(dynamic[c], c).toBeTruthy();
  });
  it("WL1d: whitelist equals the independent audited list", () => {
    expect([...WL].sort()).toEqual([...EXPECTED_WL].sort());
    expect(WL.size).toBe(52);
  });
  it("contract holds on the real app/", () => {
    expect(contractViolations(scan())).toEqual([]);
  });
  it("RuntimeErrorCode: resolved via Enum, jobs.py:770 str(exc) is dynamic, none whitelisted", () => {
    const s = scan();
    expect(s.enums.RuntimeErrorCode).toContain("INVALID_REQUEST");
    expect(s.dynamic.INVALID_REQUEST?.some(w => w.startsWith("jobs.py:"))).toBe(true);
    expect(s.enums.RuntimeErrorCode.filter(c => WL.has(c))).toEqual([]);
    // TEXT_PROVIDER_NOT_CONFIGURED：memory_agent 以内部 token 作 message，经 exc.safe_message 透出 → 动态，不得进名单
    expect(s.dynamic.TEXT_PROVIDER_NOT_CONFIGURED).toBeTruthy();
    expect(WL.has("TEXT_PROVIDER_NOT_CONFIGURED")).toBe(false);
  });
  it("env/const names are not counted as literal error codes", () => {
    const lit = Object.keys(scan().literal);
    for (const c of ["DATABASE_URL", "Q4_K_M", "OPENAI_API_KEY"]) expect(lit, c).not.toContain(c);
  });
  it("AUDIO_PARAMETER_UNSUPPORTED / IMAGE_PROVIDER_REQUEST_FAILED: every site is literal", () => {
    const s = scan();
    for (const c of ["AUDIO_PARAMETER_UNSUPPORTED", "IMAGE_PROVIDER_REQUEST_FAILED"]) { expect(s.literal[c]?.length, c).toBeGreaterThan(0); expect(s.dynamic[c], c).toBeUndefined(); }
  });
});

type Inj = { status: number; ct: string; body: string };
const env = (status: number, detail: any): Inj => {
  let code: string, message: string, details: any;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) { code = String(detail.code || `HTTP_${status}`); message = String(detail.message || detail.detail || code); details = detail.details ?? detail; }
  else { code = `HTTP_${status}`; message = String(detail); details = {}; }
  return { status, ct: "application/json", body: JSON.stringify({ detail, code, message, details, request_id: "r-" + status }) };
};
const serve = (v: Inj) => vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(v.body, { status: v.status, headers: { "content-type": v.ct } }));
const VIA = { call: () => call("/api/probe"), exportDownload: () => api.exportDownload("job1"), assetDownload: () => api.assetDownload("a1", "n1") } as const;
const caught = async (fn: () => Promise<unknown>) => { try { await fn(); } catch (e) { return e as ApiError; } throw new Error("no throw"); };
afterEach(() => { vi.restoreAllMocks(); setApiErrorShellMode("basic"); setLocale("zh-CN"); });

// Vera bypass-probe.txt 的 20+ 条短原文（<200 字，旧规则表放行）
const SHORT = ["'title'", "unsupported operand type(s) for +: 'int' and 'str'", "__init__() got an unexpected keyword argument 'foo'", "Expecting value: line 1 column 1 (char 0)", "too many values to unpack (expected 2)", "cannot open data/x", "missing uploads/abc", "cannot read 'secrets.toml'", "no such table: assets", "no such column: novels.owner_id", "database is locked", 'insert or update on table "assets" violates foreign key', "connect to 10.0.3.7:5432 refused", "http://127.0.0.1:11434 unreachable", "OPENAI_API_KEY=sk-abc123 invalid", "$HOME not set", 'cannot open "novel_42.sqlite"', "/etc missing", "bad file /secret.db", "..\\..\\secret.db", "math domain error", "{'novel_id': 'n1', 'token': 'abc'}"];
const DYN_CODES = ["INVALID_ASSET_REQUEST", "INVALID_CAPABILITY_REQUEST", "WORKBENCH_INVALID", "PLANNING_INVALID", "AUDIOBOOK_VOICE_DYNAMIC", "SOME_UNKNOWN_CODE"];
const cases = DYN_CODES.flatMap(code => SHORT.map(t => [code, t] as const));
describe.each(Object.keys(VIA) as Array<keyof typeof VIA>)("short raw messages via %s", via => {
  it.each(cases)("basic: %s / %s → friendly only", async (code, text) => {
    serve(env(400, { code, message: text }));
    const e = await caught(VIA[via]);
    const v = apiErrorView(e, "操作失败");
    expect(v.message).not.toContain(text);
    expect(e.message).not.toContain(text);
    expect(v.message).toMatch(/[\u4e00-\u9fff]/);
    expect(v.technical).toBeUndefined();
    expect(e.problem.message_source).toBe("fallback");
  });
  it.each(SHORT)("pro: technical carries raw text: %s", async text => {
    setApiErrorShellMode("pro");
    serve(env(400, { code: "INVALID_ASSET_REQUEST", message: text }));
    const v = apiErrorView(await caught(VIA[via]));
    expect(v.message).not.toContain(text);
    expect(v.technical).toBe(text);
  });
});

describe("legitimate copy is displayed", () => {
  const LEGIT = ["比例需在 1/2.5 之间", "Terror theme is not allowed", "请选择 JSON/YAML.zip 文件", "Each line 2 must be filled", "任务已更新，请刷新后重试。", "Chapter was modified elsewhere, please reload."];
  it.each(LEGIT)("whitelisted code shows: %s", async text => {
    serve(env(409, { code: "PLANNING_VERSION_CONFLICT", message: text }));
    expect(apiErrorView(await caught(VIA.call)).message).toBe(text);
  });
  it.each(LEGIT)("frontend-local Error is never sanitized: %s", text => {
    expect(apiErrorView(new Error(text), "操作失败").message).toBe(text);
  });
});

describe("mutation killers", () => {
  it("C2: code carried only in detail.code is honoured", async () => {
    serve({ status: 409, ct: "application/json", body: JSON.stringify({ detail: { code: "PLANNING_VERSION_CONFLICT", message: "任务已更新，请刷新后重试。" } }) });
    expect(apiErrorView(await caught(VIA.call)).message).toBe("任务已更新，请刷新后重试。");
    vi.restoreAllMocks();
    serve({ status: 400, ct: "application/json", body: JSON.stringify({ detail: { code: "INVALID_ASSET_REQUEST", message: "unsupported operand" } }) });
    expect(apiErrorView(await caught(VIA.call)).message).not.toContain("unsupported");
  });
  it("C2: HTTP_n top-level code does not mask a whitelisted detail.code", async () => {
    serve({ status: 409, ct: "application/json", body: JSON.stringify({ code: "HTTP_409", detail: { code: "PLANNING_VERSION_CONFLICT", message: "任务已更新" } }) });
    expect(apiErrorView(await caught(VIA.call)).message).toBe("任务已更新");
  });
  it("E2: dict message equal to dict detail (explicit message) is kept", async () => {
    serve(env(409, { code: "PLANNING_VERSION_CONFLICT", message: "任务已更新", detail: "任务已更新" }));
    expect(apiErrorView(await caught(VIA.call)).message).toBe("任务已更新");
  });
  it("E2 counterpart: detail echoed into message without explicit message is raw", async () => {
    serve(env(409, { code: "PLANNING_VERSION_CONFLICT", detail: "stale thing" }));
    expect(apiErrorView(await caught(VIA.call)).message).not.toBe("stale thing");
  });
});

// [HERMIA-FE-20261025 VERA-e471dc76 P2-1 / VERA-fbe029c4 §5] Vera 后端变异：扫描器在内存中替换单个文件后对整个 app/ 重新扫描
// （真实 app/ 只读，从不改写），再交给与真实契约同一个 contractViolations() 判定。不再依赖“变异 code 进入 dynamic”的旁路断言。
describe("contract kills Vera's backend mutants (in-memory copy, app/ untouched)", () => {
  const AP = "ai_planning_api.py", AB = "services/audiobook_service.py", API = "api.py";
  const L22 = 'raise HTTPException(409, {"code": "PLANNING_VERSION_CONFLICT", "message": "任务已更新，请刷新后重试。", "current": exc.current}) from exc';
  const K0 = 'raise HTTPException(409, {"code": "KNOWLEDGE_REVIEW_SOURCE_EMPTY", "message": "当前章节尚无可审查的正文"})';
  const KB = 'raise HTTPException(409, {"code": "KNOWLEDGE_REVIEW_SOURCE_EMPTY", "message": "小说尚无可审查的章节正文"})'; // api.py:2035
  const AB0 = 'else: error = AudiobookError("SPEECH_SYNTHESIS_FAILED", "语音合成或音频验证失败", 502)';
  const P = "PLANNING_VERSION_CONFLICT", K = "KNOWLEDGE_REVIEW_SOURCE_EMPTY", I = "        ";
  const M: Array<[string, string, string, string]> = [
    ["B1 同行 str(exc)", AP, L22, `raise HTTPException(409, {"code": "${P}", "message": str(exc), "current": exc.current}) from exc`],
    ["B2 message=变量", AP, L22, `msg = str(exc)\n            raise HTTPException(409, {"code": "${P}", "message": msg, "current": exc.current}) from exc`],
    ["B3 跨行 f-string", AP, L22, `raise HTTPException(409, {"code": "${P}",\n                "message": (\n                    f"conflict {exc}"), "current": exc.current}) from exc`],
    ["B4 .format", AP, L22, `raise HTTPException(409, {"code": "${P}", "message": "冲突 {}".format(exc), "current": exc.current}) from exc`],
    ["B5 %", AP, L22, `raise HTTPException(409, {"code": "${P}", "message": "冲突 %s" % exc, "current": exc.current}) from exc`],
    ["B6 函数构造", AP, L22, `raise HTTPException(409, {"code": "${P}", "message": describe(exc), "current": exc.current}) from exc`],
    ["B7 字面后换行 + str(exc)", AP, L22, `raise HTTPException(409, {"code": "${P}", "message": "冲突："\n                + str(exc), "current": exc.current}) from exc`],
    ["B8 隐式拼接 \"x\" f\"{exc}\"", AP, L22, `raise HTTPException(409, {"code": "${P}", "message": ("冲突："\n                f"{exc}"), "current": exc.current}) from exc`],
    ["B9 message 在 code 前", AP, L22, `raise HTTPException(409, {\n                "message": str(exc),\n                "code": "${P}", "current": exc.current}) from exc`],
    ["B10 dict(code=,message=) 跨行", AP, L22, `raise HTTPException(409, dict(code="${P}",\n                message=str(exc))) from exc`],
    ["B11 repr(exc)", AP, L22, `raise HTTPException(409, {"code": "${P}", "message": repr(exc), "current": exc.current}) from exc`],
    ["B12 AudiobookError(白名单 code, 变量)", AB, AB0, 'else:\n                detail_text = str(exc)\n                error = AudiobookError("SPEECH_SYNTHESIS_FAILED", detail_text, 502)'],
    ["B14 删除唯一字面出处", API, 'raise HTTPException(400, {"code": "UNSUPPORTED_PROVIDER", "message": "不支持的服务商"})', 'raise HTTPException(400, {"code": "UNSUPPORTED_PROVIDER_X", "message": "不支持的服务商"})'],
    ["K1 双出处一处 message=msg", API, K0, `msg = describe()\n${I}raise HTTPException(409, {"code": "${K}", "message": msg})`],
    ["K2 双出处一处 message 在前跨行", API, K0, `raise HTTPException(409, {\n            "message": str(exc),\n            "code": "${K}"})`],
    ["K3 双出处一处 dict(code=,message=) 跨行", API, K0, `raise HTTPException(409, dict(code="${K}",\n            message=str(exc)))`],
    ["K4 双出处一处跨行 f-string", API, K0, `raise HTTPException(409, {"code": "${K}",\n            "message": f"当前章节 {chapter} 尚无正文"})`],
    // Vera fbe029c4 §5：多出处 code（api.py:2035）上的 9 个盲区变异
    ["mK1 **dict 展开 message", API, KB, `raise HTTPException(409, {"code": "${K}", **{"message": str(exc)}})`],
    ["mK2 **base 展开（base 携带 code）", API, KB, `base = {"code": "${K}"}\n${I}raise HTTPException(409, {**base, "message": str(exc)})`],
    ["mK3 下标赋值 body['message']", API, KB, `body = {"code": "${K}", "message": "小说尚无可审查的章节正文"}\n${I}body["message"] = str(exc)\n${I}raise HTTPException(409, body)`],
    ["mK5 code=, **{message}", API, KB, `raise ApiErr(code="${K}", **{"message": str(exc)})`],
    ["mI1 子类类属性 code", API, KB, `class _C(HTTPException):\n${I}    code = "${K}"\n${I}raise _C(str(exc))`],
    ["mD1 常量变量 code", API, KB, `_VERA_C = "${K}"\n${I}raise HTTPException(409, {"code": _VERA_C, "message": str(exc)})`],
    ["mD2 exc.code", API, KB, `raise HTTPException(409, {"code": exc.code, "message": str(exc)})`],
    ["mD3 Enum .value", API, KB, `raise HTTPException(409, {"code": Codes.${K}.value, "message": str(exc)})`],
    ["mS3 reason 键", API, KB, `raise HTTPException(409, {"code": "${K}", "reason": str(exc)})`],
    // 额外：dict.update、f-string code
    ["K6 dict.update", API, KB, `body = {"code": "${K}", "message": "小说尚无可审查的章节正文"}\n${I}body.update(message=str(exc))\n${I}raise HTTPException(409, body)`],
    ["D4 f-string code", API, KB, `raise HTTPException(409, {"code": f"KNOWLEDGE_{k}_EMPTY", "message": str(exc)})`],
  ];
  let RES: Record<string, Scan & { error?: string }> | undefined, ERR: string | undefined;
  try {
    const dir = mkdtempSync(join(tmpdir(), "hermia-mut-"));
    try {
      const f = join(dir, "mutants.json");
      writeFileSync(f, JSON.stringify([{ name: "BASELINE", file: API, from: "", to: "" }, ...M.map(([name, file, from, to]) => ({ name, file, from, to }))]));
      RES = runScanner([APP, "--mutants", f]);
    } finally { rmSync(dir, { recursive: true, force: true }); }
  } catch (e) { ERR = String((e as Error)?.message ?? e); }
  const res = (n: string) => { if (!RES) throw new Error(`scanner unavailable: ${ERR}`); const r = RES[n]; expect(r?.error, n).toBeUndefined(); return r; };
  it("baseline (no mutation) satisfies the contract", () => { expect(contractViolations(res("BASELINE"))).toEqual([]); });
  it.each(M)("%s → contract violated", name => {
    expect(contractViolations(res(name)).length, name).toBeGreaterThan(0);
  });
  it("covers Vera's 9 multi-site mutants on KNOWLEDGE_REVIEW_SOURCE_EMPTY", () => {
    expect(M.filter(([n]) => /^m[KIDS]\d/.test(n)).length).toBe(9);
  });
});

// [HERMIA-FE-20261025 VERA-e471dc76 P2-2] C1：两名单不相交（原 api.ts 中的 RAW 检查为死代码，已删除，改由此断言守护）。N8：message===code 不显示裸 code。
describe("P2-2 coverage restored", () => {
  it("C1: RAW_MESSAGE_CODES and LITERAL_MESSAGE_CODES are disjoint", () => {
    expect([...A.RAW_MESSAGE_CODES].filter(c => WL.has(c))).toEqual([]);
  });
  it.each(["CANON_RECOVERY_REQUIRED", "EXPORT_CANCELLED", "PLANNING_VERSION_CONFLICT"])("N8: %s with message===code never shows the bare code", async code => {
    expect(WL.has(code)).toBe(true);
    serve(env(409, { code }));
    const e = await caught(VIA.call);
    const v = apiErrorView(e, "操作失败");
    expect(v.message).not.toContain(code);
    expect(e.problem.message_source).toBe("fallback");
    vi.restoreAllMocks();
    serve(env(409, { code, message: code }));
    expect(apiErrorView(await caught(VIA.call)).message).not.toContain(code);
  });
});

// [HERMIA-FE-20261025 VERA-e471dc76 P3-1] 白名单内英文后端字面文案：中文界面显示中文，英文界面保持原文。
describe("P3-1 English server literals are localized", () => {
  const english = Object.entries(A.SERVER_LITERAL_EN) as Array<[string, string]>;
  it("SERVER_LITERAL_EN matches the backend literals exactly", () => {
    const { literal } = scan();
    const fromScan = [...WL].flatMap(c => [...new Set((literal[c] ?? []).filter(m => !/[\u4e00-\u9fff]/.test(m)))].map(m => [c, m]));
    expect([...english].sort()).toEqual(fromScan.sort());
  });
  it("scanner finds the English literals (incl. export cancelled)", () => {
    expect(english.map(([, m]) => m)).toContain("export cancelled");
    expect(english.length).toBeGreaterThanOrEqual(10);
  });
  it.each(english)("zh: %s %s → Chinese", async (code, text) => {
    expect((zhCN as Record<string, string>)[`err.srv.${code}`], code).toMatch(/[\u4e00-\u9fff]/);
    serve(env(409, { code, message: text }));
    const e = await caught(VIA.call);
    expect(e.problem.message_source).toBe("server");
    expect(apiErrorView(e).message).toBe((zhCN as Record<string, string>)[`err.srv.${code}`]);
  });
  it.each(english)("en: %s %s → original English", async (code, text) => {
    setLocale("en");
    serve(env(409, { code, message: text }));
    expect(apiErrorView(await caught(VIA.call)).message).toBe(text);
  });
  it("zh: a different English message for the same code is shown as-is (only exact literals are mapped)", async () => {
    serve(env(409, { code: "EXPORT_CANCELLED", message: "Export was cancelled by another tab." }));
    expect(apiErrorView(await caught(VIA.call)).message).toBe("Export was cancelled by another tab.");
  });
});

// [HERMIA-FE-20261025 VERA-e471dc76 P3-2] 「文案保留」参数化到全部白名单 code × 三种信封形态（WL1b/WL1c 类删名单变异可被击杀）。
describe("P3-2 every whitelisted code preserves its message in all envelope forms", () => {
  const MSG = "自定义提示：请刷新后重试。";
  const FORMS = {
    top: (code: string) => env(409, { code, message: MSG }),
    detailOnly: (code: string): Inj => ({ status: 409, ct: "application/json", body: JSON.stringify({ detail: { code, message: MSG } }) }),
    httpTopDetailCode: (code: string): Inj => ({ status: 409, ct: "application/json", body: JSON.stringify({ code: "HTTP_409", message: MSG, detail: { code, message: MSG } }) }),
  } as const;
  const rows = [...WL].sort().flatMap(code => (Object.keys(FORMS) as Array<keyof typeof FORMS>).map(form => [code, form] as const));
  it("covers all 52 codes × 3 forms", () => { expect(WL.size).toBe(52); expect(rows.length).toBe(156); });
  it.each(rows)("%s via %s", async (code, form) => {
    serve(FORMS[form](code));
    const e = await caught(VIA.call);
    expect(e.problem.message_source).toBe("server");
    expect(apiErrorView(e).message).toBe(MSG);
  });
});

// [HERMIA-FE-20261025 VERA-fbe029c4 §4] 存活变异 N8b / S3 / S4 的击杀用例；TEXT_PROVIDER_NOT_CONFIGURED 的专属友好文案。
describe("fbe029c4 survivors", () => {
  it("N8b: message equal to code modulo surrounding whitespace is not shown", async () => {
    serve(env(409, { code: "EXPORT_CANCELLED", message: "  EXPORT_CANCELLED  " }));
    const e = await caught(VIA.call);
    expect(apiErrorView(e).message).not.toContain("EXPORT_CANCELLED");
    expect(e.problem.message_source).toBe("fallback");
  });
  it("S3: a missing err.srv translation falls back to the server text, never to the bare code", async () => {
    registerApiErrorTranslator(() => "");
    try {
      serve(env(409, { code: "EXPORT_CANCELLED", message: "export cancelled" }));
      const m = apiErrorView(await caught(VIA.call)).message;
      expect(m).toBe("export cancelled");
      expect(m).not.toContain("EXPORT_CANCELLED");
    } finally { registerApiErrorTranslator((key) => (key.startsWith("err.") && key in zhCN ? tr(key as any) : "")); }
  });
  it.each(["Export cancelled", "EXPORT CANCELLED", "export  cancelled", " export cancelled"])("S4: only the exact literal is mapped, not %j", async text => {
    serve(env(409, { code: "EXPORT_CANCELLED", message: text }));
    expect(apiErrorView(await caught(VIA.call)).message).toBe(text);
  });
  it("TEXT_PROVIDER_NOT_CONFIGURED stays out of the whitelist but has dedicated friendly copy (zh + en)", async () => {
    expect(WL.has("TEXT_PROVIDER_NOT_CONFIGURED")).toBe(false);
    serve(env(503, { code: "TEXT_PROVIDER_NOT_CONFIGURED", message: "MEMORY_LOCAL_PROVIDER_NOT_CONFIGURED" }));
    const e = await caught(VIA.call);
    expect(apiErrorView(e).message).toBe(zhCN["err.code.TEXT_PROVIDER_NOT_CONFIGURED" as keyof typeof zhCN]);
    expect(apiErrorView(e).message).not.toContain("MEMORY_");
    vi.restoreAllMocks(); setLocale("en");
    serve(env(503, { code: "TEXT_PROVIDER_NOT_CONFIGURED", message: "未配置可用文本模型" }));
    expect(apiErrorView(await caught(VIA.call)).message).toMatch(/text model/i);
  });
  it("zh copy of INVALID_EXPECTED_VERSION / PRECONDITION_REQUIRED has no developer field names", () => {
    for (const c of ["INVALID_EXPECTED_VERSION", "PRECONDITION_REQUIRED"]) expect((zhCN as Record<string, string>)[`err.srv.${c}`]).not.toMatch(/[a-z]_[a-z]|[A-Za-z]{3,}/);
  });
});
