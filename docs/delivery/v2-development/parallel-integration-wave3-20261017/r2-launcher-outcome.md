# Preserved pre-Python launcher error

The r2 freeze passed on db6487b5eab7340433426fefcb5499122ec3d881. First r2 stage launch then exited 127 before Python, the original runner, imports or tests: profile suffix replacement accidentally altered the fixed approved interpreter directory from ci-reconciliation-python-r1 to nonexistent ci-reconciliation-python-r2.

Parent authorized restoring only that launcher constant. The failed script is retained as run-r2-launch-path-error.sh; original failure output is origin-launch-r2.log. No original-runner receipt was produced for the failed launch. Actual renewed launch outputs use *-launch-r2b.log. The real interpreter remains ci-reconciliation-python-r1; actual runner profiles independently use wave3-integration-*-r2. Fresh natural and actual runner-child provenance preceded renewed tests. No product or test change accompanied this launcher correction.
