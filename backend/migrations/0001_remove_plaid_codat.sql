-- Migration: Remove Plaid and Codat, leaving only QuickBooks Online.
-- This script drops old CHECK constraints on 'provider' and 'source' columns and enforces 'quickbooks' only.

-- 1. Clean up any existing data that doesn't match the new constraints (defensive cleanup)
DELETE FROM integrations WHERE provider != 'quickbooks';
DELETE FROM financial_snapshots WHERE source != 'quickbooks';

-- 2. Update integrations table provider CHECK constraint
-- If the constraint was created inline, it defaults to: integrations_provider_check
ALTER TABLE integrations DROP CONSTRAINT IF EXISTS integrations_provider_check;
ALTER TABLE integrations ADD CONSTRAINT integrations_provider_check CHECK (provider = 'quickbooks');

-- 3. Update financial_snapshots table source CHECK constraint
-- If the constraint was created inline, it defaults to: financial_snapshots_source_check
ALTER TABLE financial_snapshots DROP CONSTRAINT IF EXISTS financial_snapshots_source_check;
ALTER TABLE financial_snapshots ADD CONSTRAINT financial_snapshots_source_check CHECK (source = 'quickbooks');
