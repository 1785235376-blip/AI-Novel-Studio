// [HERMIA-FE-20261025 VERA-620963bf MF] 白名单裁定（option b）：普通模式只对后端 app/ 中“字面文案”的 code 显示服务端 message；
// 其余（str(exc)、动态 exc.code、未知 code）一律按 code/状态码友好文案，原文只进专业模式 technical。
// 本文件包含：app/ 契约扫描、Vera 20 条短绕过 × 三条路径、4 条合法文案、C2 / E2 变异击杀用例。
import { execFileSync } from "node:child_process";
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as A from "./api";
import { ApiError, api, apiErrorView, call, setApiErrorShellMode } from "./api";
import { setLocale } from "./i18n";
import { zhCN } from "./i18n/zh-CN";

const APP = resolve(__dirname, "../../app");
// [HERMIA-FE-20261025 VERA-e471dc76 P2-1] 契约扫描改用 Python ast（scripts/scan_error_codes.py），替代 regex+500 字符窗口：
// 覆盖跨行 "x" + str(exc)、隐式拼接 "x" f"{exc}"、dict(code=,message=)、任意键序、自定义异常/helper 构造 Foo("CODE", 变量)。
// 规格说明：旧 regex 的“同一行 str(exc)/f\"\" 即判动态”会把 AUDIO_PARAMETER_UNSUPPORTED 等误判为动态；ast 不再误判，但这些 code 仍保守留在名单外。
const SCANNER = resolve(__dirname, "../scripts/scan_error_codes.py");
type Scan = { literal: Record<string, string[]>; dynamic: Record<string, string[]> };
const scanDir = (dir: string): Scan => JSON.parse(execFileSync("python3", [SCANNER, dir], { encoding: "utf8", maxBuffer: 64 << 20 }));
function scanApp() {
  const s = scanDir(APP);
  return { literal: new Set(Object.keys(s.literal)), dynamic: new Set(Object.keys(s.dynamic)), raw: s };
}
const WL: ReadonlySet<string> = (A as any).LITERAL_MESSAGE_CODES ?? new Set();

describe("contract: whitelist vs backend app/ (read-only scan)", () => {
  const { literal, dynamic } = scanApp();
  it("scanner sees the str(exc) codes Vera listed (sanity)", () => {
    for (const c of ["WORKBENCH_INVALID", "PLANNING_INVALID", "INVALID_ASSET_REQUEST", "ASSET_IDEMPOTENCY_CONFLICT", "INVALID_CAPABILITY_REQUEST", "CREATION_RECORD_NOT_AVAILABLE", "IMPORT_AI_REVIEW_INVALID", "SOURCE_PRIVACY_REVIEW_REQUIRED", "EXPERIMENTAL_SOURCE_STALE", "INVALID_PROVIDER_CONFIG", "ASSET_INTEGRITY_FAILED", "IMAGE_EDIT_INVALID", "INVALID_WORKER_CONFIG", "EXPERIMENTAL_INVALID"]) expect(dynamic.has(c), c).toBe(true);
  });
  it("whitelist is non-empty and every whitelisted code exists in app/ with a literal message", () => {
    expect(WL.size).toBeGreaterThan(10);
    for (const c of WL) expect(literal.has(c), c).toBe(true);
  });
  it("no str(exc)/dynamic-message code is whitelisted", () => {
    expect([...WL].filter(c => dynamic.has(c))).toEqual([]);
  });
  it("HTTP_n and dynamic exc.code can never be whitelisted", () => {
    expect([...WL].filter(c => /^HTTP_/.test(c))).toEqual([]);
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

// [HERMIA-FE-20261025 VERA-e471dc76 P2-1] Vera 后端变异（backend-contract-mutations*.log）在临时副本上复现：真实 app/ 只读，从不改写。
describe("contract scanner catches Vera's backend mutants (temp copy, app/ untouched)", () => {
  const AP = "ai_planning_api.py", AB = "services/audiobook_service.py", API = "api.py";
  const L22 = 'raise HTTPException(409, {"code": "PLANNING_VERSION_CONFLICT", "message": "任务已更新，请刷新后重试。", "current": exc.current}) from exc';
  const K0 = 'raise HTTPException(409, {"code": "KNOWLEDGE_REVIEW_SOURCE_EMPTY", "message": "当前章节尚无可审查的正文"})';
  const AB0 = 'else: error = AudiobookError("SPEECH_SYNTHESIS_FAILED", "语音合成或音频验证失败", 502)';
  const P = "PLANNING_VERSION_CONFLICT", K = "KNOWLEDGE_REVIEW_SOURCE_EMPTY";
  const M: Array<[string, string, string, string, string]> = [
    ["B1 同行 str(exc)", AP, L22, `raise HTTPException(409, {"code": "${P}", "message": str(exc), "current": exc.current}) from exc`, P],
    ["B2 message=变量", AP, L22, `msg = str(exc)\n            raise HTTPException(409, {"code": "${P}", "message": msg, "current": exc.current}) from exc`, P],
    ["B3 跨行 f-string", AP, L22, `raise HTTPException(409, {"code": "${P}",\n                "message": (\n                    f"conflict {exc}"), "current": exc.current}) from exc`, P],
    ["B4 .format", AP, L22, `raise HTTPException(409, {"code": "${P}", "message": "冲突 {}".format(exc), "current": exc.current}) from exc`, P],
    ["B5 %", AP, L22, `raise HTTPException(409, {"code": "${P}", "message": "冲突 %s" % exc, "current": exc.current}) from exc`, P],
    ["B6 函数构造", AP, L22, `raise HTTPException(409, {"code": "${P}", "message": describe(exc), "current": exc.current}) from exc`, P],
    ["B7 字面后换行 + str(exc)", AP, L22, `raise HTTPException(409, {"code": "${P}", "message": "冲突："\n                + str(exc), "current": exc.current}) from exc`, P],
    ["B8 隐式拼接 \"x\" f\"{exc}\"", AP, L22, `raise HTTPException(409, {"code": "${P}", "message": ("冲突："\n                f"{exc}"), "current": exc.current}) from exc`, P],
    ["B9 message 在 code 前", AP, L22, `raise HTTPException(409, {\n                "message": str(exc),\n                "code": "${P}", "current": exc.current}) from exc`, P],
    ["B10 dict(code=,message=) 跨行", AP, L22, `raise HTTPException(409, dict(code="${P}",\n                message=str(exc))) from exc`, P],
    ["B11 repr(exc)", AP, L22, `raise HTTPException(409, {"code": "${P}", "message": repr(exc), "current": exc.current}) from exc`, P],
    ["B12 AudiobookError(白名单 code, 变量)", AB, AB0, 'else:\n                detail_text = str(exc)\n                error = AudiobookError("SPEECH_SYNTHESIS_FAILED", detail_text, 502)', "SPEECH_SYNTHESIS_FAILED"],
    ["K1 双出处一处 message=msg", API, K0, `msg = describe()\n        raise HTTPException(409, {"code": "${K}", "message": msg})`, K],
    ["K2 双出处一处 message 在前跨行", API, K0, `raise HTTPException(409, {\n            "message": str(exc),\n            "code": "${K}"})`, K],
    ["K3 双出处一处 dict(code=,message=) 跨行", API, K0, `raise HTTPException(409, dict(code="${K}",\n            message=str(exc)))`, K],
    ["K4 双出处一处跨行 f-string", API, K0, `raise HTTPException(409, {"code": "${K}",\n            "message": f"当前章节 {chapter} 尚无正文"})`, K],
  ];
  const withMutant = <T,>(file: string, from: string, to: string, fn: (dir: string) => T): T => {
    const dir = mkdtempSync(join(tmpdir(), "hermia-scan-"));
    try {
      const src = readFileSync(join(APP, file), "utf8");
      expect(src.includes(from), `pattern in ${file}`).toBe(true);
      writeFileSync(join(dir, "mutant.py"), src.replace(from, to));
      return fn(dir);
    } finally { rmSync(dir, { recursive: true, force: true }); }
  };
  it.each(M)("%s → flagged dynamic", (_n, file, from, to, code) => {
    // 动态集合是并集：仅扫描被改文件即可判定该 code 进入 dynamic → 白名单契约失败
    withMutant(file, from, to, dir => {
      const s = scanDir(dir);
      expect(s.dynamic[code], code).toBeTruthy();
      expect(WL.has(code)).toBe(true);
    });
  });
  it("baseline: the unmodified files produce no dynamic whitelisted code", () => {
    for (const f of [AP, AB, API]) withMutant(f, "", "", dir => expect([...WL].filter(c => scanDir(dir).dynamic[c])).toEqual([]));
  });
  it("B14 removing the only literal occurrence is detected (full temp copy)", () => {
    const dir = mkdtempSync(join(tmpdir(), "hermia-scan-full-"));
    try {
      cpSync(APP, dir, { recursive: true, filter: s => !s.includes("__pycache__") });
      const f = join(dir, API), from = 'raise HTTPException(400, {"code": "UNSUPPORTED_PROVIDER", "message": "不支持的服务商"})';
      const src = readFileSync(f, "utf8"); expect(src.includes(from)).toBe(true);
      writeFileSync(f, src.split(from).join(from.replace("UNSUPPORTED_PROVIDER", "UNSUPPORTED_PROVIDER_X")));
      const s = scanDir(dir);
      expect(s.literal.UNSUPPORTED_PROVIDER).toBeUndefined();
    } finally { rmSync(dir, { recursive: true, force: true }); }
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
  const { raw } = scanApp();
  const english = [...WL].flatMap(c => [...new Set((raw.literal[c] ?? []).filter(m => !/[\u4e00-\u9fff]/.test(m)))].map(m => [c, m] as const));
  it("SERVER_LITERAL_EN matches the backend literals exactly", () => {
    expect(Object.entries(A.SERVER_LITERAL_EN).sort()).toEqual([...english].sort());
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
  it("covers all 50 codes × 3 forms", () => { expect(WL.size).toBe(50); expect(rows.length).toBe(150); });
  it.each(rows)("%s via %s", async (code, form) => {
    serve(FORMS[form](code));
    const e = await caught(VIA.call);
    expect(e.problem.message_source).toBe("server");
    expect(apiErrorView(e).message).toBe(MSG);
  });
});
