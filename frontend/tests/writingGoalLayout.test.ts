import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("../src/novel/novel.css", import.meta.url), "utf8");
const tokens = readFileSync(new URL("../src/ui/tokens.css", import.meta.url), "utf8");
function rule(selector: string) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const value = css.match(new RegExp(`${escaped}\\s*\\{([^}]+)\\}`))?.[1];
  expect(value, `missing scoped rule: ${selector}`).toBeTruthy();
  return value!;
}

describe("writing-goal inspector form layout", () => {
  it("uses a shrinking single-column panel with the existing spacing token", () => {
    const panel = rule(".writing-goal-panel");
    for (const declaration of ["display:grid", "grid-template-columns:minmax(0,1fr)", "gap:var(--space-3)", "min-width:0"]) expect(panel).toContain(declaration);
    expect(tokens).toContain("--space-3:");
  });
  it("places each label above its own input instead of inline with another field", () => {
    const label = rule(".writing-goal-panel>label");
    for (const declaration of ["display:grid", "grid-template-columns:minmax(0,1fr)", "gap:var(--space-1)", "min-width:0", "margin:0"]) expect(label).toContain(declaration);
    expect(tokens).toContain("--space-1:");
  });
  it("contains date and number controls within the available panel width", () => {
    const input = rule(".writing-goal-panel>label>input");
    for (const declaration of ["display:block", "box-sizing:border-box", "width:100%", "min-width:0", "max-width:100%", "margin:0"]) expect(input).toContain(declaration);
  });
  it("lets the panel gap own direct heading and description spacing", () => {
    expect(rule(".writing-goal-panel>h2,.writing-goal-panel>p")).toContain("margin:0");
  });
});
