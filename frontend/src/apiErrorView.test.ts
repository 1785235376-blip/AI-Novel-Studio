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
  it("structured message field is still shown (whitelisted contract)", async () => {
    fail(409, JSON.stringify({ code: "VERSION_CONFLICT", message: "章节已被他人修改", details: { actual_version: 4, secret: "x" } }));
    const v = apiErrorView(await caught());
    expect(v.message).toBe("章节已被他人修改");
    expect(v.code).toBe("VERSION_CONFLICT");
    expect(v.details).toBe('{"actual_version":4}');
  });
  it("nested object detail.message is structured and kept", async () => {
    fail(400, JSON.stringify({ detail: { code: "BAD", message: "标题不能为空" } }));
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
