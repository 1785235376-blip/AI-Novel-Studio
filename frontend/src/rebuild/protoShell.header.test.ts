// [HERMIA-FE-20261025 P1-HDR] 头部窄屏规则：搜索文字须视觉隐藏（clip）而非 display:none；专业模式头部收紧规则存在
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const css = readFileSync(resolve(__dirname, "protoShell.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
const block = (q: string) => {
  const i = css.indexOf(q);
  expect(i, `missing media ${q}`).toBeGreaterThanOrEqual(0);
  let d = 0, j = css.indexOf("{", i);
  const s = j;
  for (; j < css.length; j++) { if (css[j] === "{") d++; else if (css[j] === "}") { d--; if (!d) break; } }
  return css.slice(s, j + 1);
};
const rule = (b: string, sel: string) => {
  const m = b.match(new RegExp(sel.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\{([^}]*)\\}"));
  return m ? m[1] : null;
};

describe("protoShell header ≤1360 search label", () => {
  it("keeps the search text in the accessibility tree (clip, not display:none)", () => {
    const decl = rule(block("@media (max-width:1360px)"), "html .app-shell .global-search>span");
    expect(decl).not.toBeNull();
    expect(decl!).not.toMatch(/display\s*:\s*none/);
    expect(decl!).not.toMatch(/visibility\s*:\s*hidden/);
    expect(decl!).toMatch(/position:absolute/);
    expect(decl!).toMatch(/clip-path:inset\(50%\)/);
    expect(decl!).toMatch(/width:1px/);
  });
  it("no rule anywhere hides .global-search>span with display:none", () => {
    expect(css).not.toMatch(/\.global-search>span\{[^}]*display:none/);
  });
});

describe("protoShell pro header tightening", () => {
  it("drops the 220px logo min-width in pro ≤1600 and visually hides the product name ≤1500", () => {
    expect(rule(block("@media (max-width:1600px)"), "html .app-shell[data-shell-mode=pro] .product-mark")).toMatch(/min-width:0/);
    const n = rule(block("@media (max-width:1500px)"), "html .app-shell[data-shell-mode=pro] .product-mark__name");
    expect(n).toMatch(/clip-path:inset\(50%\)/);
    expect(n).not.toMatch(/display:none/);
  });
});
