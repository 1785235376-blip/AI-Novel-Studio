# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: v2-prompt-adoption-ui-live.spec.ts >> isolated original button commits bound Prompt and reload preserves its exact source pin
- Location: tests\e2e\v2-prompt-adoption-ui-live.spec.ts:19:1

# Error details

```
Error: {"detail":{"code":"BRANCH_SOURCE_UNAVAILABLE"},"code":"BRANCH_SOURCE_UNAVAILABLE","message":"BRANCH_SOURCE_UNAVAILABLE","details":{"code":"BRANCH_SOURCE_UNAVAILABLE"},"request_id":"a48b379e-9c3f-467f-b125-0f832b714b38"}

expect(received).toBe(expected) // Object.is equality

Expected: 200
Received: 409
```

# Test source

```ts
  1   | import { createHash } from 'node:crypto';
  2   | import { expect, test, type APIResponse } from '@playwright/test';
  3   | import { openPromptWorkspace, promptLibrary } from '../../e2e/promptAcceptanceEntry';
  4   | 
  5   | const FIRST = '  采用成功闭环 第一版\n逐字中文与 emoji 🙂  \n';
  6   | const NEWER = '  来源家族第二版；不应自动替换已采用修订 🎬\n';
  7   | const CONSENT = '我已核对来源正文、修订与当前镜头版本，确认替换画面提示词。';
  8   | const canonical = (value: unknown): string => {
  9   |   if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  10  |   if (value !== null && typeof value === 'object') {
  11  |     const row = value as Record<string, unknown>;
  12  |     return `{${Object.keys(row).sort().map(key => `${JSON.stringify(key)}:${canonical(row[key])}`).join(',')}}`;
  13  |   }
  14  |   const rendered = JSON.stringify(value);
  15  |   if (rendered === undefined) throw new Error('Canonical owner data contains undefined.');
  16  |   return rendered;
  17  | };
  18  | 
  19  | test('isolated original button commits bound Prompt and reload preserves its exact source pin', async ({ page, request }, info) => {
  20  |   const token = process.env.STUDIO_PROMPT_ADOPTION_UI_BROWSER_TOKEN;
  21  |   if (!token) throw new Error('The isolated launcher must obtain an original packaged bootstrap session.');
  22  |   const errors: string[] = [], calls: { method: string; path: string; status: number }[] = [];
  23  |   page.on('pageerror', error => errors.push(error.message));
  24  |   page.on('response', response => {
  25  |     const path = new URL(response.url()).pathname;
  26  |     if (path.startsWith('/api/')) calls.push({ method: response.request().method(), path, status: response.status() });
  27  |   });
  28  |   const exact = async (response: APIResponse, status: number) => {
> 29  |     expect(response.status(), await response.text()).toBe(status);
      |                                                      ^ Error: {"detail":{"code":"BRANCH_SOURCE_UNAVAILABLE"},"code":"BRANCH_SOURCE_UNAVAILABLE","message":"BRANCH_SOURCE_UNAVAILABLE","details":{"code":"BRANCH_SOURCE_UNAVAILABLE"},"request_id":"a48b379e-9c3f-467f-b125-0f832b714b38"}
  30  |     return response.json();
  31  |   };
  32  |   const admin = '/api/collaboration/admin/workspaces/workspace-a';
  33  |   let headers: Record<string, string> = { 'X-Session-Token': token };
  34  |   let projectId = '';
  35  |   const title = `采用 UI 验收 ${info.project.name}`;
  36  |   const boardTitle = `真实分镜 ${info.project.name}`;
  37  |   try {
  38  |     const project = await exact(await request.post(`${admin}/projects`, { headers,
  39  |       data: { title, genre: '' } }), 201);
  40  |     projectId = project.id;
  41  |     const navigation = await exact(await request.get(`${admin}/navigation`, { headers }), 200);
  42  |     const path = navigation.eligible_paths.find((row: { project_id: string }) => row.project_id === projectId);
  43  |     expect(path).toBeTruthy(); headers = { ...headers, 'X-Branch-ID': path.branch_id };
  44  |     const studio = `/api/projects/${projectId}/studio`;
  45  |     await exact(await request.post(`${studio}/activate`, { headers }), 200);
  46  |     const character = await exact(await request.put(`/api/novels/${projectId}/characters/ui-bound-character`,
  47  |       { headers, data: { name: '采用时真实角色目标' } }), 200);
  48  |     const characters = await exact(await request.get(`/api/novels/${projectId}/characters`, { headers }), 200);
  49  |     const originalCharacter = characters.find((row: { id: string }) => row.id === character.id);
  50  |     expect(originalCharacter).toBeTruthy();
  51  |     const characterDigest = createHash('sha256').update(canonical(originalCharacter)).digest('hex');
  52  |     const creative = `/api/novels/${projectId}/experimental/creative/documents`;
  53  |     const script = await exact(await request.post(creative, { headers, data: { mode: 'SCREENPLAY',
  54  |       title: `真实来源剧本 ${info.project.name}`, source_independent: true,
  55  |       scenes: [{ id: 'real-ui-scene', sequence: 1, heading: 'INT. ROOM - DAY', action: 'A visitor arrives.' }] } }), 201);
  56  |     const board = await exact(await request.post(`${creative}/${script.id}/derive`, { headers,
  57  |       data: { expected_version: script.version, mode: 'STORYBOARD', title: boardTitle, shot_policy: 'SCENE' } }), 201);
  58  |     expect(board.shots).toHaveLength(1);
  59  |     const shotId = board.shots[0].id;
  60  |     const ownerPath = `${creative}/${board.id}`;
  61  |     const adoptionPath = `${studio}/documents/${board.id}/shots/${shotId}/prompt-adoption`;
  62  |     const projectionPath = `${studio}/documents/${board.id}/prompt-adoption`;
  63  | 
  64  |     // Reconnect, project choice and module changes are all existing product UI.
  65  |     // A full reload can return to the entry screen or restore the same project.
  66  |     const enterProject = async () => {
  67  |       await page.goto('/');
  68  |       await expect.poll(async () =>
  69  |         await page.getByText('连接已有创作空间', { exact: true }).isVisible()
  70  |         || await page.getByLabel('访问凭证', { exact: true }).isVisible()
  71  |         || await page.getByRole('button', { name: '我的创作空间', exact: true }).isVisible()
  72  |         || await page.getByText(title, { exact: true }).first().isVisible(), { timeout: 30_000 }).toBe(true);
  73  |       if (await page.getByText('连接已有创作空间', { exact: true }).isVisible()) {
  74  |         await page.getByText('连接已有创作空间', { exact: true }).click();
  75  |         await expect(page.getByLabel('访问凭证', { exact: true })).toBeVisible();
  76  |       }
  77  |       if (await page.getByLabel('访问凭证', { exact: true }).isVisible()) {
  78  |         await page.getByLabel('访问凭证', { exact: true }).fill(token);
  79  |         await page.getByRole('button', { name: '连接创作空间', exact: true }).click();
  80  |         await expect(page.getByRole('button', { name: '我的创作空间', exact: true })).toBeVisible();
  81  |       }
  82  |       const workspace = page.getByRole('button', { name: '我的创作空间', exact: true });
  83  |       const projectChoice = page.getByRole('button', { name: new RegExp(title) });
  84  |       if (await workspace.isVisible()) {
  85  |         await workspace.click();
  86  |         await expect(projectChoice).toBeVisible();
  87  |       }
  88  |       if (await projectChoice.isVisible()) await projectChoice.click();
  89  |       await expect(page.getByText(title, { exact: true }).first()).toBeVisible();
  90  |     };
  91  |     const openBoard = async () => {
  92  |       await page.getByRole('button', { name: '小说', exact: true }).click();
  93  |       await page.getByRole('button', { name: '打开 V2 创作工作台', exact: true }).click();
  94  |       await page.getByRole('tab', { name: /^分镜/ }).click();
  95  |       await page.getByRole('region', { name: '创作文档', exact: true })
  96  |         .getByRole('button', { name: new RegExp(boardTitle) }).click();
  97  |       await page.getByRole('button', { name: '按需打开镜头工作区', exact: true }).click();
  98  |       const shots = page.getByRole('region', { name: '分镜工作区', exact: true });
  99  |       await shots.getByRole('button', { name: '读取已保存分镜', exact: true }).click();
  100 |       await shots.getByRole('button', { name: `镜头 1（身份 ${shotId}）`, exact: true }).click();
  101 |       return shots;
  102 |     };
  103 |     const pin = async () => {
  104 |       const show = page.getByRole('button', { name: '查看 Prompt 采用来源', exact: true });
  105 |       if (await show.isVisible()) await show.click();
  106 |       const value = page.locator('.prompt-adoption-record');
  107 |       await expect(value).toBeVisible();
  108 |       return value;
  109 |     };
  110 | 
  111 |     await enterProject();
  112 |     await openPromptWorkspace(page);
  113 |     await page.getByRole('button', { name: '新建 Prompt', exact: true }).click();
  114 |     await page.getByLabel('正文', { exact: true }).fill(FIRST);
  115 |     await page.getByLabel('角色 ID', { exact: true }).fill(character.id);
  116 |     const creating = page.waitForResponse(response => new URL(response.url()).pathname === `${studio}/prompts`
  117 |       && response.request().method() === 'POST');
  118 |     await page.getByRole('button', { name: '保存为新 Prompt', exact: true }).click();
  119 |     const creation = await creating;
  120 |     expect(creation.status(), await creation.text()).toBe(201);
  121 |     expect(creation.request().postDataJSON().character_ids).toEqual([character.id]);
  122 |     const source = await creation.json();
  123 |     await expect(page.locator('.prompt-status')).toContainText('已保存');
  124 | 
  125 |     await openBoard();
  126 |     await page.getByRole('button', { name: '核对 Prompt 采用条件', exact: true }).click();
  127 |     const operation = page.getByRole('region', { name: 'Prompt 采用操作', exact: true });
  128 |     await operation.getByLabel('Prompt 来源家族', { exact: true }).selectOption(source.family_id);
  129 |     await operation.getByRole('button', { name: '读取所选 Prompt 修订', exact: true }).click();
```