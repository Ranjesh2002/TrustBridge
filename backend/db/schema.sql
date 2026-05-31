-- TrustBridge — Real-world schema
-- Run: psql -U trustbridge -d trustbridge -f schema.sql

-- ── Users (merchants, suppliers, customers, vendors) ─────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    user_id         VARCHAR(20) UNIQUE NOT NULL,
    full_name       VARCHAR(100) NOT NULL,
    role            VARCHAR(20) NOT NULL CHECK (role IN ('merchant','supplier','vendor','customer')),
    phone           VARCHAR(15),
    location        VARCHAR(80),
    business_name   VARCHAR(150),
    business_type   VARCHAR(80),
    esewa_id        VARCHAR(20),
    khalti_id       VARCHAR(20),
    joined_date     DATE NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ── Merchants (extended profile, only for role=merchant) ─────────────────────

CREATE TABLE IF NOT EXISTS merchants (
    id              SERIAL PRIMARY KEY,
    merchant_id     VARCHAR(20) UNIQUE NOT NULL REFERENCES users(user_id),
    owner_name      VARCHAR(100) NOT NULL,
    legal_name      VARCHAR(150),
    location        VARCHAR(80),
    business_type   VARCHAR(80),
    segment         VARCHAR(30),
    months_active   INTEGER DEFAULT 0,
    digital_footprint BOOLEAN DEFAULT FALSE,
    esewa_registered  BOOLEAN DEFAULT FALSE,
    khalti_registered BOOLEAN DEFAULT FALSE,
    full_data       JSONB NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ── Transactions ─────────────────────────────────────────────────────────────
-- Every payment, purchase, utility bill, loan repayment etc. lives here

CREATE TABLE IF NOT EXISTS transactions (
    id              SERIAL PRIMARY KEY,
    txn_id          VARCHAR(30) UNIQUE NOT NULL,
    from_user_id    VARCHAR(20) NOT NULL REFERENCES users(user_id),
    to_user_id      VARCHAR(20) NOT NULL REFERENCES users(user_id),
    amount_npr      NUMERIC(12,2) NOT NULL,
    txn_type        VARCHAR(30) NOT NULL CHECK (txn_type IN (
                        'sale',           -- merchant sells to customer
                        'purchase',       -- merchant buys from supplier
                        'utility_nea',    -- NEA electricity bill
                        'utility_water',  -- water bill
                        'utility_internet',
                        'airtime_topup',  -- mobile recharge
                        'loan_disburse',  -- loan given to merchant
                        'loan_repayment', -- merchant repays loan
                        'vendor_service', -- vendor provides service
                        'refund',
                        'transfer'        -- peer transfer
                    )),
    status          VARCHAR(15) NOT NULL DEFAULT 'completed'
                        CHECK (status IN ('completed','pending','failed','reversed')),
    payment_method  VARCHAR(20) DEFAULT 'cash'
                        CHECK (payment_method IN ('cash','esewa','khalti','bank','credit')),
    description     TEXT,
    txn_date        DATE NOT NULL,
    txn_month       INTEGER GENERATED ALWAYS AS (EXTRACT(MONTH FROM txn_date)::int) STORED,
    txn_year        INTEGER GENERATED ALWAYS AS (EXTRACT(YEAR FROM txn_date)::int) STORED,
    days_to_pay     INTEGER DEFAULT 0,   -- 0 = paid same day, >0 = delayed
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ── Vouch edges ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS vouch_edges (
    id                  SERIAL PRIMARY KEY,
    from_merchant_id    VARCHAR(20) NOT NULL,
    to_merchant_id      VARCHAR(20) NOT NULL,
    edge_weight         FLOAT DEFAULT 1.0,
    created_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE (from_merchant_id, to_merchant_id)
);

-- ── Trust scores ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS trust_scores (
    id                  SERIAL PRIMARY KEY,
    merchant_id         VARCHAR(20) NOT NULL,
    final_score         INTEGER CHECK (final_score BETWEEN 0 AND 100),
    confidence          DECIMAL(4,2),
    segment             VARCHAR(30),
    social_score        INTEGER,
    psychometric_score  INTEGER,
    behavioral_score    INTEGER,
    lending_tier        VARCHAR(2),
    fraud_flag          BOOLEAN DEFAULT FALSE,
    full_result         JSONB,
    scored_at           TIMESTAMP DEFAULT NOW()
);

-- ── Psychometric responses ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS psychometric_responses (
    id                  SERIAL PRIMARY KEY,
    merchant_id         VARCHAR(20) NOT NULL,
    responses           JSONB NOT NULL,
    credit_personality  VARCHAR(80),
    assessed_at         TIMESTAMP DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_txn_from        ON transactions(from_user_id);
CREATE INDEX IF NOT EXISTS idx_txn_to          ON transactions(to_user_id);
CREATE INDEX IF NOT EXISTS idx_txn_date        ON transactions(txn_date);
CREATE INDEX IF NOT EXISTS idx_txn_type        ON transactions(txn_type);
CREATE INDEX IF NOT EXISTS idx_txn_month_year  ON transactions(txn_year, txn_month);
CREATE INDEX IF NOT EXISTS idx_trust_merchant  ON trust_scores(merchant_id);
CREATE INDEX IF NOT EXISTS idx_trust_time      ON trust_scores(scored_at DESC);
CREATE INDEX IF NOT EXISTS idx_vouch_from      ON vouch_edges(from_merchant_id);
CREATE INDEX IF NOT EXISTS idx_vouch_to        ON vouch_edges(to_merchant_id);