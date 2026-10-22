/** [HERMIA-FE-20261022] H-UX-START-01 · App wiring contract (no mount) */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("H-UX-START-01 App wiring", () => {
  const app = readFileSync(resolve(__dirname, "../App.tsx"), "utf8");

  it("mounts ModuleStartGate on studio paths and keeps cold-start write", () => {
    expect(app).toContain("H-UX-START-01");
    expect(app).toContain("shouldOpenModuleStartGate");
    expect(app).toContain("markModuleStartGateDismissed");
    expect(app).toContain("{moduleStartGate}");
    expect(app).toContain('setPanel("write")');
    expect(app).toContain('commitStudioModule("NOVEL")');
    // media pick uses commitStudioModule(module) — does not force novel center
    expect(app).toMatch(/onPick=\{\(module\) => \{[\s\S]*commitStudioModule\(module\)/);
    // N-UX-04 / inspector default not touched by this ticket
    expect(app).not.toMatch(/studio-inspector-open["'].*H-UX-START/);
  });
});
