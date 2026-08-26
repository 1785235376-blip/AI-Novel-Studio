import { type ReactNode, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  LibraryBig,
  Plus,
  Users,
} from "lucide-react";
import {
  AdminWorkspace,
  ApiError,
  Scope,
  WorkspaceNavigationPath,
  api,
  createNovelKnowledgeReview,
  setCollaborationContext,
} from "../api";
import { Button, EmptyState, Panel } from "../ui/primitives";
import {
  NovelImportPanel,
  type NovelImportPlan,
  type NovelImportSource,
} from "./NovelImportPanel";
import {
  importChaptersWithRecovery,
  type ImportRecovery,
} from "./importRecovery";
import "./novel.css";

type Props = {
  initialToken: string;
  onEnter: (token: string, scope: Scope) => void;
  localHome?: ReactNode;
  packagedHost?: boolean;
};
type EntryMode = "PERSONAL" | "TEAM";
type PackagedStage = "LAUNCH" | "WORKSPACE" | "NOVELS";

export function EntryExperience({
  initialToken,
  onEnter,
  localHome,
  packagedHost = false,
}: Props) {
  const [token, setToken] = useState(initialToken),
    [workspaces, setWorkspaces] = useState<AdminWorkspace[]>([]),
    [workspace, setWorkspace] = useState<AdminWorkspace>(),
    [paths, setPaths] = useState<WorkspaceNavigationPath[]>([]),
    [projectTitle, setProjectTitle] = useState(""),
    [loading, setLoading] = useState(false),
    [ready, setReady] = useState(false),
    [error, setError] = useState(""),
    [mode, setMode] = useState<EntryMode>(),
    [stage, setStage] = useState<PackagedStage>("LAUNCH");
  const projectTitleRef = useRef<HTMLInputElement>(null),
    personalCreateRef = useRef<Promise<AdminWorkspace | undefined>>();

  async function recover(value = token) {
    if (!value.trim() && !packagedHost) return;
    setLoading(true);
    setError("");
    setCollaborationContext({ sessionToken: value.trim() });
    try {
      setWorkspaces(await api.adminWorkspaces());
    } catch (reason) {
      setError(
        reason instanceof ApiError && reason.status === 401
          ? "会话已失效，请重新打开应用。"
          : "无法准备创作空间，请稍后重试。",
      );
    } finally {
      setLoading(false);
      setReady(true);
    }
  }
  async function chooseWorkspace(item: AdminWorkspace, value = token) {
    setLoading(true);
    setError("");
    setCollaborationContext({ sessionToken: value.trim() });
    try {
      const navigation = await api.adminWorkspaceNavigation(item.id);
      setWorkspace(item);
      setPaths(navigation.eligible_paths);
      setStage("NOVELS");
    } catch {
      setError("无法打开创作空间，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }
  async function createPersonalWorkspace() {
    if (personalCreateRef.current) return personalCreateRef.current;
    const request = (async () => {
      setLoading(true);
      setError("");
      try {
        const created = await api.packagedProvisionInitialWorkspace();
        setWorkspaces((items) =>
          items.some((item) => item.id === created.id)
            ? items
            : [...items, created],
        );
        await chooseWorkspace(created);
        return created;
      } catch {
        setError("创作空间建立失败，请重试。");
        return undefined;
      } finally {
        setLoading(false);
        personalCreateRef.current = undefined;
      }
    })();
    personalCreateRef.current = request;
    return request;
  }
  async function selectMode(next: EntryMode) {
    setMode(next);
    setError("");
    if (next === "PERSONAL" && workspaces.length === 0) {
      await createPersonalWorkspace();
      return;
    }
    setWorkspace(undefined);
    setPaths([]);
    setStage("WORKSPACE");
  }
  function returnToLaunch() {
    setMode(undefined);
    setWorkspace(undefined);
    setPaths([]);
    setError("");
    setStage("LAUNCH");
  }
  function enter(path: WorkspaceNavigationPath, value = token) {
    onEnter(value.trim(), {
      workspaceId: path.workspace_id,
      projectId: path.project_id,
      storylineId: path.storyline_id,
      branchId: path.branch_id,
      workspaceName: workspace?.name,
      projectName: path.project_name,
      storylineName: path.storyline_name,
      branchName: path.branch_name,
    });
  }
  async function createProject() {
    if (!workspace || !projectTitle.trim()) return;
    setLoading(true);
    setError("");
    try {
      const created = await api.adminCreateProject(
        workspace.id,
        projectTitle.trim(),
      );
      const navigation = await api.adminWorkspaceNavigation(workspace.id);
      setPaths(navigation.eligible_paths);
      setProjectTitle("");
      const createdPath = navigation.eligible_paths.find(
        (path) => path.project_id === created.id,
      );
      if (createdPath) enter(createdPath);
    } catch {
      setError("无法创建小说，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }
  async function importProject(
    source: NovelImportSource,
    preview: { title: string },
    plan: NovelImportPlan,
    report: (message: string) => void,
  ) {
    if (!workspace) return;
    setLoading(true);
    setError("");
    const digest = Array.from(
      new Uint8Array(
        await crypto.subtle.digest(
          "SHA-256",
          new TextEncoder().encode(
            `${source.format}\n${source.contentBase64 || source.content}`,
          ),
        ),
      ),
    )
      .map((value) => value.toString(16).padStart(2, "0"))
      .join("");
    const recoveryKey = `novel-import:${workspace.id}:${digest}`;
    try {
      let stored = JSON.parse(localStorage.getItem(recoveryKey) || "null") as
        ({ path: WorkspaceNavigationPath } & ImportRecovery) | null;
      let navigation = await api.adminWorkspaceNavigation(workspace.id);
      if (!stored) {
        report("正在建立小说项目和主分支…");
        const created = await api.adminCreateProject(
          workspace.id,
          preview.title,
        );
        navigation = await api.adminWorkspaceNavigation(workspace.id);
        const path = navigation.eligible_paths.find(
          (item) => item.project_id === created.id,
        );
        if (!path) throw new Error("未建立默认创作分支");
        stored = { path, nextIndex: 0 };
        localStorage.setItem(recoveryKey, JSON.stringify(stored));
      } else report(`发现未完成导入，将从第 ${stored.nextIndex + 1} 章继续。`);
      const path = stored.path;
      const scope = {
        workspaceId: path.workspace_id,
        projectId: path.project_id,
        storylineId: path.storyline_id,
        branchId: path.branch_id,
      };
      setCollaborationContext({ sessionToken: token.trim(), scope });
      await importChaptersWithRecovery({
        plan,
        recovery: stored,
        persist: (state) =>
          localStorage.setItem(recoveryKey, JSON.stringify({ ...state, path })),
        create: (title) => api.scopedCreateChapter(scope, title),
        save: async (chapter, content) => {
          await api.saveChapter(
            chapter.id,
            content,
            chapter.version,
            undefined,
            "MANUAL_SAVE",
          );
        },
        report,
      });
      report("章节已写入，正在建立整本资料审查任务…");
      await createNovelKnowledgeReview(path.project_id);
      report(
        `已完成 ${plan.chapters.length}/${plan.chapters.length} 章，正在打开小说…`,
      );
      localStorage.removeItem(recoveryKey);
      setPaths(navigation.eligible_paths);
      enter(path);
    } catch {
      setError("小说导入在中途停止。再次选择同一文件并确认，即可从断点继续。");
      throw new Error("导入已暂停，可从断点继续。");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    if (initialToken || packagedHost) void recover(initialToken);
  }, []);

  if (packagedHost) {
    if (stage === "LAUNCH")
      return (
        <main className="novel-launch">
          <section className="novel-launch__identity">
            <BookOpen aria-hidden="true" />
            <p>长篇小说创作工作室</p>
            <h1>AI Novel Studio</h1>
            <span>选择本次创作方式，继续进入你的小说。</span>
          </section>
          <section className="novel-launch__choices" aria-label="选择创作方式">
            {loading ? (
              <p role="status">
                {ready ? "正在准备你的创作空间…" : "正在准备创作空间…"}
              </p>
            ) : (
              <>
                <Button
                  className="novel-launch__choice"
                  disabled={!!error}
                  onClick={() => void selectMode("PERSONAL")}
                >
                  <BookOpen aria-hidden="true" />
                  <span>
                    <strong>个人创作</strong>
                    <small>管理自己的小说与章节，专注个人写作。</small>
                  </span>
                  <ArrowRight aria-hidden="true" />
                </Button>
                <Button
                  className="novel-launch__choice"
                  disabled={!!error}
                  onClick={() => void selectMode("TEAM")}
                >
                  <Users aria-hidden="true" />
                  <span>
                    <strong>团队协作</strong>
                    <small>进入已有团队创作空间，与成员共同工作。</small>
                  </span>
                  <ArrowRight aria-hidden="true" />
                </Button>
              </>
            )}
            {error && (
              <div className="novel-entry-error">
                <p role="alert">{error}</p>
                <Button onClick={() => void recover()}>重试</Button>
              </div>
            )}
          </section>
        </main>
      );
    if (stage === "WORKSPACE")
      return (
        <main className="novel-entry-page">
          <header className="novel-entry-page__header">
            <Button variant="ghost" onClick={returnToLaunch}>
              <ArrowLeft aria-hidden="true" />
              返回
            </Button>
            <div>
              <span>AI Novel Studio</span>
              <h1>
                {mode === "PERSONAL" ? "选择个人创作空间" : "选择团队创作空间"}
              </h1>
              <p>
                {mode === "PERSONAL"
                  ? "已有空间无法可靠区分用途，请选择这次要使用的创作空间。"
                  : "仅显示当前账号已有权限进入的团队创作空间。"}
              </p>
            </div>
          </header>
          <section className="novel-workspace-selection">
            {loading ? (
              <p role="status">正在准备创作空间…</p>
            ) : mode === "TEAM" && workspaces.length === 0 ? (
              <EmptyState
                title="目前还没有可加入的团队创作空间"
                detail="当你获得团队空间权限后，它会显示在这里。"
              />
            ) : (
              <div className="novel-workspace-grid" aria-label="可用创作空间">
                {workspaces.map((item) => (
                  <Button
                    className="novel-workspace-card"
                    key={item.id}
                    onClick={() => void chooseWorkspace(item)}
                  >
                    <LibraryBig aria-hidden="true" />
                    <span>
                      <strong>{item.name}</strong>
                      <small>进入创作空间</small>
                    </span>
                    <ArrowRight aria-hidden="true" />
                  </Button>
                ))}
              </div>
            )}
            {error && (
              <p className="novel-error" role="alert">
                {error}
              </p>
            )}
          </section>
        </main>
      );
    const focusCreate = () => projectTitleRef.current?.focus();
    return (
      <main className="novel-entry-page novel-library-page">
        <header className="novel-entry-page__header">
          <Button variant="ghost" onClick={() => setStage("WORKSPACE")}>
            <ArrowLeft aria-hidden="true" />
            切换创作空间
          </Button>
          <div>
            <span>{workspace?.name}</span>
            <h1>我的小说</h1>
            <p>从最近的故事继续，或开始一部新的创作。</p>
          </div>
        </header>
        <div className="novel-library__overview" aria-label="创作空间概览">
          <div>
            <span>当前空间</span>
            <strong>{workspace?.name || "未命名空间"}</strong>
          </div>
          <div>
            <span>可用小说</span>
            <strong>{paths.length}</strong>
          </div>
          <div>
            <span>运行任务</span>
            <strong>暂无</strong>
            <small>任务中心待接入</small>
          </div>
        </div>
        <div className="novel-library__layout">
          <section className="novel-library__collection">
            <div className="novel-library__section-head">
              <div>
                <span className="novel-kicker">STORIES</span>
                <h2>最近小说</h2>
              </div>
              <span className="novel-library__count">{paths.length} 部</span>
            </div>
            {error && (
              <p className="novel-error" role="alert">
                {error}
              </p>
            )}
            {loading && <p role="status">正在加载小说…</p>}
            {!loading && !paths.length ? (
              <div className="novel-entry-empty">
                <EmptyState
                  title="还没有小说"
                  detail="创建第一部小说，开始写下你的故事。"
                />
                <Button onClick={focusCreate}>
                  <Plus aria-hidden="true" />
                  新建小说
                </Button>
              </div>
            ) : !loading ? (
              <div className="novel-entry-grid" aria-label="已有小说">
                {paths.map((path) => (
                  <Button
                    className="novel-entry-card"
                    key={`${path.project_id}:${path.storyline_id}:${path.branch_id}`}
                    onClick={() => enter(path)}
                  >
                    <BookOpen aria-hidden="true" />
                    <span>
                      <strong>{path.project_name || "未命名小说"}</strong>
                      <small>
                        {path.storyline_name || "默认故事线"} ·{" "}
                        {path.branch_name || "主分支"} · 打开小说
                      </small>
                    </span>
                    <ArrowRight aria-hidden="true" />
                  </Button>
                ))}
              </div>
            ) : null}
            <div className="novel-library__task-slot" aria-label="任务状态">
              <span>任务状态</span>
              <p>当前空间没有正在运行的生成任务。</p>
              <Button variant="ghost" disabled>
                打开任务中心
              </Button>
            </div>
          </section>
          <aside
            className="novel-entry-create"
            aria-labelledby="create-novel-title"
          >
            <div>
              <Plus aria-hidden="true" />
              <div>
                <h2 id="create-novel-title">新建小说</h2>
                <p>输入小说名称即可开始创作。</p>
              </div>
            </div>
            <label>
              小说名称
              <input
                ref={projectTitleRef}
                value={projectTitle}
                maxLength={200}
                disabled={loading}
                onChange={(event) => setProjectTitle(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && projectTitle.trim() && !loading)
                    void createProject();
                }}
                placeholder="例如：雾港来信"
              />
            </label>
            <Button
              variant="primary"
              disabled={!projectTitle.trim() || loading}
              onClick={() => void createProject()}
            >
              {loading ? "正在创建…" : "新建小说"}
            </Button>
            <NovelImportPanel onConfirm={importProject} />
          </aside>
        </div>
      </main>
    );
  }
  return (
    <main className="home novel-entry">
      <h1>AI Novel Studio</h1>
      <p>选择创作空间和小说，继续写作。</p>
      {!initialToken && !workspaces.length && (
        <details className="novel-entry-advanced">
          <summary>连接已有创作空间</summary>
          <Panel title="安全连接">
            <label>
              访问凭证
              <input
                type="password"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                autoComplete="current-password"
              />
            </label>
            <Button
              variant="primary"
              disabled={!token.trim() || loading}
              onClick={() => void recover()}
            >
              {loading ? "正在连接…" : "连接创作空间"}
            </Button>
          </Panel>
        </details>
      )}
      {error && (
        <p className="novel-error" role="alert">
          {error}
        </p>
      )}
      {loading && <p role="status">正在加载创作空间…</p>}
      {!!workspaces.length && !workspace && (
        <Panel title="选择创作空间">
          <div className="novel-entry-grid">
            {workspaces.map((item) => (
              <Button key={item.id} onClick={() => void chooseWorkspace(item)}>
                {item.name}
              </Button>
            ))}
          </div>
        </Panel>
      )}
      {workspace && (
        <Panel title="新建小说">
          <label>
            小说名称
            <input
              value={projectTitle}
              maxLength={200}
              onChange={(event) => setProjectTitle(event.target.value)}
              placeholder="输入小说名称"
            />
          </label>
          <Button
            variant="primary"
            disabled={!projectTitle.trim() || loading}
            onClick={() => void createProject()}
          >
            {loading ? "正在创建…" : "创建并打开"}
          </Button>
        </Panel>
      )}
      {workspace && !paths.length && !loading && (
        <EmptyState
          title="这个创作空间还没有小说"
          detail="输入小说名称，系统会同时建立默认故事线和主分支。"
        />
      )}
      {!!paths.length && (
        <Panel title={workspace?.name || "选择小说"}>
          <div className="novel-entry-grid">
            {paths.map((path) => (
              <Button
                key={`${path.project_id}:${path.storyline_id}:${path.branch_id}`}
                onClick={() => enter(path)}
              >
                <strong>{path.project_name || "未命名小说"}</strong>
                <span>
                  {path.storyline_name || "故事线"} ·{" "}
                  {path.branch_name || "主分支"}
                </span>
              </Button>
            ))}
          </div>
        </Panel>
      )}
      {!initialToken && localHome}
    </main>
  );
}
