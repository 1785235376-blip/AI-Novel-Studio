# Workflow Design

Load→Context→Plan→Draft→Review→最多 MAX_REVISION_COUNT 次修订→Edit→原子保存→Summary→Pending Canon。ERROR 阻止完成；用户 Approve/Edit/Reject 决定 Canon。云端故障依次 Secondary→Local→DEGRADED。

