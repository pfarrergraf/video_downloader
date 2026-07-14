-- Provider-neutral entitlement identity for future Apple/Windows providers.
-- Legacy rows remain provider='legacy'; Google Play writes google_play + token hash.
ALTER TABLE licenses ADD COLUMN provider TEXT NOT NULL DEFAULT 'legacy';
ALTER TABLE licenses ADD COLUMN provider_subject TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_licenses_provider_subject
  ON licenses(provider, provider_subject) WHERE provider_subject IS NOT NULL;
