// [HERMIA-FE-20261025 VERA-620963bf MF] 白名单裁定（option b）：普通模式只对后端 app/ 中“字面文案”的 code 显示服务端 message；
// 其余（str(exc)、动态 exc.code、未知 code）一律按 code/状态码友好文案，原文只进专业模式 technical。
// 本文件包含：app/ 契约扫描、Vera 20 条短绕过 × 三条路径、4 条合法文案、C2 / E2 变异击杀用例。
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as A from "./api";
import { ApiError, api, apiErrorView, call, setApiErrorShellMode } from "./api";
import { setLocale } from "./i18n";

const APP = resolve(__dirname, "../../app");
const pyFiles = (dir: string): string[] => readdirSync(dir).flatMap(n => { const p = join(dir, n); if (n === "__pycache__") return []; return statSync(p).isDirectory() ? pyFiles(p) : n.endsWith(".py") ? [p] : []; });
// 与 Vera 扫描同口径：dict 形式 {'code': 'X', ..., 'message': <expr>}，以及同一行内 'X' 与 str(exc)/f"" 并存
function scanApp() {
  const literal = new Set<string>(), dynamic = new Set<string>(), all = new Set<string>();
  for (const f of pyFiles(APP)) {
    const s = readFileSync(f, "utf8");
    for (const m of s.matchAll(/["']code["']\s*:\s*["']([A-Z][A-Z0-9_]+)["']/g)) {
      all.add(m[1]);
      let w = s.slice(m.index!, m.index! + 500), d = 0;
      for (let i = 0; i < w.length; i++) { const c = w[i]; if ("{[(".includes(c)) d++; else if ("}])".includes(c)) { if (d === 0) { w = w.slice(0, i); break; } d--; } }
      const mm = /["']message["']\s*:\s*(.+)/.exec(w);
      if (!mm) continue;
      const v = mm[1].trim();
      if (/^(["'])(?:(?!\1).)*\1\s*(,|$)/.test(v) || /^\(\s*["']/.test(v)) literal.add(m[1]); else dynamic.add(m[1]);
    }
    for (const line of s.split("\n")) {
      if (!/str\((?:exc|e|err|error)\)|\bf["']/.test(line)) continue;
      for (const m of line.matchAll(/["']([A-Z][A-Z0-9]*_[A-Z0-9_]+)["']/g)) dynamic.add(m[1]);
    }
  }
  return { literal, dynamic, all };
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
