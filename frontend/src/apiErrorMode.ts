// [HERMIA-FE-20261025 P1-ERR] 当前外壳模式（供 apiErrorView 决定是否返回技术详情）。独立模块，避免 vi.mock('../api') 的测试受影响。
let mode: "basic" | "pro" = "basic";
export function setApiErrorShellMode(next: string | undefined): void { mode = next === "pro" ? "pro" : "basic"; }
export function getApiErrorShellMode(): "basic" | "pro" { return mode; }
// [HERMIA-FE-20261025 P1-ERR] 友好文案解析器由 i18n 模块注册；api.ts 不直接 import i18n（避免在打包宿主中读取 localStorage，见 AuditColdStorage.test.ts）
let translator: ((key: string) => string) | undefined;
export function registerApiErrorTranslator(fn: (key: string) => string): void { translator = fn; }
export function apiErrorText(key: string): string | undefined { return translator?.(key); }
