"""
PostgreSQL persistence layer for TrustBridge.
Updated to support users + transactions schema.
"""
import os
import json
import asyncpg
from typing import Optional, List, Dict

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://trustbridge:trustbridge@db:5432/trustbridge"
)

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def init_db():
    """Create tables if not present (idempotent)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            SERIAL PRIMARY KEY,
                user_id       VARCHAR(20) UNIQUE NOT NULL,
                full_name     VARCHAR(100) NOT NULL,
                role          VARCHAR(20) NOT NULL,
                phone         VARCHAR(15),
                location      VARCHAR(80),
                business_name VARCHAR(150),
                business_type VARCHAR(80),
                esewa_id      VARCHAR(20),
                khalti_id     VARCHAR(20),
                joined_date   DATE NOT NULL,
                created_at    TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS merchants (
                id                SERIAL PRIMARY KEY,
                merchant_id       VARCHAR(20) UNIQUE NOT NULL,
                owner_name        VARCHAR(100) NOT NULL,
                legal_name        VARCHAR(150),
                location          VARCHAR(80),
                business_type     VARCHAR(80),
                segment           VARCHAR(30),
                months_active     INTEGER DEFAULT 0,
                digital_footprint BOOLEAN DEFAULT FALSE,
                esewa_registered  BOOLEAN DEFAULT FALSE,
                khalti_registered BOOLEAN DEFAULT FALSE,
                full_data         JSONB NOT NULL,
                created_at        TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id             SERIAL PRIMARY KEY,
                txn_id         VARCHAR(30) UNIQUE NOT NULL,
                from_user_id   VARCHAR(20) NOT NULL,
                to_user_id     VARCHAR(20) NOT NULL,
                amount_npr     NUMERIC(12,2) NOT NULL,
                txn_type       VARCHAR(30) NOT NULL,
                status         VARCHAR(15) NOT NULL DEFAULT 'completed',
                payment_method VARCHAR(20) DEFAULT 'cash',
                description    TEXT,
                txn_date       DATE NOT NULL,
                days_to_pay    INTEGER DEFAULT 0,
                created_at     TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS vouch_edges (
                id               SERIAL PRIMARY KEY,
                from_merchant_id VARCHAR(20) NOT NULL,
                to_merchant_id   VARCHAR(20) NOT NULL,
                edge_weight      FLOAT DEFAULT 1.0,
                created_at       TIMESTAMP DEFAULT NOW(),
                UNIQUE (from_merchant_id, to_merchant_id)
            );

            CREATE TABLE IF NOT EXISTS trust_scores (
                id                 SERIAL PRIMARY KEY,
                merchant_id        VARCHAR(20) NOT NULL,
                final_score        INTEGER CHECK (final_score BETWEEN 0 AND 100),
                confidence         DECIMAL(4,2),
                segment            VARCHAR(30),
                social_score       INTEGER,
                psychometric_score INTEGER,
                behavioral_score   INTEGER,
                lending_tier       VARCHAR(2),
                fraud_flag         BOOLEAN DEFAULT FALSE,
                full_result        JSONB,
                scored_at          TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS psychometric_responses (
                id                 SERIAL PRIMARY KEY,
                merchant_id        VARCHAR(20) NOT NULL,
                responses          JSONB NOT NULL,
                credit_personality VARCHAR(80),
                assessed_at        TIMESTAMP DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_txn_from       ON transactions(from_user_id);
            CREATE INDEX IF NOT EXISTS idx_txn_to         ON transactions(to_user_id);
            CREATE INDEX IF NOT EXISTS idx_txn_date       ON transactions(txn_date);
            CREATE INDEX IF NOT EXISTS idx_txn_type       ON transactions(txn_type);
            CREATE INDEX IF NOT EXISTS idx_trust_merchant ON trust_scores(merchant_id);
            CREATE INDEX IF NOT EXISTS idx_trust_time     ON trust_scores(scored_at DESC);
            CREATE INDEX IF NOT EXISTS idx_vouch_from     ON vouch_edges(from_merchant_id);
            CREATE INDEX IF NOT EXISTS idx_vouch_to       ON vouch_edges(to_merchant_id);
        """)
    print("✅ DB tables created/verified")


async def seed_merchants(merchants: List[Dict]):
    """Seed merchant data (idempotent). Used for JSON-based seeding."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM merchants")
        if count > 0:
            print(f"✅ DB already has {count} merchants, skipping seed")
            return
        for m in merchants:
            meta = m["business_metadata"]
            is_digital = meta.get("segment", "") == "Digital Native"
            await conn.execute("""
                INSERT INTO merchants
                    (merchant_id, owner_name, legal_name, location, business_type,
                     segment, months_active, digital_footprint, esewa_registered,
                     khalti_registered, full_data)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (merchant_id) DO NOTHING
            """,
                m["merchant_id"], meta.get("owner_name",""), meta.get("legal_name",""),
                meta.get("location",""), meta.get("business_type",""), meta.get("segment",""),
                meta.get("months_active", 0), is_digital, is_digital, False, json.dumps(m)
            )
        for m in merchants:
            mid = m["merchant_id"]
            targets = m.get("layer_1_social_graph",{}).get("vouch_edges_to",[])
            weight  = m["layer_1_social_graph"].get("vouch_metrics",{}).get("vouch_edge_weight",1.0)
            for target in targets:
                try:
                    await conn.execute("""
                        INSERT INTO vouch_edges (from_merchant_id, to_merchant_id, edge_weight)
                        VALUES ($1,$2,$3) ON CONFLICT DO NOTHING
                    """, mid, target, weight)
                except Exception:
                    pass
        final  = await conn.fetchval("SELECT COUNT(*) FROM merchants")
        edges  = await conn.fetchval("SELECT COUNT(*) FROM vouch_edges")
        print(f"✅ Seeded {final} merchants and {edges} vouch edges")


# ── Merchant CRUD ─────────────────────────────────────────────────────────────

async def get_all_merchants() -> List[Dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT merchant_id, owner_name, legal_name, location, business_type,
                   segment, months_active, digital_footprint, esewa_registered, khalti_registered
            FROM merchants ORDER BY merchant_id
        """)
        return [dict(r) for r in rows]


async def get_merchant_full(merchant_id: str) -> Optional[Dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT full_data FROM merchants WHERE merchant_id=$1", merchant_id
        )
        return json.loads(row["full_data"]) if row else None


async def get_all_merchants_full() -> List[Dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT full_data FROM merchants ORDER BY merchant_id")
        return [json.loads(r["full_data"]) for r in rows]


# ── Transaction queries ───────────────────────────────────────────────────────

async def get_merchant_transactions(
    merchant_id: str,
    limit: int = 200,
    txn_type: str = None,
    month: int = None,
    year: int = None,
) -> List[Dict]:
    """All transactions where merchant is sender or receiver."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = ["(t.from_user_id=$1 OR t.to_user_id=$1)"]
        params = [merchant_id]
        i = 2
        if txn_type:
            where.append(f"t.txn_type=${i}")
            params.append(txn_type)
            i += 1
        if month:
            where.append(f"EXTRACT(MONTH FROM t.txn_date)=${i}")
            params.append(month)
            i += 1
        if year:
            where.append(f"EXTRACT(YEAR FROM t.txn_date)=${i}")
            params.append(year)
            i += 1
        params.append(limit)
        sql = f"""
            SELECT t.*, u1.full_name as from_name, u2.full_name as to_name
            FROM transactions t
            LEFT JOIN users u1 ON u1.user_id = t.from_user_id
            LEFT JOIN users u2 ON u2.user_id = t.to_user_id
            WHERE {' AND '.join(where)}
            ORDER BY t.txn_date DESC
            LIMIT ${i}
        """
        rows = await conn.fetch(sql, *params)
        return [dict(r) for r in rows]


async def get_merchant_monthly_summary(merchant_id: str) -> List[Dict]:
    """Monthly credits, debits, net flow per merchant."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                EXTRACT(YEAR  FROM txn_date)::int  AS year,
                EXTRACT(MONTH FROM txn_date)::int  AS month,
                SUM(CASE WHEN to_user_id=$1   THEN amount_npr ELSE 0 END) AS credits,
                SUM(CASE WHEN from_user_id=$1 THEN amount_npr ELSE 0 END) AS debits,
                COUNT(*) AS txn_count
            FROM transactions
            WHERE from_user_id=$1 OR to_user_id=$1
            GROUP BY year, month
            ORDER BY year, month
        """, merchant_id)
        result = []
        for r in rows:
            d = dict(r)
            d["net"]      = float(d["credits"]) - float(d["debits"])
            d["coverage"] = round(float(d["credits"]) / max(float(d["debits"]), 1), 3)
            result.append(d)
        return result


async def get_transaction_stats(merchant_id: str) -> Dict:
    """Aggregate stats used by behavioral engine."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                COUNT(*)                                              AS total_txns,
                SUM(CASE WHEN to_user_id=$1 THEN amount_npr END)     AS total_credits,
                SUM(CASE WHEN from_user_id=$1 THEN amount_npr END)   AS total_debits,
                AVG(CASE WHEN from_user_id=$1 THEN days_to_pay END)  AS avg_days_to_pay,
                COUNT(DISTINCT CASE WHEN to_user_id=$1
                      AND txn_type='sale' THEN from_user_id END)     AS unique_customers,
                COUNT(CASE WHEN txn_type='utility_nea'
                      AND from_user_id=$1
                      AND days_to_pay < 5 THEN 1 END)                AS nea_ontime_count,
                COUNT(CASE WHEN txn_type='airtime_topup'
                      AND from_user_id=$1 THEN 1 END)                AS topup_count
            FROM transactions
            WHERE from_user_id=$1 OR to_user_id=$1
        """, merchant_id)
        return dict(row) if row else {}


# ── Score / psychometric persistence ─────────────────────────────────────────

async def save_trust_score(merchant_id: str, result: Dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        lt = result.get("lending_tier", {})
        await conn.execute("""
            INSERT INTO trust_scores
                (merchant_id, final_score, confidence, segment,
                 social_score, psychometric_score, behavioral_score,
                 lending_tier, fraud_flag, full_result)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        """,
            merchant_id,
            result.get("final_score"),
            result.get("confidence"),
            result.get("segment"),
            result.get("sub_scores", {}).get("social"),
            result.get("sub_scores", {}).get("psychometric"),
            result.get("sub_scores", {}).get("behavioral"),
            lt.get("tier"),
            result.get("fraud_flag", False),
            json.dumps(result)
        )


async def save_psychometric(merchant_id: str, responses: Dict, result: Dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO psychometric_responses (merchant_id, responses, credit_personality)
            VALUES ($1,$2,$3)
        """, merchant_id, json.dumps(responses), result.get("credit_personality",""))


async def get_score_history(merchant_id: str, limit: int = 5) -> List[Dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT final_score, confidence, lending_tier, fraud_flag,
                   social_score, psychometric_score, behavioral_score,
                   full_result, scored_at
            FROM trust_scores
            WHERE merchant_id=$1
            ORDER BY scored_at DESC LIMIT $2
        """, merchant_id, limit)
        return [dict(r) for r in rows]


# ── Graph queries ─────────────────────────────────────────────────────────────

async def get_vouch_neighbors(merchant_id: str) -> Dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        vouched_by = await conn.fetch("""
            SELECT ve.from_merchant_id as id, m.owner_name as name
            FROM vouch_edges ve
            JOIN merchants m ON m.merchant_id = ve.from_merchant_id
            WHERE ve.to_merchant_id=$1
        """, merchant_id)
        vouches_for = await conn.fetch("""
            SELECT ve.to_merchant_id as id, m.owner_name as name
            FROM vouch_edges ve
            JOIN merchants m ON m.merchant_id = ve.to_merchant_id
            WHERE ve.from_merchant_id=$1
        """, merchant_id)
        return {
            "merchant_id": merchant_id,
            "vouched_by":  [dict(r) for r in vouched_by],
            "vouches_for": [dict(r) for r in vouches_for],
        }


async def get_graph_data_for_d3() -> Dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        merchant_rows = await conn.fetch("""
            SELECT merchant_id, owner_name, business_type, segment, location
            FROM merchants ORDER BY merchant_id
        """)
        edge_rows = await conn.fetch(
            "SELECT from_merchant_id, to_merchant_id, edge_weight FROM vouch_edges"
        )
        fraud_rows = await conn.fetch("""
                                      
            SELECT merchant_id,
                   (full_data->'layer_1_social_graph'->'fraud_ring_risk'
                    ->>'is_fraud_ring_participant')::boolean as fraud_flag
            FROM merchants
        """)
        fraud_map = {r["merchant_id"]: r["fraud_flag"] for r in fraud_rows}
        nodes = [{
            "id": r["merchant_id"], "name": r["owner_name"],
            "business_type": r["business_type"], "segment": r["segment"],
            "location": r["location"], "fraud_flag": fraud_map.get(r["merchant_id"], False),
        } for r in merchant_rows]
        edges = [{
            "source": r["from_merchant_id"], "target": r["to_merchant_id"],
            "weight": float(r["edge_weight"]),
        } for r in edge_rows]
        return {"nodes": nodes, "edges": edges}