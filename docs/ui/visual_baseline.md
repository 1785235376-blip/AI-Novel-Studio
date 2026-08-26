# Visual Baseline Workflow

## Two Different Artifacts

`docs/ui/reference/*.png` are user-approved canonical design references. They define layout, hierarchy, density, panel relationships and visual language. They are never copied into Playwright snapshots or compared pixel-for-pixel.

Playwright snapshots are real browser renders of `/ui-fixture`. They protect the approved React implementation.

```text
Canonical reference -> React implementation -> visual review -> approved React screenshot -> automated baseline
```

## Deterministic Contract

- Browser: bundled Playwright Chromium
- Primary viewport: 1440x900
- Geometry viewports: 1366x768, 1440x900, 1920x1080
- Device scale factor: 1
- Theme: DS-v1.0 light
- Locale: `zh-CN`
- Timezone: `Asia/Shanghai`
- Zoom: 100%
- Route: `/ui-fixture?module=NOVEL|IMAGE|VIDEO`
- Actor: 测试创作者
- Workspace/project/storyline/branch: 创作工作区 / 星海残章 / 主线 / 当前草稿
- Chapter: 第18章 门后的声音
- Animation/transition/caret: disabled by injected test CSS
- Fonts: wait for `document.fonts.ready`
- Data: static in-repository fixture; no random IDs, current clock or network data

Snapshots use a small platform-tolerant pixel threshold and protect major geometry, spacing, typography and hierarchy. Changes require review; do not update snapshots merely to make CI green.

