import {expect,test} from '@playwright/test';

const viewports=[
  {width:1280,height:720},
  {width:1440,height:900},
  {width:1920,height:1080},
];

for(const viewport of viewports){
  test(`P0 feature launcher remains stable at ${viewport.width}x${viewport.height}`,async({page,request})=>{
    await page.setViewportSize(viewport);
    await page.goto('/',{waitUntil:'domcontentloaded'});
    await expect(page.getByPlaceholder('小说名称')).toBeVisible();
    const title=`P0 launcher ${viewport.width} ${Date.now()}`;
    await page.getByPlaceholder('小说名称').fill(title);
    const created=page.waitForResponse(response=>response.url().endsWith('/api/novels')&&response.request().method()==='POST'&&response.ok());
    await page.getByRole('button',{name:'创建小说'}).click();
    const novel=await (await created).json() as {id:string};
    for(let index=1;index<=48;index++){
      const response=await request.post(`/api/novels/${novel.id}/chapters`,{data:{title:`章节 ${index}`}});
      expect(response.ok()).toBeTruthy();
    }
    await page.reload({waitUntil:'domcontentloaded'});
    const sidebar=page.locator('.workspace-sidebar');
    const main=page.locator('.main-workspace');
    const inspector=page.locator('.workspace-inspector');
    const chapterScroll=page.locator('[data-testid="chapter-tree-scroll"]');
    const launcher=page.locator('.feature-launcher');
    await expect(launcher).toBeVisible();
    await expect(chapterScroll).toBeVisible();
    await chapterScroll.evaluate((element)=>{element.scrollTop=element.scrollHeight});
    await expect(launcher).toBeVisible();
    const before={sidebar:await sidebar.boundingBox(),main:await main.boundingBox(),inspector:await inspector.boundingBox()};
    await page.getByRole('button',{name:'打开功能导航'}).click();
    await expect(page.getByRole('navigation',{name:'功能面板导航'})).toBeVisible();
    const after={sidebar:await sidebar.boundingBox(),main:await main.boundingBox(),inspector:await inspector.boundingBox()};
    for(const key of ['sidebar','main','inspector'] as const){
      expect(after[key]?.width).toBe(before[key]?.width);
      expect(after[key]?.x).toBe(before[key]?.x);
    }
    await page.getByRole('button',{name:'版本历史'}).click();
    expect(await page.getByRole('button',{name:'版本历史'}).getAttribute('aria-current')).toBe('page');
    await page.locator('.main-workspace').click({position:{x:10,y:10}});
    await expect(page.getByRole('navigation',{name:'功能面板导航'})).toHaveCount(0);
    await expect(page.getByRole('button',{name:'打开功能导航'})).toBeFocused();
    await page.getByRole('button',{name:'打开功能导航'}).click();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('navigation',{name:'功能面板导航'})).toHaveCount(0);
    await expect(page.getByRole('button',{name:'打开功能导航'})).toBeFocused();
    await request.delete(`/api/novels/${novel.id}`);
  });
}
