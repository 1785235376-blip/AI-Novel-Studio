// [HERMIA-FE-20261023 M1, applied M1-s2] Opt-in preview host for DockLayout (?uw=1 only).
import { DockLayout, type LayoutPanelSpec } from "./layout";

export function unifiedWorkspacePreviewEnabled(): boolean {
  try { return new URLSearchParams(window.location.search).get("uw") === "1"; } catch { return false; }
}

const SPECS: LayoutPanelSpec[] = [
  { id: "outline", title: "大纲", defaultDock: "left", docks: ["left", "right", "main", "float"], defaultSize: 248, minSize: 180 },
  { id: "creative", title: "创作画布", defaultDock: "main", docks: ["main", "float"], defaultSize: 800, minSize: 320 },
  { id: "execution", title: "执行画布", defaultDock: "main", docks: ["main", "float", "right"], defaultSize: 800, minSize: 320 },
  { id: "inspector", title: "属性", defaultDock: "right", docks: ["left", "right", "bottom", "float"], defaultSize: 340, minSize: 240, maxSize: 560 },
  { id: "tasks", title: "任务", defaultDock: "bottom", docks: ["bottom", "right", "left"], defaultSize: 200, minSize: 120 },
];

// [HERMIA-FE-20261023 M1-s2] placeholder shows panel titles, never raw ids.
export function UnifiedWorkspacePreview() {
  return (
    <DockLayout specs={SPECS} scope={{ userId: "local", projectId: "preview", projectInstanceId: "preview" }}
      storage={window.localStorage} loadOptions={{ inspectorPanelId: "inspector" }}
      renderPanel={(id) => <p style={{ padding: 12 }}>{SPECS.find((x) => x.id === id)?.title ?? "面板"}（预览占位，尚未接入实际功能）</p>} />
  );
}
