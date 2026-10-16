"""Build the public, source-grounded recovery inventory from immutable snapshots."""
from __future__ import annotations

import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parents[2]
BASELINE = "665817243cad59eef0d4140f17c2ea644f46971e"
BASE_URL = "https://github.com/1785235376-blip/AI-Novel-Studio"


def read(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8-sig"))


def pages(name: str):
    return [item for page in read(name) for item in page]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True, encoding="utf-8").strip()


def included(sha: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", sha, BASELINE], cwd=REPO,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


capabilities = {
36: ("只读Provider Runtime路由编排；Fountain/DOCX冻结导出；资源完整性与File/PG基线修复", "File 1607/29 skip；PG 1599/37 skip；UI 429；geometry 5", "app/provider_runtime_v2_routing_service.py; app/industry_export_formats.py; app/services/export_job_service.py", "tests/test_provider_runtime_v2_routing_service.py; frontend/src/novel/ExportPanel.test.tsx"),
37: ("隐私迁移018；生成CAS/幂等接受；持久化导出恢复；Local AI发现/明确启用；受控Agent与完整unsigned桌面包", "File 2147/45 skip；PG 2155/37 skip；UI 579；Windows 59；native 11", "app/context.py; app/backup_restore.py; app/services/agent_job_service.py", "frontend/src/AppRevisionHistory.test.tsx; frontend/src/localAiDiscoveryApi.test.ts"),
38: ("默认OFF实验规划/导入/世界角色/Inbox；8个Agent角色与4配方；媒体/嵌入/有声书接口；迁移019", "File 2289/168 skip；PG 2322/135 skip；UI 605/6 skip；browser 19", "app/experimental/api.py; app/experimental/planning.py; app/experimental/embeddings.py", "frontend/src/experimental/ExperimentalWorkbench.test.tsx; frontend/src/experimental/WorldPanel.test.tsx"),
39: ("40包R4/R5/UX；原写作/恢复/搜索/任务/研究/本地模型执行接缝；媒体/翻译/扩展创作；修复原项目删除竞态", "File 3754/1354 skip；PG 3755/1353 skip；UI 1045/6 skip；browser 64；TCP 2", "app/author_request.py; app/experimental/author_task_projection.py; app/experimental/api.py", "frontend/src/AppDraftRecovery.test.tsx; frontend/src/AppWorkspaceResume.test.tsx"),
40: ("原后端R1项目授权、R2 SSE撤权、R3最终状态协议修复", "Cloud双事件成功；File 4393/1992 skip；PG 4394/1991 skip；旧基线RED push wrapper FAILURE保留", "app/api.py; app/generation_stream.py; app/jobs.py", "tests/test_shared_project_route_authority.py; tests/test_shared_generation_terminal_protocol.py"),
41: ("PoemSeed Local Interop 1.0；Studio Host/上下文与显式同意UI；独立参考适配；37协议文件冻结", "Cloud与Interop双事件成功；原生交互/真实模型NOT_RUN", "app/local_interop/host.py; app/local_interop/provider.py; frontend/src/interop/LocalTutorIntegration.tsx", "frontend/src/interop/LocalTutorIntegration.test.tsx; frontend/tests/localInteropRealHost.test.ts"),
42: ("Desktop SDK/状态机/Trust/生命周期；真实Studio上下文/Verifier/Handoff适配；9类撤权权限；current-user pipe library", "Cloud与Interop双事件成功；Windows pipe仍MOCK_ONLY；交互Desktop/真实模型NOT_RUN", "app/local_interop/desktop.py; app/local_interop/host.py; frontend/src/interop/DesktopIntegrationDetails.tsx", "frontend/src/interop/DesktopIntegrationDetails.test.tsx; frontend/src/interop/entryScopeReview.test.tsx"),
43: ("5波深化原工作区/创作/模型/研究/媒体/扩展创作；持久离线恢复、source/privacy/CAS、source-bound执行接缝", "Cloud与Interop双事件成功；F00 INTEGRATED + 39 PARTIAL保留", "app/author_request.py; app/experimental/declarative_agents.py; app/experimental/embeddings.py", "frontend/src/AppDraftRecovery.test.tsx; frontend/src/experimental/EmbeddingPanel.continuation.test.tsx"),
44: ("A43富文本无损投影/复制/导出；不可重用章节ID；迁移020；原UUID/slug解析与detach接受修复", "File 5365/2554 skip；PG 5328/2591 skip；UI 1269/8 skip；browser 94；7919 nodes", "app/chapter_identity.py; app/document.py; app/file_project_lifecycle.py", "tests/test_a43_context_identity.py; tests/test_a43_detached_generation_acceptance.py; frontend/src/Editor.a43-rich.test.tsx"),
45: ("原Owner内真实branch manuscript/CAS/history/merge；Story五类版本；source-bound一致性/Canon；混合检索；媒体恢复；Interop与PG Timeline身份闭合", "本次重读历史原始归档：File 5969/3147 skip；PG 5945/3171 skip；UI 1455/8 skip；96 browser；9116 nodes；33 ZIP校验", "app/application/collaboration_service.py; app/context.py; app/experimental/adaptation_projection.py; app/collaboration_api.py", "frontend/src/experimental/BranchManuscriptPanel.test.tsx; frontend/src/AppStorySourceNavigation.test.tsx"),
}

prs = sorted(pages("pull-requests-all.json"), key=lambda p: p["number"])
major = read("github-plugin-pr36-45.json")
refs = read("git-ref-inventory.json")
branches = pages("branches.json")
artifacts = [a for page in read("actions-artifacts.json") for a in page["artifacts"]]
verification = read("pr45-artifact-verification.json")
lines = [
"# AI Novel Studio Full Version Map",
"",
"恢复盘点日期：2026-10-07（Asia/Shanghai）。所有数字绑定下面保存的GitHub与Git快照。",
"",
"## 基线结论",
"",
f"Latest Product Development Baseline = PR45 `{BASELINE}`，tree `{git('rev-parse', BASELINE + '^{tree}')}`；在其上建立 `work/full-recovery-product-candidate`。",
"",
f"`origin/main` = `{git('rev-parse', 'origin/main')}`，只有 {git('rev-list', '--count', 'origin/main')} 个可达commit。PR45保留 {git('rev-list', '--count', BASELINE)} 个原commit，比main新增 {git('rev-list', '--count', 'origin/main..' + BASELINE)} 个，包含PR36–44全部head的真实祖先；选择它避免重写或重复开发已实现功能。原PR仍保持原base/head、Draft、unmerged。",
"",
"PR37的GitHub base仍为main，但其Git祖先包含PR36；PR38–45为逐级stack。历史证据只证明原精确SHA，不自动证明当前追加修改，更不代表真实模型/用户验收完成。",
"",
f"全库可达 {git('rev-list', '--count', '--all')} 个commit，{len(branches)} 个真实origin分支，{len(prs)} 个PR；API中的缺号是issue/未使用编号，不是丢失PR。0个tag、0个GitHub Release。基线有 {len(git('ls-tree', '-r', '--name-only', BASELINE).splitlines())} 个tracked文件，docs下 {len((ROOT / 'baseline-docs-tree.tsv').read_text(encoding='utf-8-sig').splitlines())} 个blob，原源码、原测试、迁移与历史交付报告沿Git祖先完整保留。",
"",
"## PR36–45：版本、能力、代码、历史测试与选择",
"",
"历史测试的 `passed/skip` 分开列示；这里不是本次新运行。逐个精确head的Actions API保存在 `docs/delivery/full-recovery/prN-head-actions.json`，原PR内容保存在 `github-plugin-pr36-45.json`。",
"",
"| PR / version / branch / SHA | 新增能力 | 代码状态与代码证据 | 历史测试状态 | 纳入最新基线与选择理由 |",
"|---|---|---|---|---|",
]
for p in major:
    cap, tests, code, cases = capabilities[p["number"]]
    lines.append(f"| [#{p['number']}]({p['url']}) `{p['head']}`<br>`{p['head_sha']}` | {cap} | 原有实现保留；`{code}`<br>测试源码：`{cases}` | {tests}；精确run记录已恢复 | YES，真实ancestor；保留后续修复和原Owner/架构，不重开发 |")
lines += [
"",
"## PR45精确head：本次恢复并重新测量的历史运行证据",
"",
"PR45正文及旧矩阵仍写PENDING；2026-10-07 GitHub最新API和已下载原始工件证明其7个run均attempt1完成。这里更新恢复盘点，保留旧文档的原始时间语义，不篡改其历史状态。",
"",
"| 运行 | 精确归属与结果 | 原始运行链接 |",
"|---|---|---|",
"| Cloud push | SHA 6658172；所有8 job成功；strict File/PG proof complete | [37593331209](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37593331209) |",
"| Cloud PR | merge SHA 78929348；同源tree ff53a8f；所有8 job成功 | [37593337560](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37593337560) |",
"| Interop push / PR | 每事件File 345 pass/68 skip；PG 345 pass/68 skip；reference pipe为MOCK_ONLY | [push](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37593331196) / [PR](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37593337638) |",
"| A43 push / PR RED wrappers | 成功重现旧ad1缺陷；各JUnit实际1 expected failure；不能计产品pass | [push](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37593331227) / [PR](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37593337586) |",
"| R123 PR RED wrapper | 重现旧c6缺陷；不能计产品pass | [37593337569](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37593337569) |",
"",
"分别测量push与PR工件：File 5,969 passed / 3,147 skipped；真实PostgreSQL16两分片合计5,945 passed / 3,171 skipped，每profile9,116 collected；全部零错误/零失败。四份原strict aggregate proofs均status complete，Python3.12.9、source tree ff53a8f、source_manifest SHA256 `87c017723b9987ee0fbf5349203ab14b31a0f63af29758a0d6f5f9499307e5d6`。这是完整分片联合覆盖，不宣称单体PG交互等价。",
"",
"每事件前端JUnit1,455 passed / 8原optional skipped；浏览器96个journeys（63 R4 + 9 geometry + 7 Experimental + 2 business + 1 export + 9 functional + 1 branch）。Windows Host59 passed；fresh unsigned package native smoke11 command、全部exit0。File另有原coverage guard153及真实TCP2。这些属于历史合成/契约/原生smoke测试，不等于真实AI文学质量、交互WebView2、签名或完整安装验收。",
"",
"重新测量摘要：`docs/delivery/full-recovery/pr45-historical-ci-measurements.json`；ZIP恢复校验：`pr45-artifact-verification.json`。保留PR40旧wrapper failure、PR44 failed checkpoints、PR45 d9d2df3a与90f21106失败正文/报告，不把后续修复重标为当时pass。",
"",
"## PR45以外的独特历史：全部识别并保留",
"",
"| 分支 / PR | 独特commit与新增能力 | 代码与测试恢复状态 | 采用决定与理由 |",
"|---|---|---|---|",
"| `feature/plugin-runtime-phase2b-windows-sandbox` / #26 / 5cae6e0 | 5 commit；Windows AppContainer原型、worker监督、环境block/退出修复 | 完整原15路径差异、2,293 additions及原463行sandbox test以5个原format-patch保存；origin及recovery-pr/26仍可达；本次未运行原型 | ARCHIVED / NOT INTEGRATED。当前SDK执行策略DENY_ALL；原型未与新Host/identity/privacy owner证明集成，直接merge会破坏成熟后继运行边界。它是独特历史开发成果，不能声称已进入可执行产品 |",
"| `feature/provider-runtime-v2-model-center-snapshot-bridge` / #31 / 797d183 | 1 commit；旧只读Model Center snapshot bridge | 原3路径981 additions（含原395行test）以原format-patch保留；当前代码无旧module | SUPERSEDED。PR33 authoritative snapshot bridge已入main/PR45，拥有真正Host-owned StableIdentityStore/ModelRegistry/routing provenance，后续PR34/35/36补authority与routing；旧bridge全部candidate拒绝、缺identity，不另建第二authority |",
"| `grok-phase1-acceptance` / ff1511a | 1 commit；旧DesktopHost acceptance checklist | 由closure分支首个原format-patch保留；Git ref/commit完整 | SUPERSEDED。历史desktop门禁由新原生/交互分层报告继续追踪；未把旧BLOCKED伪造PASS |",
"| `grok-phase1-feature-closure` / #1 / 48b0b46 | 上述docs + 1实现commit；overview/research/Agent honest VALIDATED/video fail-closed | 原24路径853 additions与原测试以2个原format-patch完整保留 | SUPERSEDED。PR2已重新应用到main并扩充真实chapter continuity scan/packaged fail-closed；`docs/grok_phase1_feature_handoff.md`说明重新应用原因；选择更新且已集成Owner的实现 |",
"",
"恢复位置：`docs/delivery/full-recovery/historical-patches/`。共8个独特commit patch完整保留原commit ID、作者、diff、文档和测试；`git cherry`没有patch等价不代表功能缺失，PR31和旧Grok必须按后继实现/Owner判定。所有其它origin/recovery-pr head均已在PR45祖先，不需要cherry-pick。",
"",
"6个本地branch head也全部是PR45祖先（`git-local-ref-inventory.json`）。另两个detached worktree试合并commit cd16ffe/9fe50cb分别与正式PR33/34 merge具有完全相同Git tree（`local-merge-tree-equivalence.json`），没有额外遗漏实现；原worktree状态未修改。",
"",
"## 所有PR关系（包括已删除远程branch的PR head）",
"",
"旧PR2–35本次只做源码/关系与原测试资产恢复，未逐个旧版本重复执行；原测试继续留在后继基线。精确历史成功不能由merged状态推导。",
"",
"| PR | 原能力/标题 | 原head / SHA | 原GitHub状态 | 进入PR45 | 测试状态 |",
"|---|---|---|---|---|---|",
]
for p in prs:
    n = p["number"]
    ancestor = included(p["head"]["sha"])
    state = "MERGED" if p["merged_at"] else ("OPEN DRAFT" if p["state"] == "open" and p["draft"] else "CLOSED UNMERGED")
    tests = "精确head Actions已恢复，见上表" if n >= 36 else "原测试/PR文档保留；本次未逐旧版复跑"
    decision = "YES (ancestor)" if ancestor else {1:"SUPERSEDED; original patch restored",26:"ARCHIVED; executable NOT INTEGRATED",31:"SUPERSEDED by PR33"}.get(n,"NO")
    lines.append(f"| [#{n}]({p['html_url']}) | {p['title'].replace('|', '/')} | `{p['head']['ref']}`<br>`{p['head']['sha']}` | {state} | {decision} | {tests} |")
lines += [
"",
"## 所有origin分支与独特commit检查",
"",
"由 `git merge-base --is-ancestor` 与 `git rev-list --left-right --count PR45...ref`测量。HEAD只是指向main的符号ref，不是新branch；recovery-pr refs单独保存在JSON。",
"",
"| origin branch | SHA | PR45真实祖先 | 相对PR45独特commit | 纳入/选择 |",
"|---|---|---|---|---|",
]
for ref in refs:
    if not ref["ref"].startswith("refs/remotes/origin/") or ref["ref"].endswith("/HEAD"):
        continue
    name = ref["ref"].removeprefix("refs/remotes/origin/")
    decision = "YES，原历史与后继修复保留" if ref["ancestor"] else "原patch恢复；按上述ARCHIVED/SUPERSEDED决定"
    lines.append(f"| `{name}` | `{ref['sha']}` | {'YES' if ref['ancestor'] else 'NO'} | {ref['ref_unique']} | {decision} |")
lines += [
"",
"## Tags、Releases、Artifacts、Docs、Reports恢复",
"",
"- Tags与GitHub Releases：API分页结果均空，Git tag亦空；不存在可冒充正式版本的release包。",
f"- 全Actions工件：{len(artifacts):,}个、{sum(a['size_in_bytes'] for a in artifacts):,} bytes；本次快照全部未过期。完整元数据（含run、SHA、digest、到期时间）已保存 `actions-artifacts.json`。27.7GB全历史归档没有全部下载，不宣称完整bytes恢复。",
f"- 最新PR45七运行：{len(verification)}个原ZIP共{sum(v.get('bytes',0) for v in verification):,} bytes已全部恢复、全部GitHub SHA256一致且ZIP CRC完整。永久本地位置 `D:\\小说\\AI-Novel-Studio-Recovery-Assets\\pr45-6658172`，不将近500MB二进制复制进源码Git。到期时间仅影响GitHub托管，不影响已恢复本地bytes。",
"- 精确head完整unsigned Windows acceptance包：artifact11469458461（162,669,240 bytes），SHA256 `c0f8e9541a43599de6066161935ac131fb1ddc5257a314604b0e84c395ddf4ed`；PR merge包11469364136也恢复校验。它们不是本次追加实现后重新build的包。",
"- 618个原docs blob与全Git提交图已列入 `baseline-docs-tree.tsv`、`git-all-commits.tsv`；原143 feature/19 package/28 LAD、40包、73 surfaces/406 requirements/API/UI目录、失败/修复/本机限制仍留在原位置。原reports不重写为当前结论。",
"- 当前实现主控需以新完成状态/运行证据区分本次DONE、PARTIAL、BLOCKED：PR45仍有真实模型/GPU/provider、生产实时传输/密码学、交互Desktop/目标应用和可执行SDK隔离边界。资产恢复成功不等于这些能力已完成。",
"",
"## 可复核盘点工件",
"",
"`docs/delivery/full-recovery/` 包含：GitHub插件PR36–45原元数据；全部PR/branch/tag/release/API artifacts原分页快照；各PR原commit/Actions；PR45原job状态；所有Git refs/ancestry/unique count；全commit图；docs tree；8个未纳入commit完整patch；33 ZIP digest/CRC/member inventory；独立JUnit测量摘要；可重跑恢复与测量脚本。",
"",
"所有上述恢复动作均为读取、追加证据和复制公开工件；没有改写原branch、合并原PR、删除失败测试、降低断言、发布Release或启用外部插件执行。",
]
(REPO / "AI_NOVEL_STUDIO_FULL_VERSION_MAP.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote version map: {len(lines)} lines; PRs={len(prs)}, branches={len(branches)}, artifacts={len(artifacts)}")
