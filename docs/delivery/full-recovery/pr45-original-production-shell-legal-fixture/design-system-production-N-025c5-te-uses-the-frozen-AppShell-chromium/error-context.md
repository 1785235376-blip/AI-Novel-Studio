# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: design-system.spec.ts >> production NOVEL route uses the frozen AppShell
- Location: tests\visual\design-system.spec.ts:33:1

# Error details

```
Error: expect(locator).toHaveScreenshot(expected) failed

Locator: locator('.app-shell')
  38984 pixels (ratio 0.04 of all image pixels) are different.

  Snapshot: production-novel-shell.png

Call log:
  - Expect "toHaveScreenshot(production-novel-shell.png)" with timeout 5000ms
    - verifying given screenshot expectation
  - waiting for locator('.app-shell')
    - locator resolved to <div class="app-shell" data-module="NOVEL">…</div>
  - taking element screenshot
    - disabled all CSS animations
  - waiting for fonts to load...
  - fonts loaded
  - attempting scroll into view action
    - waiting for element to be stable
  - 38984 pixels (ratio 0.04 of all image pixels) are different.
  - waiting 100ms before taking screenshot
  - waiting for locator('.app-shell')
    - locator resolved to <div class="app-shell" data-module="NOVEL">…</div>
  - taking element screenshot
    - disabled all CSS animations
  - waiting for fonts to load...
  - fonts loaded
  - attempting scroll into view action
    - waiting for element to be stable
  - captured a stable screenshot
  - 38984 pixels (ratio 0.04 of all image pixels) are different.

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
      - generic [ref=e69]: 测
      - generic [ref=e70]: 测试创作者
  - navigation "当前创作范围" [ref=e71]:
    - generic [ref=e72]: 创作空间：当前工作区
    - generic [ref=e73]: /
    - generic [ref=e74]: 小说：测试小说
    - generic [ref=e75]: /
    - generic [ref=e76]: 故事线：测试故事线
    - generic [ref=e77]: /
    - generic [ref=e78]: 创作分支：测试草稿
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
          - status [ref=e90]:
            - strong [ref=e91]: 还没有章节
            - paragraph [ref=e92]: 正文目录中还没有章节。创建新章节开始写作，或从已移出章节中恢复。
          - region [ref=e93]:
            - heading "已移出章节" [level=3] [ref=e94]
            - paragraph [ref=e95]: 目前没有已移出章节。
        - generic [ref=e96]:
          - generic [ref=e97]: 工作区
          - strong [ref=e98]: 创作工具
        - generic [ref=e100]:
          - button "打开功能导航" [ref=e102] [cursor=pointer]: 功能导航
          - tooltip "打开功能导航"
    - generic [ref=e107]:
      - generic [ref=e109]:
        - generic [ref=e110]:
          - generic [ref=e111]:
            - generic [ref=e112]: 当前章节
            - generic [ref=e113]: 未选择章节
          - generic [ref=e114]: 0 字
          - generic "写作目标进度" [ref=e115]:
            - generic [ref=e116]: 目标 0 / 0 字
            - generic [ref=e117]: 第 0 / 0 章
            - progressbar [ref=e118]
            - strong [ref=e119]: 0%
        - generic [ref=e120]:
          - status [ref=e121]: 正在打开章节…
          - button "保存" [disabled] [ref=e124]
      - generic [ref=e126]:
        - strong [ref=e127]: 当前还没有打开的章节
        - paragraph [ref=e128]: 在左侧新建或选择章节，开始写作。
    - button "收起侧栏" [expanded] [ref=e129] [cursor=pointer]
    - complementary [ref=e133]:
      - separator "调整检查面板宽度" [ref=e134]
      - generic [ref=e135]:
        - generic [ref=e136]: 创作辅助
        - button "收起侧栏" [ref=e137] [cursor=pointer]
      - generic [ref=e141]:
        - region "当前写作上下文" [ref=e142]:
          - generic [ref=e143]: 当前章节
          - strong [ref=e144]: 未选择章节
          - generic [ref=e145]: 从左侧章节树选择章节
        - generic [ref=e146]:
          - heading "项目概览" [level=2] [ref=e147]
          - paragraph [ref=e148]: 设置本小说的创作目标，进度会同步显示在编辑器顶部。
          - generic [ref=e149]:
            - text: 目标字数
            - spinbutton "目标字数" [ref=e150]: "0"
          - generic [ref=e151]:
            - text: 目标章节
            - spinbutton "目标章节" [ref=e152]: "0"
          - generic [ref=e153]:
            - text: 截止日期
            - textbox "截止日期" [ref=e154]
          - button "保存写作目标" [disabled] [ref=e155]
        - generic [ref=e156]:
          - heading "AI 写作助手" [level=2] [ref=e158]
          - tablist "AI 写作方式" [ref=e159]:
            - tab "创作下一章" [selected] [ref=e160] [cursor=pointer]
            - tab "改写" [ref=e161] [cursor=pointer]
            - tab "润色" [ref=e162] [cursor=pointer]
            - tab "头脑风暴" [ref=e163] [cursor=pointer]
          - generic [ref=e164]:
            - text: 文本模型
            - combobox "文本模型" [ref=e165]:
              - option "尚未选择文本模型" [selected]
          - region [ref=e166]:
            - generic [ref=e167]:
              - strong [ref=e168]: 当前模型
              - generic [ref=e169]: 尚未选择模型
            - status [ref=e170]: 选择模型后可查看是否能够开始写作。
          - group "候选方案数量" [ref=e171]:
            - generic [ref=e172]: 候选方案
            - button "1" [pressed] [ref=e173] [cursor=pointer]
            - button "2" [ref=e174] [cursor=pointer]
            - button "3" [ref=e175] [cursor=pointer]
          - generic [ref=e176]:
            - text: 附加要求（可选）
            - textbox "附加要求（可选）" [ref=e177]:
              - /placeholder: 例如：保持紧张节奏，突出人物犹豫。
          - generic [ref=e178]:
            - text: 写作风格（可选）
            - textbox "写作风格（可选）" [ref=e179]:
              - /placeholder: 例如：克制、冷峻、短句为主
          - generic "写作风格预设" [ref=e180]:
            - button "克制冷峻 · 短句为主" [ref=e181] [cursor=pointer]
            - button "细腻抒情 · 强化感官" [ref=e182] [cursor=pointer]
            - button "紧张悬疑 · 加快节奏" [ref=e183] [cursor=pointer]
            - button "轻松幽默 · 对话自然" [ref=e184] [cursor=pointer]
          - button "生成创作下一章草稿" [disabled] [ref=e186]
          - region [ref=e187]:
            - generic [ref=e189]:
              - strong [ref=e190]: 生成流程
              - generic [ref=e191]: 上下文 → 计划 → 草稿 → 审核
            - list [ref=e192]:
              - listitem [ref=e193]:
                - generic [ref=e197]:
                  - generic [ref=e198]:
                    - strong [ref=e199]: 读取创作上下文
                    - generic [ref=e200]: 等待
                  - generic [ref=e201]: 开始生成后读取
              - listitem [ref=e202]:
                - generic [ref=e206]:
                  - generic [ref=e207]:
                    - strong [ref=e208]: 建立生成计划
                    - generic [ref=e209]: 等待
                  - generic [ref=e210]: 等待任务创建
              - listitem [ref=e211]:
                - generic [ref=e215]:
                  - generic [ref=e216]:
                    - strong [ref=e217]: 生成章节草稿
                    - generic [ref=e218]: 等待
                  - generic [ref=e219]: 等待生成
              - listitem [ref=e220]:
                - generic [ref=e224]:
                  - generic [ref=e225]:
                    - strong [ref=e226]: 作者审核
                    - generic [ref=e227]: 等待
                  - generic [ref=e228]: 等待可审核草稿
          - status [ref=e229]:
            - strong [ref=e230]: 尚未生成草稿
            - paragraph [ref=e231]: 选择写作方式并生成后，可在这里预览、比较和决定是否采用。
  - contentinfo [ref=e232]:
    - text: 保存：正在打开章节… · 连接：协作服务 · AI 任务：无运行任务
    - button "问助手" [ref=e234] [cursor=pointer]
```

# Test source

```ts
  1   | import {expect, test, type Page, type Route} from '@playwright/test';
  2   | 
  3   | const modules = ['NOVEL', 'IMAGE', 'VIDEO'] as const;
  4   | test.beforeEach(async ({page}) => {
  5   |   await page.addStyleTag({content: '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}'});
  6   | });
  7   | 
  8   | for (const module of modules) test(`${module.toLowerCase()} workspace visual baseline`, async ({page}) => {
  9   |   await page.goto(`/ui-fixture?module=${module}`);
  10  |   await page.evaluate(() => document.fonts.ready);
  11  |   await expect(page.locator('.app-shell')).toHaveScreenshot(`${module.toLowerCase()}-workspace.png`);
  12  | });
  13  | 
  14  | for (const viewport of [{width:1024,height:768},{width:1366,height:768},{width:1440,height:900},{width:1920,height:1080}]) test(`shell geometry ${viewport.width}x${viewport.height}`, async ({page}) => {
  15  |   await page.setViewportSize(viewport);
  16  |   await page.goto('/ui-fixture?module=NOVEL');
  17  |   const geometry = await page.evaluate(() => {
  18  |     const rect = (selector:string) => { const r=document.querySelector(selector)!.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height}; };
  19  |     return {header:rect('.global-header'),context:rect('.context-bar'),sidebar:rect('.workspace-sidebar'),inspector:rect('.workspace-inspector'),status:rect('.status-bar'),switcher:rect('.module-switcher')};
  20  |   });
  21  |   expect(geometry.header.height).toBe(56); expect(geometry.context.height).toBe(44); expect(geometry.status.height).toBe(32);
  22  |   expect(geometry.sidebar.width).toBe(viewport.width<1100?200:248); expect(geometry.inspector.width).toBe(viewport.width<1100?0:340); expect(geometry.switcher.y).toBe(0);
  23  | });
  24  | 
  25  | test('compact desktop keeps the workspace within the viewport', async ({page}) => {
  26  |   await page.setViewportSize({width:1024,height:768});
  27  |   await page.goto('/ui-fixture?module=NOVEL');
  28  |   const overflow = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, viewport: window.innerWidth, body: document.body.scrollWidth }));
  29  |   expect(overflow.width).toBeLessThanOrEqual(overflow.viewport);
  30  |   expect(overflow.body).toBeLessThanOrEqual(overflow.viewport);
  31  | });
  32  | 
  33  | test('production NOVEL route uses the frozen AppShell', async ({page}) => {
  34  |   await seedProductionShell(page);
  35  |   await page.goto('/');
  36  |   await expect(page.locator('.app-shell[data-module="NOVEL"]')).toBeVisible();
  37  |   await expect(page.locator('.context-bar')).toContainText('当前工作区');
  38  |   await expect(page.locator('.context-bar')).not.toContainText('workspace-real');
  39  |   await expect(page.locator('.context-bar')).not.toContainText('星海残章');
  40  |   await expect(page.locator('.novel-chapter-tree')).toContainText('还没有章节');
  41  |   await page.evaluate(() => document.fonts.ready);
  42  |   const geometry=await page.evaluate(()=>{
  43  |     const rect=(selector:string)=>{const r=document.querySelector(selector)!.getBoundingClientRect();return {width:r.width,height:r.height,left:r.left,right:r.right,bottom:r.bottom};};
  44  |     return {viewport:{width:innerWidth,height:innerHeight},shell:rect('.app-shell'),header:rect('.global-header'),context:rect('.context-bar'),sidebar:rect('.workspace-sidebar'),main:rect('.main-workspace'),inspector:rect('.workspace-inspector'),status:rect('.status-bar'),pageScrollWidth:document.documentElement.scrollWidth};
  45  |   });
  46  |   expect(geometry.viewport).toEqual({width:1440,height:900});
  47  |   expect(geometry.shell.width).toBe(1440);expect(geometry.shell.height).toBe(900);
  48  |   expect(geometry.header.height).toBe(56);expect(geometry.context.height).toBe(44);expect(geometry.status.height).toBe(32);
  49  |   expect(geometry.sidebar.width).toBe(248);expect(geometry.inspector.width).toBe(340);
  50  |   expect(geometry.main.width).toBe(804);
  51  |   expect(geometry.main.left).toBeGreaterThanOrEqual(geometry.sidebar.right);
  52  |   expect(geometry.main.right).toBeLessThanOrEqual(geometry.inspector.left);
  53  |   expect(geometry.pageScrollWidth).toBeLessThanOrEqual(geometry.viewport.width);
> 54  |   await expect(page.locator('.app-shell')).toHaveScreenshot('production-novel-shell.png');
      |                                            ^ Error: expect(locator).toHaveScreenshot(expected) failed
  55  | });
  56  | 
  57  | async function seedProductionShell(page:Page) {
  58  |   const scope={workspaceId:'workspace-real',projectId:'project-real',storylineId:'storyline-real',branchId:'branch-real',workspaceName:'当前工作区',projectName:'测试小说',storylineName:'测试故事线',branchName:'测试草稿'};
  59  |   await page.addInitScript(scope=>{localStorage.setItem('studio.session','visual-session');localStorage.setItem('studio.scope',JSON.stringify(scope));},{...scope});
  60  |   await page.route('**/api/**',async route=>{
  61  |     const path=new URL(route.request().url()).pathname;
  62  |     if(path.endsWith('/bootstrap'))return route.fulfill({json:{actor:{actor_id:'测试创作者',session_id:'session-real',client_id:'client-real'},scope:{workspace_id:scope.workspaceId,project_id:scope.projectId,storyline_id:scope.storylineId,branch_id:scope.branchId},capabilities:{}}});
  63  |     if(path.endsWith('/writing-goal'))return route.fulfill({json:{current_words:0,target_words:0,current_chapters:0,target_chapters:0,words_progress:0,chapters_progress:0,deadline:''}});
  64  |     if(path.endsWith('/text-models')||path.endsWith('/chapters/archived'))return route.fulfill({json:[]});
  65  |     if(path.endsWith('/experimental/features'))return route.fulfill({json:{experimental:false,default_enabled:false,features:{}}});
  66  |     if(path.endsWith('/media-tasks'))return route.fulfill({json:{novel_id:scope.projectId,audiobook:[],motion:[]}});
  67  |     return route.fulfill({json:{items:[]}});
  68  |   });
  69  | }
  70  | 
  71  | const v058Scope={workspaceId:'workspace-v058',projectId:'project-v058',storylineId:'storyline-v058',branchId:'branch-v058'};
  72  | async function seedV058Production(page:Page, conflict=false) {
  73  |   await page.addInitScript(({scope,conflict}) => {
  74  |     localStorage.setItem('studio.session','visual-session'); localStorage.setItem('studio.scope',JSON.stringify(scope));
  75  |     if (conflict) {
  76  |       let hash=2166136261; for(const character of 'visual-session') hash=Math.imul(hash^character.charCodeAt(0),16777619);
  77  |       const namespace=`${[scope.workspaceId,scope.projectId,scope.storylineId,scope.branchId].join('\u001f')}\u001fclient:${(hash>>>0).toString(36)}`;
  78  |       const local={chapterId:'chapter-v058',content:'Local resolution draft',baseVersion:1,updatedAt:'2026-08-10T10:00:00Z'};
  79  |       localStorage.setItem(`ai-novel-studio:draft:${namespace}:chapter-v058`,JSON.stringify(local));
  80  |       localStorage.setItem(`ai-novel-studio:conflict:${namespace}:chapter-v058`,JSON.stringify({chapterId:'chapter-v058',local,server:{id:'chapter-v058',novel_id:scope.projectId,number:1,title:'Conflict chapter',content:'Latest server content',document:{type:'doc',content:[]},version:2,word_count:3,status:'DRAFT'},detectedAt:'2026-08-10T10:01:00Z'}));
  81  |     }
  82  |   }, {scope:v058Scope,conflict});
  83  |   await page.route('**/api/**', async (route:Route) => {
  84  |     const path=new URL(route.request().url()).pathname;
  85  |     if(path.endsWith('/bootstrap')) return route.fulfill({json:{actor:{actor_id:'actor-v058',session_id:'session-v058',client_id:'client-v058'},scope:{workspace_id:v058Scope.workspaceId,project_id:v058Scope.projectId,storyline_id:v058Scope.storylineId,branch_id:v058Scope.branchId},capabilities:{}}});
  86  |     if(path.endsWith('/writing-goal')) return route.fulfill({json:{current_words:3,target_words:0,current_chapters:1,target_chapters:0,words_progress:0,chapters_progress:0}});
  87  |     if(path.endsWith('/text-models')||path.endsWith('/chapters/archived')) return route.fulfill({json:[]});
  88  |     if(path.endsWith('/experimental/features')) return route.fulfill({json:{experimental:false,default_enabled:false,features:{}}});
  89  |     if(path.endsWith('/chapters')&&path.includes('/collaboration/')) return route.fulfill({json:{items:[{id:'chapter-v058',novel_id:v058Scope.projectId,number:1,title:'Conflict chapter',version:2,word_count:3,status:'DRAFT'}]}});
  90  |     if(path.endsWith('/chapters/chapter-v058/revisions/1')) return route.fulfill({json:{version:1,timestamp:'2026-08-10T09:00:00Z',source:'USER',operator:'actor-old',reason:'MANUAL_SAVE',actor_id:'actor-old',document:{type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'Historical content'}]}]}}});
  91  |     if(path.endsWith('/chapters/chapter-v058/revisions')) return route.fulfill({json:{chapter_id:'chapter-v058',current_version:2,items:[{version:1,timestamp:'2026-08-10T09:00:00Z',source:'USER',operator:'actor-old',reason:'MANUAL_SAVE',actor_id:'actor-old'}]}});
  92  |     if(path.endsWith('/api/chapters/chapter-v058')&&route.request().method()==='GET') return route.fulfill({json:{id:'chapter-v058',novel_id:v058Scope.projectId,number:1,title:'Conflict chapter',content:'Latest server content',document:{type:'doc',content:[]},version:2,word_count:3,status:'DRAFT'}});
  93  |     if(path.includes('/history/1/restore')) return route.fulfill({status:409,json:{detail:{code:'VERSION_CONFLICT',message:'Current version changed',actual_version:3}}});
  94  |     return route.fulfill({json:{items:[]}});
  95  |   });
  96  | }
  97  | 
  98  | async function openProductionFeature(page:Page, name:string) {
  99  |   await page.getByRole('button',{name:'打开功能导航',exact:true}).click();
  100 |   await page.getByRole('navigation',{name:'功能面板导航'}).getByRole('button',{name,exact:true}).click();
  101 | }
  102 | 
  103 | test('production conflict compare and manual resolution visual', async ({page}) => {
  104 |   await seedV058Production(page,true); await page.goto('/');
  105 |   await expect(page.locator('[role="dialog"]')).toBeVisible();
  106 |   await expect(page.locator('[role="dialog"]')).toContainText('Local resolution draft');
  107 |   await expect(page.locator('[role="dialog"]')).toContainText('Latest server content');
  108 |   await expect(page.locator('[role="dialog"]')).toHaveScreenshot('production-conflict-resolution.png');
  109 | });
  110 | 
  111 | test('production revision detail restore preview and conflict visual', async ({page}) => {
  112 |   await seedV058Production(page); await page.goto('/');
  113 |   await openProductionFeature(page,'版本历史');
  114 |   await expect(page.locator('.revision-panel')).toBeVisible();
  115 |   await page.locator('.revision-timeline button').first().click();
  116 |   await expect(page.locator('.revision-detail')).toContainText('Historical content');
  117 |   await page.locator('.revision-detail>.ui-button').click();
  118 |   await expect(page.locator('.revision-confirm')).toBeVisible();
  119 |   await page.locator('.revision-confirm .ui-button--primary').click();
  120 |   await expect(page.locator('.revision-restore-message[role="alert"]')).toBeVisible();
  121 |   await page.locator('.revision-panel').scrollIntoViewIfNeeded();
  122 |   const geometry = await page.locator('.revision-panel').evaluate(panel => {
  123 |     const rect=panel.getBoundingClientRect();
  124 |     const main=panel.closest('.main-workspace')!.getBoundingClientRect();
  125 |     const status=document.querySelector('.status-bar')!.getBoundingClientRect();
  126 |     return {viewport:{width:innerWidth,height:innerHeight},panel:{width:rect.width,left:rect.left,right:rect.right,top:rect.top,bottom:rect.bottom},main:{left:main.left,right:main.right},statusTop:status.top,panelWidth:panel.clientWidth,panelScrollWidth:panel.scrollWidth,pageScrollWidth:document.documentElement.scrollWidth};
  127 |   });
  128 |   expect(geometry.viewport).toEqual({width:1440,height:900});
  129 |   expect(geometry.panel.width).toBe(802);
  130 |   expect(geometry.panel.left).toBeGreaterThanOrEqual(geometry.main.left);
  131 |   expect(geometry.panel.right).toBeLessThanOrEqual(geometry.main.right);
  132 |   expect(geometry.panel.top).toBeGreaterThanOrEqual(100);
  133 |   expect(geometry.panel.bottom).toBeLessThanOrEqual(geometry.statusTop);
  134 |   expect(geometry.panelScrollWidth).toBeLessThanOrEqual(geometry.panelWidth);
  135 |   expect(geometry.pageScrollWidth).toBeLessThanOrEqual(geometry.viewport.width);
  136 |   await expect(page.locator('.revision-panel')).toHaveScreenshot('production-revision-restore-conflict.png');
  137 | });
  138 | 
```