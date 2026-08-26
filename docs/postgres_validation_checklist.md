# PostgreSQL Runtime Validation Checklist

- [x] Docker available
- [x] Docker Compose available
- [x] PostgreSQL running and healthy
- [x] `DATABASE_URL` configured for validation process
- [x] Migration 001 executed (`schema_versions=0.1.0`)
- [x] Migration 002 executed (`schema_versions=0.2.0`)
- [x] Migration 003 executed (`schema_versions=0.4.0`)
- [x] Tables, indexes, and constraints inspected
- [x] Repository contract assertions passed directly against PostgreSQL (pytest runner remains PARTIAL)
- [x] File-to-PostgreSQL migration transaction passed
- [x] Repeated migration runs proved idempotent
- [ ] Context Compare passed (executed, but unequal)
- [x] Complete Author Flow passed (Mock AI provider; real PostgreSQL persistence)
- [ ] Frontend PostgreSQL flow passed
- [x] Runtime validation reports archived
