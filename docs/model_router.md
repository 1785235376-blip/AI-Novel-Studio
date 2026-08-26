# Model Router

路由由 role/profile 配置决定，并按有序 Route 回退。业务代码不判断具体厂商。Provider 失败被分类为 ProviderError；完整 Prompt 默认不记录。

