BEGIN;
CREATE TABLE domain_role_assignments(id TEXT PRIMARY KEY,payload JSONB NOT NULL);
CREATE TABLE permission_assignments(id TEXT PRIMARY KEY,payload JSONB NOT NULL);
CREATE TABLE authorization_audit_events(id TEXT PRIMARY KEY,payload JSONB NOT NULL);
CREATE INDEX idx_domain_role_principal ON domain_role_assignments((payload->>'principal_id'));
CREATE INDEX idx_permission_principal ON permission_assignments((payload->>'principal_id'));
CREATE INDEX idx_authorization_audit_scope ON authorization_audit_events((payload->'scope'->>'workspace_id'));
INSERT INTO schema_versions(version) VALUES ('0.5.5-scope-authorization-foundation');
COMMIT;
