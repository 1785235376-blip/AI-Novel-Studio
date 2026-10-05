-- Historical foreshadowing writes did not persist a policy. Missing or invalid
-- policies cannot be reconstructed: retain content locally and mark for review.
UPDATE foreshadowing
SET details = details || '{"privacy_level":"LOCAL_ONLY","privacy_status":"UNKNOWN"}'::jsonb
WHERE NOT (details ? 'privacy_level')
   OR jsonb_typeof(details->'privacy_level') IS DISTINCT FROM 'string'
   OR details->>'privacy_level' NOT IN ('LOCAL_ONLY','CLOUD_ALLOWED','REDACT_BEFORE_CLOUD');

ALTER TABLE foreshadowing ADD CONSTRAINT foreshadowing_privacy_policy_valid
CHECK (details ? 'privacy_level'
       AND jsonb_typeof(details->'privacy_level') = 'string'
       AND details->>'privacy_level' IN ('LOCAL_ONLY','CLOUD_ALLOWED','REDACT_BEFORE_CLOUD'));

-- Imported records that explicitly recorded absent source policy are unknown,
-- not consent to send the source off-device.
UPDATE characters SET privacy = 'LOCAL_ONLY'
WHERE facts->>'_source_privacy_present' = 'false' AND privacy = 'CLOUD_ALLOWED';
UPDATE locations SET privacy = 'LOCAL_ONLY'
WHERE facts->>'_source_privacy_present' = 'false' AND privacy = 'CLOUD_ALLOWED';

-- New rows with no explicit policy are local. Existing explicit policies remain.
ALTER TABLE characters ALTER COLUMN privacy SET DEFAULT 'LOCAL_ONLY';
ALTER TABLE locations ALTER COLUMN privacy SET DEFAULT 'LOCAL_ONLY';
ALTER TABLE organizations ALTER COLUMN privacy SET DEFAULT 'LOCAL_ONLY';
ALTER TABLE timeline_events ALTER COLUMN privacy SET DEFAULT 'LOCAL_ONLY';
ALTER TABLE canon_entries ALTER COLUMN privacy SET DEFAULT 'LOCAL_ONLY';
