# 分镜采用已关联导演镜头字段

产品基线 `a9974f24e7c556e3379f750f50d621be1255a05f`，仅采用已独立审查的dc69四文件 patch，映射为 `9d95cabbd111718e55063ef61f4b9249410a2432`，树 `ed1b4d6228341d43a3aa225ae92cb4c701d31dad`。与既有Audio/子调用变更无共享写集、无冲突；patch-id、补丁字节及四个最终blob/mode与dc69一致，其余基线源码不变。未回带dc69基于0ec的旧祖先。

## 实际功能

原CreativeCanvas中的Storyboard草稿可从现有director_notes快照与同场景shot.director_note_ids绑定，明确选择1–4个已存在目标、从5项镜头字段白名单中选择，逐字段比较旧/新值，再明确采纳到原CreativeInput.shots/onChange草稿。预览/采纳不发Save/API/模型请求，仍由原CreativeWorkspace/CreativeClient.update/CreativeService CAS与history保存。一次受限Undo只在原采纳后的当前草稿及权限/场景/版本/busy仍匹配时有效，后续编辑、ABA和旧回调不覆写当前内容。不是上游Director实时刷新、模型镜头生成或完整DIR-03/08验收。

## 验证来源与原始中断

作者13新增+3原Canvas唯一用例通过，保留最初Windows同名helper/component解析冲突导致的失败以及更名后的通过；类型/构建原失败和修正日志也保留。实际File/UI：原Save v2后浏览器执行器中断，先确认服务端仍v2且旧worker已不存在，才继续；最终C分段明确预览/确认/Undo/再确认后仅一次原PUT v2→v3，B新浏览器重开v3/history无写入。C在recovered4通过，B在reopened5通过，未声称一次全绿完整旅程。GET/Save结构比对只对created_at/updated_at元数据做UTC规范化，原捕获与哈希保留。

独立3项反例最终通过、无P1/P2。首次Undo探针未更新受控父草稿的harness失败保留，仅修正后重跑该1项；未改弱断言，也不重复计数。

本组合只跑2项smoke（原Canvas采纳/Undo模拟宿主保存、既有降噪实际File回执解码），一次TS及一次Vite build，均通过；原大包提示保留。没有重跑作者16项、6项共享壳或真实浏览器/API。作者真实File分段证据不冒充本轮新跑E2E。

**PG受控环境缺失而BLOCKED；真实协作浏览器撤权、新CAS冲突浏览器场景、完整E2E/产品生产验收及实时上游/模型能力未验收。**

## 归档与清理

仅向指定公开archive分支追加本唯一目录，预期父 `e67ace9b6fa413bbdb28ed7a03375141bcf1e9ee`，普通非force更新；不main合并、Tag/Release或源码PR，不操作demo或原工作树。新Git源码对象仅四个已审前端文件。代码/测试、必要原始日志及合成资料副本脱敏路径、ANSI和凭据形态字段；不含实际凭据、真实用户资料、后端实现、运行配置、raw trace、数据库、依赖或dist。

唯一外部前置为a997；复用已保留隔离Git对象库验证下载增量，无完整历史源码导出。公开回读/恢复/fsck后，仅清理本轮临时工作树、依赖/构建产物与重复打包副本；保留Git refs/objects、唯一证据与公开下载包，实际清理另记本地回执。
