-- ═══════════════════════════════════════════════════════════════════════
-- Celesys r63.71 — Institutional Positioning Database Schema
-- Target: Neon Postgres 16
-- Purpose: 13F filing storage + CUSIP/ticker mapping for the
--          institutional positioning scanner (Decide tab).
-- ═══════════════════════════════════════════════════════════════════════

-- ─── Tables drop in dependency order (for clean reruns during dev) ───
-- Comment out the DROPs in production. The migration script handles
-- "create if not exists" correctly without DROPs.
-- DROP TABLE IF EXISTS holdings CASCADE;
-- DROP TABLE IF EXISTS filings CASCADE;
-- DROP TABLE IF EXISTS filers CASCADE;
-- DROP TABLE IF EXISTS cusip_ticker_map CASCADE;
-- DROP TABLE IF EXISTS mapping_overrides CASCADE;

-- ═══════════════════════════════════════════════════════════════════════
-- filers — institutional managers who file 13F-HR (one row per CIK)
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS filers (
    cik             VARCHAR(10) PRIMARY KEY,           -- SEC Central Index Key, zero-padded
    name            TEXT NOT NULL,                     -- Manager legal name
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_filers_name ON filers (name);

-- ═══════════════════════════════════════════════════════════════════════
-- filings — one row per 13F-HR filing (CIK + period)
-- A 13F-HR is filed quarterly within 45 days of quarter-end.
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS filings (
    id              BIGSERIAL PRIMARY KEY,
    cik             VARCHAR(10) NOT NULL REFERENCES filers(cik) ON DELETE CASCADE,
    accession_no    VARCHAR(25) NOT NULL UNIQUE,       -- e.g. "0001752724-25-012345"
    period_of_report DATE NOT NULL,                    -- Quarter-end being reported (e.g. 2025-09-30)
    filed_at        TIMESTAMPTZ NOT NULL,              -- When SEC received it
    form_type       VARCHAR(20) NOT NULL,              -- "13F-HR" or "13F-HR/A" (amendment)
    is_amendment    BOOLEAN NOT NULL DEFAULT FALSE,
    total_value_usd BIGINT,                            -- Sum of all positions, in USD (already × 1000 from filing)
    holdings_count  INTEGER,                           -- Number of holdings in info table
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_filings_cik_period ON filings (cik, period_of_report DESC);
CREATE INDEX IF NOT EXISTS idx_filings_period ON filings (period_of_report DESC);

-- ═══════════════════════════════════════════════════════════════════════
-- holdings — individual line items from a 13F information table
-- One filing has 50–500 holdings rows. SPX 500 × 8 quarters across all
-- filers ≈ 5–15 million rows total — comfortably within Neon free tier.
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS holdings (
    id                  BIGSERIAL PRIMARY KEY,
    filing_id           BIGINT NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    cusip               VARCHAR(9) NOT NULL,           -- Always present in 13F
    ticker              VARCHAR(10),                   -- NULL until resolved via FIGI / overrides
    issuer_name         TEXT,                          -- "nameOfIssuer" from filing
    title_of_class      TEXT,                          -- "COM", "CL A", "PUT", "CALL", etc.
    value_usd           BIGINT NOT NULL,               -- Position value in USD (already × 1000)
    shares              BIGINT,                        -- Share count from filing
    put_call            VARCHAR(4),                    -- "PUT" / "CALL" / NULL for common
    investment_discretion VARCHAR(10),                 -- "SOLE", "DFND", "OTR"
    period_of_report    DATE NOT NULL,                 -- Denormalized from filings for fast Q-over-Q queries
    cik                 VARCHAR(10) NOT NULL           -- Denormalized for fast filer-level queries
);
CREATE INDEX IF NOT EXISTS idx_holdings_cusip_period ON holdings (cusip, period_of_report DESC);
CREATE INDEX IF NOT EXISTS idx_holdings_ticker_period ON holdings (ticker, period_of_report DESC) WHERE ticker IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_holdings_cik_period ON holdings (cik, period_of_report DESC);
CREATE INDEX IF NOT EXISTS idx_holdings_filing ON holdings (filing_id);

-- ═══════════════════════════════════════════════════════════════════════
-- cusip_ticker_map — resolved CUSIP → ticker via OpenFIGI
-- Cached forever. Once resolved, never re-queried.
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS cusip_ticker_map (
    cusip           VARCHAR(9) PRIMARY KEY,
    ticker          VARCHAR(10),                       -- NULL = no FIGI match (e.g. delisted, foreign)
    figi            VARCHAR(12),                       -- Bloomberg FIGI identifier
    name            TEXT,
    exchange        VARCHAR(20),                       -- "US", "UN" (NYSE), "UW" (NASDAQ), etc.
    security_type   VARCHAR(40),                       -- "Common Stock", "ETP", etc.
    confidence      VARCHAR(10) NOT NULL DEFAULT 'figi',  -- "figi", "manual", "unresolved"
    resolved_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    attempt_count   INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_cusip_map_ticker ON cusip_ticker_map (ticker) WHERE ticker IS NOT NULL;

-- ═══════════════════════════════════════════════════════════════════════
-- mapping_overrides — manual CUSIP/ticker corrections
-- Takes precedence over cusip_ticker_map at query time.
-- Use for: corporate actions, ticker changes, FIGI errors, edge cases.
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS mapping_overrides (
    cusip           VARCHAR(9) PRIMARY KEY,
    ticker          VARCHAR(10) NOT NULL,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT
);

-- ═══════════════════════════════════════════════════════════════════════
-- ingestion_log — operational visibility for backfill + recurring jobs
-- ═══════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS ingestion_log (
    id              BIGSERIAL PRIMARY KEY,
    job_name        VARCHAR(40) NOT NULL,              -- "backfill_q3_2025", "quarterly_sync", etc.
    status          VARCHAR(20) NOT NULL,              -- "started", "ok", "failed", "partial"
    filings_processed INTEGER NOT NULL DEFAULT 0,
    holdings_inserted INTEGER NOT NULL DEFAULT 0,
    cusips_resolved INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_ingestion_log_started ON ingestion_log (started_at DESC);
