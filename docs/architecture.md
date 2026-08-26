# Architecture

Browser/Dify → Novel Service → Model Router → Provider Adapters；Novel Service 同时连接 PostgreSQL Canon、宿主机 Markdown/Knowledge Source。Cloud Writer 只收到经隐私裁剪的 Context Pack；Local Reviewer 返回修订意见；Archivist 只能写 Pending Canon，审批后才进入 Canon。

