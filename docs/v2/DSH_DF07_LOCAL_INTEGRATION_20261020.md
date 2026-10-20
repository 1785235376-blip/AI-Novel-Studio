# DSH / df07 本地隔离整合范围

起点为已审 `df07c337f520425ec4c4cc8884f0e4a3aea2f077`，合入完整 DSH `f87938c8a9509e5e59fbab75b48ec84280e652cb`，共同基线 `b8371a48816b852176d45151eb9a0e3618a32c07`。保留 DSH 原 58 提交，包括最初互动实现、后续导出/信任/恢复修复及明确绑定代码 9ffa 的证据。没有纳入其他线的文字多图片、便携引用或未提交分镜工作。

自动合并预检无代码冲突。唯一双方修改文件 `packaging/public-build.json` 保留主产品 20 个既有 runtime 模块、Docker 合同条目及 DSH 18 个新增显式路径，再补齐 Ink helper/schema 两个实际消费资源。`PUBLIC`、roots、排除命名空间、依赖及构建防护均保持；不增加目录通配、依赖或引擎。

产品整合没有改写原共享壳、Graph/Director/Asset owner、源分支或交付文件。新增组合回归只检查实际 PUBLIC staged imports/resources 与同一 File scope 内 Graph 写入、旧互动回执幂等和撤权隔离。

具体提交/tree、命令和验证结果另绑定至本地 evidence 索引，不能用此前固定 SHA 的 303/672 等作者声明替代新组合验证。真实模型/GPU、Host、PG、多进程、GUI、原生 C# Ink、媒体和 RenPy 运行等未验边界继续保留。该本地整合不是 main merge、上传或 Release。
