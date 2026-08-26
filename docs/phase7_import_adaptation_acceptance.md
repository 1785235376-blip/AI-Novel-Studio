# Phase 7 小说导入与智能改编验收

Phase 7 覆盖 TXT、Markdown、项目 JSON 导入，章节预览、确认写入、团队分支导入和断点恢复。

智能改编支持商业、文学、影视和自定义目标；方案锁定原作版本，蓝图可修订、批准后冻结。物化创建独立工作副本，不覆盖原作。逐章草稿可使用本地准备模式或显式选择真实文本模型；模型输出必须通过结构校验，失败时不回退、不写入。草稿经过审核和哈希校验后，才能通过版本化写入应用到工作副本。

团队模式使用可信会话、分支范围、`domain.read/write/review` 能力和内容隔离审计。审计不保存原作正文、模型草稿或改编要求。

统一验收：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_phase7_import_adaptation.ps1
```
