# 最终源码与权限边界独立复核

日期：2026-10-17（Asia/Shanghai）。实际核对实现 HEAD：`f7fd63a1fff3c0ec7fa88c9c111676f9539a41a5`；本轮基线：`618affbca0aaf20d5bc669d697d8e2b1abb9b3fa`。

本次只读复核后按要求留档；未重跑测试、修改源码/属性/清单或提交。

- **2352 个清单源码输入：**独立通过 `git cat-file --batch` 读取实际 HEAD blobs，并逐项与 V2 manifest 的 SHA-256、工作区原字节比较；两组差异均为空。
- **2290 个运行器源码输入：**全部为 `RAW_BYTES_EQUAL`，均属于上述清单，记录哈希逐项一致。没有 EOL 归一化例外。
- **最终 PG 组合：**读取 [r3-prompt-combined-pg-final-r3.json](../v2-development/r3-prompt-combined-pg-final-r3.json) 及其原日志，确认同一实现 HEAD、exit 0、PASS，`103 passed, 99 deselected`。运行前后 2290 个源码哈希相同，且全部匹配最终 manifest/HEAD。本项为既有真实运行凭证复核，不是本次重新执行。
- **原 owner 与关闭闸门：**生产 `PROMPT_ADOPTION_WRITE_ENABLED=False` 保持不变。采纳沿原 `GraphAssetInputs.phase` 与 `CreativeService.revise_in_state` 提交；绑定读取、私有生命周期和来源标记仍由原 Novel/AssetLibrary/Creative owner 持有。原授权提交租约及 Session resolver 的 mutation/read 锁分离保留；未发现新增 owner 或写入绕行。
- **750/752 保护范围：**核对保护审计、本轮 Git 路径差异及工作区路径差异，750 个冻结测试/门禁源码和 752 个保护资产均无本轮变更。原 9151 manifest SHA-256 仍为 `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`。EOL 说明明确保留 `persistence.py` 在原 app-source map 中的既有语义差异，不宣称全部 V1 应用源码相同或 V1 运行验收通过。

结论：在上述源码、原 owner 权限路径及证据范围内，**未发现新的实质缺陷**。该结论不是完整 V2、生产采纳成功写、托管 CI、Windows clean-machine、模型/GPU 或 release 验收；最终 PG 浏览器和资源留存状态由对应最终凭证另行确认。
