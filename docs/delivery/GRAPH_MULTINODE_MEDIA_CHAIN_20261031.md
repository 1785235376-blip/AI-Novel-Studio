# Graph 三级媒体链（2026-10-31）

## 能力验证
`tests/test_graph_multinode_media_chain.py` 使用 File owner + 确定性 provider 替身（非真实模型）验证：

1. 三级 IMAGE 图：text→prompt→t2i→review→prompt→i2i→review→prompt→i2i→review；
2. 每级 `media_previews` 的 source snapshot digest = 上一级 review 后的正式资产 digest；
3. 下一级 provider 实际收到的是上一级正式落盘字节（不是临时候选）；
4. 最终正式资产 digest/字节可通过原 owner 回读；
5. 第三级 dispatch 后失败 → job `UNKNOWN`、不得再次 execute、无第三级/review_c typed output；取消后仍无输出；
6. 失败前两级输出保留、可观察。

图组回归（binary branch/local branch/image leaf rerun/expiry/source guard/multinode）19 passed。

## 边界
真实模型/GPU、真实 PostgreSQL、跨进程崩溃恢复、完整 DAG 多模态编排仍 NOT_RUN/NOT_VERIFIED；不可把本测试当作产品验收。
