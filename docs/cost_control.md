# Cost Control

cloud_requests 预留 input/output/cached tokens、estimated_cost、latency。预算变量支持日/月/章额度。V0.1 尚未实现价格表与事务性预算锁，达到预算时应由路由拒绝非必要云调用并回退本地。

