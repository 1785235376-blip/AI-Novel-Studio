# 双参考图与作者 Prompt：原画布首片

基线 `0574ff74e4d0b40472d26a737172bfac7fec7f5f`，保留 330、16f、3c4、faeb 历史。独立分支 `work/v2-dual-canvas-image-bridge-20261020`。原七个 Storyboard 文件继续冻结在另一工作区，不属于本切片。

## 实际行为

1. 上层原媒体画布先明确保存，再选择两张不同正式图片；两份引用须为 CURRENT_METADATA。
2. 原图入口明确读取图片目录、采用空白 schema 4。上层布局写入仍遵守原脏表单锁；仅元数据选择可以在下层草稿脏时进行。
3. 作者填写 1–8000 字符 Prompt、各图用途和大于 0 至 1 的权重。原 Asset 接口核对两个版本、类型及摘要后，预览卡片到新节点的对应关系。
4. 一次确认通过原控制器 change/history 建立七节点六连线：text_input → image_prompt → image_generate → media_review；两份 asset_reference → image_reference → image_prompt。operation 为原 m5.image.reference。
5. provider/model 保持空白本地输入、allow_cloud=false。原 Inspector 配置、Save、预检、运行、Job 和 Review 继续分别明确操作。
6. 原 Review 产生正式 Asset 后，使用原“读取可用素材／加入引用卡片”，明确保存上层。未审核私有候选不能成为画布素材；两层没有分布式原子保存或自动回接。

原图保存后，作者输入和固定版本素材引用仍由原节点持久化，上层只读投影从这些原节点读取。不存在额外提示词存储、执行引擎或自动任务。

## 守卫及容量

目标复用 0574 同步 mutation generation 和 insertion 权限边界；完整预览封存对象身份和内容，只消费一次。来源卡片选择增加同步 generation，阻止同批 A→B→A、旧回调及迟到元数据结果。权限、忙碌、脏来源、未决保存、恢复、图历史容量、原节点/边/完整字节限制保持。

本地未配置路线仍可留作草稿；完整 Save 校验没有放宽。用途标签不代表角色一致性、三视图或真实推理已验证；discovery 仍是 CONFIGURED_NOT_VERIFIED。

## Windows 原 Job 读取修复

原 atomic_write 使用 UTF-8；ImageJobService._load 未指定编码，Windows GBK 环境无法读取含中文 Prompt 的 Job。独立提交 `7b1f7afbc32b21e33ccc1b04cfa1b2aa2b9f9459` 仅显式使用 UTF-8 读取，没有修改系统编码或账户配置。完整 File 回归保留原失败及修复后结果。

## 验证与边界

针对性前端测试覆盖纯计划、类型连接、两源版本、容量、原子应用、一次撤销重做、旧确认、目标/来源 ABA、忙碌、权限切换、计划篡改、迟到结果及生产 hook 的真实接线。

原 File Graph/Job/Review/Asset/Canvas owners 使用真实 PNG 校验，来源替换明确映射前端导出的原计划；仅模型 HTTP 使用现有合成 Comfy transport。验证中文 Prompt 保存重开、两引用命令、私有候选拒绝、正式资产显式回接并重开。不是模型推理、Host、PostgreSQL 或 Windows 完整 E2E 验收。

真实 Chromium 静态元数据夹具在 1366×768、1440×900、1920×1080 检查原 AppShell、面板无横向溢出、完整原图及撤销重做；自动 Save/run 均为 0。保留原节点虚拟化，不把可见 DOM 数当全图数量。截图遵从 DS token、共同外壳及 canonical reference 关系，不更新基线。

原始失败、最终命令记录、截图和导出脚本位于同任务 `dual-canvas-image-bridge-evidence-20261020`。DSH725、未审配方组件和 Storyboard 不随已审0574归档。
