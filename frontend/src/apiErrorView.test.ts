// [HERMIA-FE-20261025 P1-ERR] 共享 apiErrorView：字符串 detail / 非 JSON 正文不得原样展示；仅专业模式技术详情可见原文
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiErrorView, call, setApiErrorShellMode } from "./api";
import { setLocale } from "./i18n";

const fail = (status: number, body: string, type = "application/json") =>
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(body, { status, headers: { "Content-Type": type } }));
const caught = async () => { try { await call("/api/x"); } catch (e) { return e; } throw new Error("no throw"); };

afterEach(() => { vi.restoreAllMocks(); setApiErrorShellMode("basic"); setLocale("zh-CN"); });

describe("apiErrorView whitelist", () => {
  it("string detail is not echoed (zh friendly copy by status)", async () => {
    fail(500, '{"detail":"boom: Traceback psycopg2.OperationalError at /srv/app.py:42"}');
    const e = await caught();
    expect(e).toBeInstanceOf(ApiError);
    const v = apiErrorView(e, "操作失败");
    expect(v.message).not.toMatch(/boom|Traceback|psycopg2|detail|\{/);
    expect(v.message).toBe("服务暂时出错，请稍后重试");
    expect((e as Error).message).not.toMatch(/boom|\{/);
    expect(v.technical).toBeUndefined();
    expect(JSON.stringify(v)).not.toMatch(/boom/);
  });
  it("non-JSON body (HTML proxy page) is not echoed; en copy", async () => {
    setLocale("en");
    fail(502, "<html><body>nginx upstream 10.0.0.3:8000 refused</body></html>", "text/html");
    const v = apiErrorView(await caught(), "Operation failed");
    expect(v.message).not.toMatch(/nginx|<html|10\.0\.0\.3/);
    expect(v.message).toBe("The service is unreachable right now. Please try again shortly.");
  });
  it("unknown status falls back to caller fallback, not body", async () => {
    fail(418, "teapot internals");
    expect(apiErrorView(await caught(), "保存失败").message).toBe("保存失败");
  });
// [HERMIA-FE-20261025 VERA-620963bf 规格变更] 白名单裁定：仅 LITERAL_MESSAGE_CODES 内的 code 可原样展示；VERSION_CONFLICT/BAD/X/无 code 在后端不带字面文案，改用白名单 code PLANNING_VERSION_CONFLICT 验证“展示”，原 code 改断言为友好文案。
  it("structured message field is still shown (whitelisted contract)", async () => {
    fail(409, JSON.stringify({ code: "PLANNING_VERSION_CONFLICT", message: "章节已被他人修改", details: { actual_version: 4, secret: "x" } }));
    const v = apiErrorView(await caught());
    expect(v.message).toBe("章节已被他人修改");
    expect(v.code).toBe("PLANNING_VERSION_CONFLICT");
    expect(v.details).toBe('{"actual_version":4}');
  });
  it("nested object detail.message is structured and kept", async () => {
    fail(400, JSON.stringify({ detail: { code: "PLANNING_VERSION_CONFLICT", message: "标题不能为空" } }));
    expect(apiErrorView(await caught()).message).toBe("标题不能为空");
  });
  it("pro mode exposes raw text only as technical details (truncated), message stays friendly", async () => {
    setApiErrorShellMode("pro");
    fail(500, JSON.stringify({ detail: "boom " + "x".repeat(2000) }));
    const v = apiErrorView(await caught());
    expect(v.message).toBe("服务暂时出错，请稍后重试");
    expect(v.technical).toMatch(/^boom x/);
    expect(v.technical!.length).toBeLessThanOrEqual(501);
  });
  it("basic mode never exposes technical even for structured errors", async () => {
    fail(500, "plain crash text");
    const v = apiErrorView(await caught());
    expect(v.technical).toBeUndefined();
    expect(v.message).not.toMatch(/crash/);
  });

});

// [HERMIA-FE-20261025 VERA-097 MF1] 真实后端信封（app/main.py unified_http_error）：字符串 detail 被复制进 message，code=HTTP_<n>
const envelope = (status: number, detail: unknown, extra: Record<string, unknown> = {}) => {
  const code = detail && typeof detail === "object" ? String((detail as any).code || `HTTP_${status}`) : `HTTP_${status}`;
  const message = detail && typeof detail === "object" ? String((detail as any).message || (detail as any).detail || code) : String(detail);
  return JSON.stringify({ detail, code, message, details: detail && typeof detail === "object" ? (detail as any).details ?? detail : {}, request_id: "rq-1", ...extra });
};
describe("apiErrorView with the real unified_http_error envelope", () => {
  it.each([
    [404, "Not found: /home/u/SECRET-T4.key", "请求的内容不存在或已被删除"],
    [500, "KeyError('chapter') at /srv/app/api.py:547", "服务暂时出错，请稍后重试"],
    [400, "nf", "请求内容有误，请检查后重试"],
    [422, "Traceback (most recent call last):\n  File \"x.py\", line 3", "提交的内容未通过校验，请检查后重试"],
  ])("basic: %s string detail echoed into message is withheld", async (status, detail, friendly) => {
    fail(status, envelope(status, detail));
    const e = await caught() as ApiError;
    const v = apiErrorView(e, "操作失败");
    expect(v.message).toBe(friendly);
    expect(JSON.stringify(v)).not.toContain(detail.slice(0, 8));
    expect(e.message).toBe(friendly);
    expect(e.problem.message_source).toBe("fallback");
    expect(e.problem.code).toBe(`HTTP_${status}`);
    expect(v.requestId).toBe("rq-1");
  });
  it("pro: echoed string detail is available as technical details", async () => {
    setApiErrorShellMode("pro");
    fail(404, envelope(404, "Not found: /home/u/SECRET-T4.key"));
    const v = apiErrorView(await caught());
    expect(v.message).toBe("请求的内容不存在或已被删除");
    expect(v.technical).toBe("Not found: /home/u/SECRET-T4.key");
  });
  it("structured dict detail keeps its message through the envelope", async () => {
    fail(409, envelope(409, { code: "PLANNING_VERSION_CONFLICT", message: "章节已被他人修改", details: { actual_version: 7 } }));
    const v = apiErrorView(await caught());
    expect(v.message).toBe("章节已被他人修改");
    expect(v.code).toBe("PLANNING_VERSION_CONFLICT");
    expect(v.details).toBe('{"actual_version":7}');
  });
// [HERMIA-FE-20261025 VERA-620963bf 规格变更] 白名单裁定：仅 LITERAL_MESSAGE_CODES 内的 code 可原样展示；VERSION_CONFLICT/BAD/X/无 code 在后端不带字面文案，改用白名单 code PLANNING_VERSION_CONFLICT 验证“展示”，原 code 改断言为友好文案。
  it("dict detail without code (HTTP_<n>) is never shown; unsafe text dropped too", async () => {
    fail(400, envelope(400, { message: "标题不能为空" }));
    expect(apiErrorView(await caught()).message).toBe("请求内容有误，请检查后重试");
    fail(400, envelope(400, { message: "ValueError: bad path /var/lib/app/db.sqlite" }));
    expect(apiErrorView(await caught()).message).toBe("请求内容有误，请检查后重试");
  });
  it("dict detail with no message falls back (message===code is not copy)", async () => {
    fail(403, envelope(403, { code: "FORBIDDEN_SCOPE" }));
    const v = apiErrorView(await caught());
    expect(v.message).toBe("没有权限执行此操作");
    expect(v.code).toBe("FORBIDDEN_SCOPE");
  });
  it("structured top-level message with internal paths/Traceback is filtered", async () => {
    fail(500, JSON.stringify({ code: "INTERNAL", message: "Traceback: File \"/srv/app/main.py\", line 9" }));
    expect(apiErrorView(await caught()).message).toBe("服务暂时出错，请稍后重试");
  });
  it("en locale friendly copy for the envelope", async () => {
    setLocale("en");
    fail(404, envelope(404, "Not found: C:\\Users\\a\\secret.txt"));
    expect(apiErrorView(await caught(), "Operation failed").message).toBe("The requested item does not exist or was deleted.");
  });
});

// [HERMIA-FE-20261025 VERA-097 W7] raw_text 截断
describe("raw_text truncation", () => {
  it("stores at most 500 chars of the raw text", async () => {
    fail(500, envelope(500, "E".repeat(5000)));
    const e = await caught() as ApiError;
    expect(e.problem.raw_text).toBe("E".repeat(500));
    fail(502, "<html>" + "y".repeat(3000));
    expect(((await caught()) as ApiError).problem.raw_text!.length).toBe(500);
  });
});

