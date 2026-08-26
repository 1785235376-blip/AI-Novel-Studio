# V1.0 Backend Deployment

## Docker Compose

1. Copy `.env.example` to `.env` and set a strong `POSTGRES_PASSWORD`.
2. Start the stack with `docker compose up -d --build`.
3. Check `http://127.0.0.1:8000/health` and `http://127.0.0.1:8000/docs`.
4. Stop with `docker compose down`; preserve the named PostgreSQL volume.

The compose file binds PostgreSQL, API, and frontend to loopback by default. Put a reviewed reverse proxy in front before exposing it outside the machine.

## Direct Python

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use the repository `.venv` or an equivalent Python 3.11+ environment installed with `pip install -e .`.

## Secrets and data

- Store text/image Provider keys through the credential API and OS credential manager.
- Keep `.env`, `novel_data`, `logs`, and PostgreSQL volumes outside source control.
- Configure non-sensitive image Provider settings through `/api/asset-providers/{provider_id}`.
- Configure Worker defaults through `/api/asset-tasks/worker/config`.
