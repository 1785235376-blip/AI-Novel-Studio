// [HERMIA-FE-20261025 VERA-F70 MF-1/MF-2/P2] Vera @f703b17e 的 15 种注入（duim-f703b17e/inj.mjs），call() 与 downloadCall() 同测；
// 过滤规则逐条独立；str(exc) 业务 code 默认按原文；N6/N7/N9 各自独立用例。
import { afterEach, describe, expect, it, vi } from "vitest";
import * as A from "./api";
import { ApiError, api, apiErrorView, call, setApiErrorShellMode } from "./api";
// 规格常量写死在测试里（Vera 列出的后端 str(exc) code；上限 200），并与实现导出逐一比对
const SPEC_RAW_CODES = ["INVALID_PROVIDER_CONFIG", "ASSET_INTEGRITY_FAILED", "IMAGE_EDIT_INVALID", "INVALID_WORKER_CONFIG", "EXPERIMENTAL_INVALID"];
const SERVER_MESSAGE_LIMIT = 200;
const UNSAFE_SERVER_RULES: ReadonlyArray<readonly [string, RegExp]> = (A as any).UNSAFE_SERVER_RULES ?? [];
import { setLocale } from "./i18n";

type Inj = { status: number; ct: string; body: string };
// 与 app/main.py unified_http_error 以及 Vera inj.mjs 的 env() 相同
const env = (status: number, detail: any): Inj => {
  let code: string, message: string, details: any;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) { code = String(detail.code || `HTTP_${status}`); message = String(detail.message || detail.detail || code); details = detail.details ?? detail; }
  else { code = `HTTP_${status}`; message = String(detail); details = {}; }
  return { status, ct: "application/json", body: JSON.stringify({ detail, code, message, details, request_id: "r-" + status }) };
};
const V: Record<string, Inj> = {
  strTrace: env(500, 'Traceback (most recent call last): File "/srv/app/api.py", line 9 SECRET-A'),
  strPlain: env(404, "Chapter not found SECRET-B"),
  strZh: env(400, "章节编号重复 SECRET-C"),
  dictCodeSafe: env(409, { code: "VERSION_CONFLICT", message: "章节已被其他人修改，请刷新后重试 SAFE-D", details: { expected_version: 3, actual_version: 4 } }),
  dictNoCodeSafe: env(409, { message: "草稿已过期，请重新读取 SAFE-E" }),
  dictNoCodeDetail: env(400, { detail: "invalid literal for int() with base 10: SECRET-F" }),
  dictCodeExcStr: env(400, { code: "INVALID_PROVIDER_CONFIG", message: "[Errno 2] No such file or directory: 'config/providers/SECRET-G.toml'" }),
  dictCodeSql: env(409, { code: "ASSET_INTEGRITY_FAILED", message: "UNIQUE constraint failed: assets.sha256 SECRET-H" }),
  dictCodeWin: env(400, { code: "X", message: "无法读取 C:\\Users\\bob\\SECRET-I.db" }),
  dictCodeRel: env(400, { code: "X", message: "cannot open ./data/novels/SECRET-J.json" }),
  dictCodeUnc: env(400, { code: "X", message: "\\\\fileserver\\share\\SECRET-K" }),
  dictCodeLong: env(400, { code: "X", message: "SECRET-L " + "很长的服务端文本".repeat(200) }),
  dictCodeDataAbs: env(500, { code: "X", message: "open failed /data/poemseed/SECRET-M.db" }),
  plain500: { status: 500, ct: "text/plain", body: "Traceback SECRET-N /home/u/.env" },
  html502: { status: 502, ct: "text/html", body: "<html>nginx SECRET-O</html>" },
  revLock: { status: 409, ct: "application/json", body: JSON.stringify({ code: "REVISION_LOCKED", message: "段落已锁定或锁定依据已变化。请核对后明确解锁，再采用 AI 修改。", details: {}, request_id: "r" }) },
};
const serve = (v: Inj) => vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(v.body, { status: v.status, headers: { "content-type": v.ct } }));
const VIA = {
  call: () => call("/api/probe"),
  exportDownload: () => api.exportDownload("job1"),
  assetDownload: () => api.assetDownload("a1", "n1"),
} as const;
const caught = async (fn: () => Promise<unknown>) => { try { await fn(); } catch (e) { return e as ApiError; } throw new Error("no throw"); };

afterEach(() => { vi.restoreAllMocks(); setApiErrorShellMode("basic"); setLocale("zh-CN"); });

const SECRET_CASES = Object.keys(V).filter(k => /SECRET/.test(V[k].body));
describe.each(Object.keys(VIA) as Array<keyof typeof VIA>)("Vera 15-case injection via %s", via => {
  it.each(SECRET_CASES)("basic: %s never shows server text", async k => {
    serve(V[k]);
    const e = await caught(VIA[via]);
    expect(e).toBeInstanceOf(ApiError);
    const v = apiErrorView(e, "操作失败");
    expect(v.message).not.toMatch(/SECRET|Traceback|<html|Errno|constraint|\\\\|\/data\//);
    expect(e.message).not.toMatch(/SECRET/);
    expect(v.technical).toBeUndefined();
    expect(e.problem.message_source).toBe("fallback");
  });
  it.each(SECRET_CASES)("pro: %s raw text only in technical (≤500)", async k => {
    setApiErrorShellMode("pro");
    serve(V[k]);
    const v = apiErrorView(await caught(VIA[via]), "操作失败");
    expect(v.message).not.toMatch(/SECRET/);
    expect(v.technical).toMatch(/SECRET/);
    expect(v.technical!.length).toBeLessThanOrEqual(500);
  });
  it.each([["dictCodeSafe", "SAFE-D"], ["dictNoCodeSafe", "SAFE-E"], ["revLock", "段落已锁定"]])("legit %s message kept", async (k, needle) => {
    serve(V[k]);
    const v = apiErrorView(await caught(VIA[via]), "操作失败");
    expect(v.message).toContain(needle);
  });
});

describe("str(exc) business codes use per-code friendly copy", () => {
  it("exports match the spec", () => {
    expect([...((A as any).RAW_MESSAGE_CODES ?? [])].sort()).toEqual([...SPEC_RAW_CODES].sort());
    expect((A as any).SERVER_MESSAGE_LIMIT).toBe(SERVER_MESSAGE_LIMIT);
  });
  it.each(SPEC_RAW_CODES)("%s: safe-looking message is still treated as raw (zh + en)", async code => {
    serve(env(400, { code, message: "bad value for field" }));
    const e = await caught(VIA.call);
    const zh = apiErrorView(e).message;
    expect(zh).not.toMatch(/bad value/);
    expect(zh).toMatch(/[\u4e00-\u9fff]/);
    expect(zh).not.toBe("请求内容有误，请检查后重试"); // 按 code，不是按状态码
    setLocale("en");
    const en = apiErrorView(e).message;
    expect(en).not.toMatch(/bad value|[\u4e00-\u9fff]/);
  });
});

describe("unsafe rules are each independently load-bearing", () => {
  // 每条样本只命中自己那条规则：删掉任何一条规则，对应样本就会原样显示（杀 N2–N5 类变异）
  const SAMPLES: Record<string, string> = {
    traceback: "Traceback (most recent call last): boom",
    winDrive: "无法读取 C:\\Users\\bob",
    unc: "\\\\fileserver\\share\\k",
    absPath: "open failed /data/poemseed/m",
    relPath: "missing data/uploads/abc.png",
    excName: "KeyError: 'title'",
    lineNo: "第 line 3 行",
    errno: "[Errno 2] No such file or directory",
    sql: "UNIQUE constraint failed: chapters.novel_id",
    pyRepr: "invalid literal for int() with base 10: 'abc'",
    html: "<html>nginx</html>",
  };
  it("every rule has a sample and every sample matches exactly its own rule", () => {
    expect(Object.keys(SAMPLES).sort()).toEqual(UNSAFE_SERVER_RULES.map(([n]) => n).sort());
    for (const [name, text] of Object.entries(SAMPLES)) {
      expect(UNSAFE_SERVER_RULES.filter(([, re]) => re.test(text)).map(([n]) => n), text).toEqual([name]);
    }
  });
  it.each(Object.entries(SAMPLES))("%s sample is withheld end-to-end", async (_n, text) => {
    serve(env(400, { code: "X", message: text }));
    expect(apiErrorView(await caught(VIA.call)).message).toBe("请求内容有误，请检查后重试");
  });
  it.each([
    "cannot open ./data/novels/x.json", "~/.poemseed/config.toml", "SELECT * FROM novels WHERE id=?",
    "duplicate key value violates unique constraint \"assets_pkey\"", "/home/u/.env", "C:/Users/bob/a.db",
  ])("more leak shapes withheld: %s", async text => {
    serve(env(400, { code: "X", message: text }));
    expect(apiErrorView(await caught(VIA.call)).message).toBe("请求内容有误，请检查后重试");
  });
  it.each(["该章节已被其他人修改，请刷新后重试", "Chapter was modified elsewhere", "网络 Error 请重试", "Use A/B test variants"])("legit text kept: %s", async text => {
    serve(env(409, { code: "X", message: text }));
    expect(apiErrorView(await caught(VIA.call)).message).toBe(text);
  });
  it("length cap: exactly the limit is kept, one more char is raw", async () => {
    serve(env(409, { code: "X", message: "好".repeat(SERVER_MESSAGE_LIMIT) }));
    expect(apiErrorView(await caught(VIA.call)).message).toBe("好".repeat(SERVER_MESSAGE_LIMIT));
    vi.restoreAllMocks();
    serve(env(409, { code: "X", message: "好".repeat(SERVER_MESSAGE_LIMIT + 1) }));
    expect(apiErrorView(await caught(VIA.call)).message).toBe("内容已被修改，请刷新后重试");
  });
});

describe("independent guards (N6 / N7 / N9 / dict echo)", () => {
  it("N6: string detail echoed into message is raw even with a non-HTTP code", async () => {
    serve({ status: 409, ct: "application/json", body: JSON.stringify({ detail: "Chapter gone", code: "NOT_FOUNDISH", message: "Chapter gone" }) });
    expect(apiErrorView(await caught(VIA.call)).message).not.toBe("Chapter gone");
  });
  it("N7: HTTP_n envelope without structured detail is raw even when message differs", async () => {
    serve({ status: 400, ct: "application/json", body: JSON.stringify({ code: "HTTP_400", message: "Bad thing happened" }) });
    expect(apiErrorView(await caught(VIA.call)).message).toBe("请求内容有误，请检查后重试");
  });
  it("N9: raw_text falls back to top-level message when there is no detail", async () => {
    setApiErrorShellMode("pro");
    serve({ status: 400, ct: "application/json", body: JSON.stringify({ code: "INVALID_WORKER_CONFIG", message: "worker SECRET-N9" }) });
    expect(apiErrorView(await caught(VIA.call)).technical).toBe("worker SECRET-N9");
  });
  it("dict detail echoed into message (no code) is raw; explicit d.message kept", async () => {
    serve(env(400, { detail: "Chapter number must be positive" }));
    expect(apiErrorView(await caught(VIA.call)).message).toBe("请求内容有误，请检查后重试");
    vi.restoreAllMocks();
    serve(env(400, { detail: "x", message: "标题不能为空" }));
    expect(apiErrorView(await caught(VIA.call)).message).toBe("标题不能为空");
  });
});
