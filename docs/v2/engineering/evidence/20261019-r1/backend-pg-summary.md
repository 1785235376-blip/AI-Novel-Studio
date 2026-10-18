# Focused real-PostgreSQL contract subset

Round: 2026-10-19 r1 · tested baseline SHA: a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3

Command: --junitxml=evidence/backend-pg-subset.xml
Log: Engineering-Runs/20261019-r1/logs/backend-pg-evidence.log

Summary: 118 passed, 151 deselected, 1 warning in 148.53s (0:02:28)

Failures/errors: none recorded.

Last log lines:
~~~
..............................................                           [100%]
============================== warnings summary ===============================
C:\Users\admin\AppData\Local\Programs\Python\Python311\Lib\site-packages\fastapi\testclient.py:1
  C:\Users\admin\AppData\Local\Programs\Python\Python311\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
118 passed, 151 deselected, 1 warning in 148.53s (0:02:28)
~~~
