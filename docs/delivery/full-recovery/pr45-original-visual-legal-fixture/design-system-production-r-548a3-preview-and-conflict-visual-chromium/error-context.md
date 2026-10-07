# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: design-system.spec.ts >> production revision detail restore preview and conflict visual
- Location: tests\visual\design-system.spec.ts:83:1

# Error details

```
Error: expect(locator).toHaveScreenshot(expected) failed

Locator: locator('.revision-panel')
  Expected an image 802px by 742px, received 802px by 383px. 14663 pixels (ratio 0.03 of all image pixels) are different.

  Snapshot: production-revision-restore-conflict.png

Call log:
  - Expect "toHaveScreenshot(production-revision-restore-conflict.png)" with timeout 5000ms
    - verifying given screenshot expectation
  - waiting for locator('.revision-panel')
    - locator resolved to <section class="ui-panel revision-panel">…</section>
  - taking element screenshot
    - disabled all CSS animations
  - waiting for fonts to load...
  - fonts loaded
  - attempting scroll into view action
    - waiting for element to be stable
  - Expected an image 802px by 742px, received 802px by 383px. 14663 pixels (ratio 0.03 of all image pixels) are different.
  - waiting 100ms before taking screenshot
  - waiting for locator('.revision-panel')
    - locator resolved to <section class="ui-panel revision-panel">…</section>
  - taking element screenshot
    - disabled all CSS animations
  - waiting for fonts to load...
  - fonts loaded
  - attempting scroll into view action
    - waiting for element to be stable
  - captured a stable screenshot
  - Expected an image 802px by 742px, received 802px by 383px. 14663 pixels (ratio 0.03 of all image pixels) are different.

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - banner [ref=e4]:
    - generic "AI Novel Studio" [ref=e5]:
      - generic [ref=e9]:
        - strong [ref=e10]: AI Novel
        - generic [ref=e11]: Studio
    - tablist "创作模块" [ref=e12]:
      - tab "小说" [selected] [ref=e13] [cursor=pointer]
      - tab "图片" [ref=e17] [cursor=pointer]
      - tab "视频" [ref=e23] [cursor=pointer]
      - tab "资产" [ref=e28] [cursor=pointer]
      - tab "声音" [ref=e32] [cursor=pointer]
      - tab "主控" [ref=e38] [cursor=pointer]
      - tab "插件" [ref=e52] [cursor=pointer]
      - tab "工作流" [ref=e56] [cursor=pointer]
    - button "打开全局命令" [ref=e62] [cursor=pointer]:
      - generic [ref=e66]: 搜索作品、章节与素材
      - generic [ref=e67]: Ctrl K
    - generic [ref=e68]:
      - generic [ref=e69]: A
      - generic [ref=e70]: actor-v058
  - navigation "当前创作范围" [ref=e71]:
    - generic [ref=e72]: 创作空间：workspace-v058
    - generic [ref=e73]: /
    - generic [ref=e74]: 小说：project-v058
    - generic [ref=e75]: /
    - generic [ref=e76]: 故事线：storyline-v058
    - generic [ref=e77]: /
    - generic [ref=e78]: 创作分支：branch-v058
  - main [ref=e79]:
    - complementary [ref=e80]:
      - generic [ref=e81]:
        - generic [ref=e82]:
          - generic [ref=e83]: 小说结构
          - strong [ref=e84]: 章节导航
        - generic [ref=e86]:
          - generic [ref=e87]:
            - heading "作品结构" [level=2] [ref=e88]
            - button "新建章节" [ref=e89] [cursor=pointer]
          - navigation "章节列表" [ref=e90]:
            - list [ref=e91]:
              - listitem [ref=e92]:
                - generic [ref=e93]:
                  - button "1. Conflict chapter 已保存" [ref=e94] [cursor=pointer]:
                    - generic "Conflict chapter" [ref=e95]: 1. Conflict chapter
                    - generic [ref=e96]: 已保存
                  - generic [ref=e97]:
                    - button "重命名Conflict chapter" [ref=e98] [cursor=pointer]
                    - button "更多章节操作Conflict chapter" [ref=e102] [cursor=pointer]
          - region [ref=e107]:
            - heading "已移出章节" [level=3] [ref=e108]
            - paragraph [ref=e109]: 目前没有已移出章节。
        - generic [ref=e110]:
          - generic [ref=e111]: 工作区
          - strong [ref=e112]: 创作工具
        - generic [ref=e114]:
          - button "打开功能导航" [ref=e116] [cursor=pointer]: 功能导航
          - tooltip "打开功能导航"
    - generic [ref=e121]:
      - generic [ref=e123]:
        - generic [ref=e124]:
          - generic [ref=e125]:
            - generic [ref=e126]: 当前章节
            - generic [ref=e127]: Conflict chapter
          - generic [ref=e128]: 21 字
          - generic "写作目标进度" [ref=e129]:
            - generic [ref=e130]: 目标 3 / 0 字
            - generic [ref=e131]: 第 1 / 0 章
            - progressbar [ref=e132]
            - strong [ref=e133]: 0%
        - generic [ref=e134]:
          - status [ref=e135]: 已保存
          - button "保存" [ref=e139] [cursor=pointer]
      - textbox "章节正文" [ref=e142]:
        - paragraph [ref=e143]
      - generic [ref=e144]:
        - heading "版本记录" [level=2] [ref=e146]
        - generic [ref=e147]:
          - navigation "版本记录时间线" [ref=e148]:
            - list [ref=e149]:
              - listitem [ref=e150]:
                - button "版本 1 手动保存 actor-old · 2026/8/10 17:00:00" [ref=e151] [cursor=pointer]:
                  - strong [ref=e153]: 版本 1
                  - generic [ref=e154]: 手动保存
                  - generic [ref=e155]: actor-old · 2026/8/10 17:00:00
          - region "版本详情" [ref=e156]:
            - generic [ref=e157]:
              - generic [ref=e158]:
                - heading "历史版本 1" [level=3] [ref=e159]
                - paragraph [ref=e160]: 手动保存 · actor-old · 2026/8/10 17:00:00
              - generic [ref=e161]: 当前版本 2
            - generic "历史版本 1 与当前版本 2 的正文比较" [ref=e162]:
              - generic [ref=e163]:
                - heading "历史版本 1" [level=4] [ref=e164]
                - generic [ref=e165]: Historical content
              - generic [ref=e166]:
                - heading "当前正文（版本 2）" [level=4] [ref=e167]
                - generic [ref=e168]: Latest server content
            - alert [ref=e169]:
              - generic [ref=e172]:
                - strong [ref=e173]: 版本冲突，未恢复
                - paragraph [ref=e174]: Current version changed
            - group "确认恢复历史版本" [ref=e175]:
              - paragraph [ref=e176]:
                - strong [ref=e177]: 恢复历史版本 1？
              - paragraph [ref=e178]: 恢复后会以这份正文创建一个新的当前版本；现有历史版本不会被删除。
              - generic [ref=e179]:
                - button "恢复此版本" [ref=e180] [cursor=pointer]
                - button "取消" [ref=e181] [cursor=pointer]
    - button "收起侧栏" [expanded] [ref=e182] [cursor=pointer]
    - complementary [ref=e186]:
      - separator "调整检查面板宽度" [ref=e187]
      - generic [ref=e188]:
        - generic [ref=e189]: 创作辅助
        - button "收起侧栏" [ref=e190] [cursor=pointer]
      - generic [ref=e194]:
        - region "当前写作上下文" [ref=e195]:
          - generic [ref=e196]: 当前章节
          - strong [ref=e197]: Conflict chapter
          - generic [ref=e198]: 第 1 章 · 版本 2
        - generic [ref=e199]:
          - heading "项目概览" [level=2] [ref=e200]
          - paragraph [ref=e201]: 设置本小说的创作目标，进度会同步显示在编辑器顶部。
          - generic [ref=e202]:
            - text: 目标字数
            - spinbutton "目标字数" [ref=e203]: "0"
          - generic [ref=e204]:
            - text: 目标章节
            - spinbutton "目标章节" [ref=e205]: "0"
          - generic [ref=e206]:
            - text: 截止日期
            - textbox "截止日期" [ref=e207]
          - button "保存写作目标" [disabled] [ref=e208]
        - region "正文外发策略" [ref=e209]:
          - group [ref=e210]:
            - generic "正文隐私：仅本地或尚未确认" [ref=e211]
            - option "仅本地" [selected]
            - option "允许我选定的云模型接收此版本"
        - generic [ref=e212]:
          - heading "AI 写作助手" [level=2] [ref=e214]
          - tablist "AI 写作方式" [ref=e215]:
            - tab "创作下一章" [selected] [ref=e216] [cursor=pointer]
            - tab "改写" [ref=e217] [cursor=pointer]
            - tab "润色" [ref=e218] [cursor=pointer]
            - tab "头脑风暴" [ref=e219] [cursor=pointer]
          - generic [ref=e220]:
            - text: 文本模型
            - combobox "文本模型" [ref=e221]:
              - option "尚未选择文本模型" [selected]
          - region [ref=e222]:
            - generic [ref=e223]:
              - strong [ref=e224]: 当前模型
              - generic [ref=e225]: 尚未选择模型
            - status [ref=e226]: 选择模型后可查看是否能够开始写作。
          - group "候选方案数量" [ref=e227]:
            - generic [ref=e228]: 候选方案
            - button "1" [pressed] [ref=e229] [cursor=pointer]
            - button "2" [ref=e230] [cursor=pointer]
            - button "3" [ref=e231] [cursor=pointer]
          - generic [ref=e232]:
            - text: 附加要求（可选）
            - textbox "附加要求（可选）" [ref=e233]:
              - /placeholder: 例如：保持紧张节奏，突出人物犹豫。
          - generic [ref=e234]:
            - text: 写作风格（可选）
            - textbox "写作风格（可选）" [ref=e235]:
              - /placeholder: 例如：克制、冷峻、短句为主
          - generic "写作风格预设" [ref=e236]:
            - button "克制冷峻 · 短句为主" [ref=e237] [cursor=pointer]
            - button "细腻抒情 · 强化感官" [ref=e238] [cursor=pointer]
            - button "紧张悬疑 · 加快节奏" [ref=e239] [cursor=pointer]
            - button "轻松幽默 · 对话自然" [ref=e240] [cursor=pointer]
          - region [ref=e241]:
            - generic [ref=e242]:
              - generic [ref=e243]:
                - heading "AI Context Preview" [level=3] [ref=e244]
                - paragraph [ref=e245]: 角色上下文资料检查。它与写作生成的请求构造不同，不是最终发送预览。
              - generic [ref=e246]: 资料检查
            - generic [ref=e247]:
              - generic [ref=e248]:
                - text: 上下文目标
                - combobox "上下文目标" [ref=e249]:
                  - option "本地上下文" [selected]
                  - option "云端安全上下文"
              - button "刷新上下文" [ref=e250] [cursor=pointer]
            - status [ref=e251]: 点击“刷新上下文”，读取当前写作方式对应的 Context Service 数据。
          - button "生成创作下一章草稿" [disabled] [ref=e253]
          - region [ref=e254]:
            - generic [ref=e256]:
              - strong [ref=e257]: 生成流程
              - generic [ref=e258]: 上下文 → 计划 → 草稿 → 审核
            - list [ref=e259]:
              - listitem [ref=e260]:
                - generic [ref=e264]:
                  - generic [ref=e265]:
                    - strong [ref=e266]: 读取创作上下文
                    - generic [ref=e267]: 等待
                  - generic [ref=e268]: 开始生成后读取
              - listitem [ref=e269]:
                - generic [ref=e273]:
                  - generic [ref=e274]:
                    - strong [ref=e275]: 建立生成计划
                    - generic [ref=e276]: 等待
                  - generic [ref=e277]: 等待任务创建
              - listitem [ref=e278]:
                - generic [ref=e282]:
                  - generic [ref=e283]:
                    - strong [ref=e284]: 生成章节草稿
                    - generic [ref=e285]: 等待
                  - generic [ref=e286]: 等待生成
              - listitem [ref=e287]:
                - generic [ref=e291]:
                  - generic [ref=e292]:
                    - strong [ref=e293]: 作者审核
                    - generic [ref=e294]: 等待
                  - generic [ref=e295]: 等待可审核草稿
          - status [ref=e296]:
            - strong [ref=e297]: 尚未生成草稿
            - paragraph [ref=e298]: 选择写作方式并生成后，可在这里预览、比较和决定是否采用。
  - contentinfo [ref=e299]:
    - text: 保存：已保存 · 连接：协作服务 · AI 任务：无运行任务
    - button "问助手" [ref=e301] [cursor=pointer]
```

# Test source

```ts
  1  | import {expect, test, type Page, type Route} from '@playwright/test';
  2  | 
  3  | const modules = ['NOVEL', 'IMAGE', 'VIDEO'] as const;
  4  | test.beforeEach(async ({page}) => {
  5  |   await page.addStyleTag({content: '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}'});
  6  | });
  7  | 
  8  | for (const module of modules) test(`${module.toLowerCase()} workspace visual baseline`, async ({page}) => {
  9  |   await page.goto(`/ui-fixture?module=${module}`);
  10 |   await page.evaluate(() => document.fonts.ready);
  11 |   await expect(page.locator('.app-shell')).toHaveScreenshot(`${module.toLowerCase()}-workspace.png`);
  12 | });
  13 | 
  14 | for (const viewport of [{width:1024,height:768},{width:1366,height:768},{width:1440,height:900},{width:1920,height:1080}]) test(`shell geometry ${viewport.width}x${viewport.height}`, async ({page}) => {
  15 |   await page.setViewportSize(viewport);
  16 |   await page.goto('/ui-fixture?module=NOVEL');
  17 |   const geometry = await page.evaluate(() => {
  18 |     const rect = (selector:string) => { const r=document.querySelector(selector)!.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height}; };
  19 |     return {header:rect('.global-header'),context:rect('.context-bar'),sidebar:rect('.workspace-sidebar'),inspector:rect('.workspace-inspector'),status:rect('.status-bar'),switcher:rect('.module-switcher')};
  20 |   });
  21 |   expect(geometry.header.height).toBe(56); expect(geometry.context.height).toBe(44); expect(geometry.status.height).toBe(32);
  22 |   expect(geometry.sidebar.width).toBe(viewport.width<1100?200:248); expect(geometry.inspector.width).toBe(viewport.width<1100?0:340); expect(geometry.switcher.y).toBe(0);
  23 | });
  24 | 
  25 | test('compact desktop keeps the workspace within the viewport', async ({page}) => {
  26 |   await page.setViewportSize({width:1024,height:768});
  27 |   await page.goto('/ui-fixture?module=NOVEL');
  28 |   const overflow = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, viewport: window.innerWidth, body: document.body.scrollWidth }));
  29 |   expect(overflow.width).toBeLessThanOrEqual(overflow.viewport);
  30 |   expect(overflow.body).toBeLessThanOrEqual(overflow.viewport);
  31 | });
  32 | 
  33 | test('production NOVEL route uses the frozen AppShell', async ({page}) => {
  34 |   await page.addInitScript(() => {localStorage.setItem('studio.session','visual-session');localStorage.setItem('studio.scope',JSON.stringify({workspaceId:'workspace-real',projectId:'project-real',storylineId:'storyline-real',branchId:'branch-real'}));});
  35 |   await page.goto('/');
  36 |   await expect(page.locator('.app-shell[data-module="NOVEL"]')).toBeVisible();
  37 |   await expect(page.locator('.context-bar')).toContainText('当前工作区');
  38 |   await expect(page.locator('.context-bar')).not.toContainText('workspace-real');
  39 |   await expect(page.locator('.context-bar')).not.toContainText('星海残章');
  40 |   await expect(page.locator('.app-shell')).toHaveScreenshot('production-novel-shell.png');
  41 | });
  42 | 
  43 | const v058Scope={workspaceId:'workspace-v058',projectId:'project-v058',storylineId:'storyline-v058',branchId:'branch-v058'};
  44 | async function seedV058Production(page:Page, conflict=false) {
  45 |   await page.addInitScript(({scope,conflict}) => {
  46 |     localStorage.setItem('studio.session','visual-session'); localStorage.setItem('studio.scope',JSON.stringify(scope));
  47 |     if (conflict) {
  48 |       let hash=2166136261; for(const character of 'visual-session') hash=Math.imul(hash^character.charCodeAt(0),16777619);
  49 |       const namespace=`${[scope.workspaceId,scope.projectId,scope.storylineId,scope.branchId].join('\u001f')}\u001fclient:${(hash>>>0).toString(36)}`;
  50 |       const local={chapterId:'chapter-v058',content:'Local resolution draft',baseVersion:1,updatedAt:'2026-08-10T10:00:00Z'};
  51 |       localStorage.setItem(`ai-novel-studio:draft:${namespace}:chapter-v058`,JSON.stringify(local));
  52 |       localStorage.setItem(`ai-novel-studio:conflict:${namespace}:chapter-v058`,JSON.stringify({chapterId:'chapter-v058',local,server:{id:'chapter-v058',novel_id:scope.projectId,number:1,title:'Conflict chapter',content:'Latest server content',document:{type:'doc',content:[]},version:2,word_count:3,status:'DRAFT'},detectedAt:'2026-08-10T10:01:00Z'}));
  53 |     }
  54 |   }, {scope:v058Scope,conflict});
  55 |   await page.route('**/api/**', async (route:Route) => {
  56 |     const path=new URL(route.request().url()).pathname;
  57 |     if(path.endsWith('/bootstrap')) return route.fulfill({json:{actor:{actor_id:'actor-v058',session_id:'session-v058',client_id:'client-v058'},scope:{workspace_id:v058Scope.workspaceId,project_id:v058Scope.projectId,storyline_id:v058Scope.storylineId,branch_id:v058Scope.branchId},capabilities:{}}});
  58 |     if(path.endsWith('/writing-goal')) return route.fulfill({json:{current_words:3,target_words:0,current_chapters:1,target_chapters:0,words_progress:0,chapters_progress:0}});
  59 |     if(path.endsWith('/text-models')||path.endsWith('/chapters/archived')) return route.fulfill({json:[]});
  60 |     if(path.endsWith('/experimental/features')) return route.fulfill({json:{experimental:false,default_enabled:false,features:{}}});
  61 |     if(path.endsWith('/chapters')&&path.includes('/collaboration/')) return route.fulfill({json:{items:[{id:'chapter-v058',novel_id:v058Scope.projectId,number:1,title:'Conflict chapter',version:2,word_count:3,status:'DRAFT'}]}});
  62 |     if(path.endsWith('/chapters/chapter-v058/revisions/1')) return route.fulfill({json:{version:1,timestamp:'2026-08-10T09:00:00Z',source:'USER',operator:'actor-old',reason:'MANUAL_SAVE',actor_id:'actor-old',document:{type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'Historical content'}]}]}}});
  63 |     if(path.endsWith('/chapters/chapter-v058/revisions')) return route.fulfill({json:{chapter_id:'chapter-v058',current_version:2,items:[{version:1,timestamp:'2026-08-10T09:00:00Z',source:'USER',operator:'actor-old',reason:'MANUAL_SAVE',actor_id:'actor-old'}]}});
  64 |     if(path.endsWith('/api/chapters/chapter-v058')&&route.request().method()==='GET') return route.fulfill({json:{id:'chapter-v058',novel_id:v058Scope.projectId,number:1,title:'Conflict chapter',content:'Latest server content',document:{type:'doc',content:[]},version:2,word_count:3,status:'DRAFT'}});
  65 |     if(path.includes('/history/1/restore')) return route.fulfill({status:409,json:{detail:{code:'VERSION_CONFLICT',message:'Current version changed',actual_version:3}}});
  66 |     return route.fulfill({json:{items:[]}});
  67 |   });
  68 | }
  69 | 
  70 | async function openProductionFeature(page:Page, name:string) {
  71 |   await page.getByRole('button',{name:'打开功能导航',exact:true}).click();
  72 |   await page.getByRole('navigation',{name:'功能面板导航'}).getByRole('button',{name,exact:true}).click();
  73 | }
  74 | 
  75 | test('production conflict compare and manual resolution visual', async ({page}) => {
  76 |   await seedV058Production(page,true); await page.goto('/');
  77 |   await expect(page.locator('[role="dialog"]')).toBeVisible();
  78 |   await expect(page.locator('[role="dialog"]')).toContainText('Local resolution draft');
  79 |   await expect(page.locator('[role="dialog"]')).toContainText('Latest server content');
  80 |   await expect(page.locator('[role="dialog"]')).toHaveScreenshot('production-conflict-resolution.png');
  81 | });
  82 | 
  83 | test('production revision detail restore preview and conflict visual', async ({page}) => {
  84 |   await seedV058Production(page); await page.goto('/');
  85 |   await openProductionFeature(page,'版本历史');
  86 |   await expect(page.locator('.revision-panel')).toBeVisible();
  87 |   await page.locator('.revision-timeline button').first().click();
  88 |   await expect(page.locator('.revision-detail')).toContainText('Historical content');
  89 |   await page.locator('.revision-detail>.ui-button').click();
  90 |   await expect(page.locator('.revision-confirm')).toBeVisible();
  91 |   await page.locator('.revision-confirm .ui-button--primary').click();
  92 |   await expect(page.locator('.revision-restore-message[role="alert"]')).toBeVisible();
> 93 |   await expect(page.locator('.revision-panel')).toHaveScreenshot('production-revision-restore-conflict.png');
     |                                                 ^ Error: expect(locator).toHaveScreenshot(expected) failed
  94 | });
  95 | 
```