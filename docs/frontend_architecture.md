# Frontend Architecture

`App` 组织 Novel Tree、Chapter Editor、AI Workspace 与 Inspector；`api.ts` 是唯一网络边界；`store.ts` 只保存选择与 Profile；TipTap 维护编辑事务。正文手工编辑防抖保存，AI 内容不进入编辑器状态，直到后端 Accept 成功后重新拉取章节。
