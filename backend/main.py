import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Optional, List
import networkx as nx

from db import (
    init_db,
    get_all_merchants,
    get_all_merchants_full,
    get_merchant_full,
    save_trust_score,
    save_psychometric,
    get_score_history,
    get_vouch_neighbors,
    get_graph_data_for_d3,
)
from engines.social_graph import build_graph_from_edges, score_merchant_social
from engines.psychometric import run_psychometric_assessment, get_questions
from engines.behavioral import compute_behavioral_score
from engines.fusion import fuse_scores
from engines.inference import predict

# ── Startup ───────────────────────────────────────────────────────────────────

GRAPH: nx.DiGraph = nx.DiGraph()
MERCHANT_CACHE: Dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global GRAPH, MERCHANT_CACHE
    await init_db()

    # Load all merchants into in-memory cache for graph + scoring
    merchants = await get_all_merchants_full()
    MERCHANT_CACHE = {m["merchant_id"]: m for m in merchants}

    # Build graph from DB edges
    graph_data = await get_graph_data_for_d3()
    GRAPH = build_graph_from_edges(merchants, graph_data["edges"])
    print(f"✅ Graph: {GRAPH.number_of_nodes()} nodes, {GRAPH.number_of_edges()} edges")
    yield
    from db import close_pool

    await close_pool()


app = FastAPI(
    title="TrustBridge API",
    description="Alternative Trust Middleware for Unbanked Merchants — Nepal",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ── Pydantic models ───────────────────────────────────────────────────────────


class ScoreRequest(BaseModel):
    merchant_id: str
    psychometric_responses: Optional[Dict[str, str]] = None
    lang: Optional[str] = "ne"


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/")
def root():
    return {
        "name": "TrustBridge",
        "version": "2.0.0",
        "status": "running",
        "merchants_loaded": len(MERCHANT_CACHE),
        "graph_nodes": GRAPH.number_of_nodes(),
        "graph_edges": GRAPH.number_of_edges(),
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/merchants")
async def list_merchants():
    rows = await get_all_merchants()
    return [
        {
            "merchant_id": r["merchant_id"],
            "name": r["owner_name"],
            "legal_name": r["legal_name"],
            "district": r["district"] or r["location"],
            "region": r["region"],
            "business_type": r["business_type"],
            "segment": r["segment"],
            "months_active": r["months_active"],
            "digital_footprint": r["digital_footprint"],
            "esewa_registered": r["esewa_registered"],
            "khalti_registered": r["khalti_registered"],
            "risk_score": float(r["risk_score"]) if r["risk_score"] else None,
            "repayment_risk": r["repayment_risk"],
        }
        for r in rows
    ]


@app.get("/merchants/{merchant_id}")
async def get_merchant(merchant_id: str):
    m = await get_merchant_full(merchant_id)
    if not m:
        raise HTTPException(status_code=404, detail="Merchant not found")

    # New flat schema (TB-2026-XXXX)
    if "business_metadata" not in m:
        return {
            **m,
            "name": m.get("owner_name", ""),
            "district": m.get("district", ""),
            "region": m.get("region", ""),
            "business_type": m.get("business_type", ""),
            "months_active": m.get("months_active", 0),
            "digital_footprint": m.get("esewa_usage_rate", 0) > 0,
            "esewa_registered": m.get("esewa_usage_rate", 0) > 0,
            "khalti_registered": False,
        }

    # Old 3-layer schema (USR-M-XXX)
    meta = m["business_metadata"]
    return {
        **m,
        "name": meta["owner_name"],
        "district": meta["location"],
        "business_type": meta["business_type"],
        "months_active": meta["months_active"],
        "digital_footprint": meta.get("segment", "") == "Digital Native",
        "esewa_registered": meta.get("segment", "") == "Digital Native",
        "khalti_registered": False,
    }


@app.get("/psychometric/questions")
def psychometric_questions(merchant_id: str = None, lang: str = "ne"):
    return get_questions(lang=lang, seed=merchant_id)


@app.post("/score/{merchant_id}")
async def compute_full_score(merchant_id: str, body: ScoreRequest):
    merchant = MERCHANT_CACHE.get(merchant_id)
    if not merchant:
        merchant = await get_merchant_full(merchant_id)
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    merchant = normalise_merchant(merchant)

    # Layer 1: Social graph
    social_result = score_merchant_social(merchant_id, GRAPH, merchant)

    # Layer 2: Psychometric
    responses = body.psychometric_responses or {}
    if responses:
        psychometric_result = run_psychometric_assessment(
            merchant_id,
            merchant.get("business_metadata", {}).get("owner_name")
            or merchant.get("owner_name", ""),
            responses,
            lang=body.lang or "ne",
        )
    else:
        psychometric_result = {
            "psychometric_score": 0,
            "credit_personality": "Not assessed",
            "credit_personality_ne": "मूल्याङ्कन गरिएको छैन",
            "insight": "",
            "red_flags": "none",
            "strengths": "",
            "xp_earned": 0,
            "badges_unlocked": [],
        }

    # Layer 3: Behavioral
    behavioral_result = compute_behavioral_score(merchant)

    # Fusion
    final = fuse_scores(merchant, social_result, psychometric_result, behavioral_result)

    # Attach gamification
    final["xp_earned"] = psychometric_result.get("xp_earned", 0)
    final["badges_unlocked"] = psychometric_result.get("badges_unlocked", [])
    final["hallucination_corrections"] = psychometric_result.get(
        "hallucination_corrections", []
    )
    final["deterministic_baseline"] = psychometric_result.get(
        "deterministic_baseline", {}
    )

    # Persist to PostgreSQL
    await save_trust_score(merchant_id, final)
    if responses:
        await save_psychometric(merchant_id, responses, psychometric_result)

    # Attach score history
    history = await get_score_history(merchant_id)
    final["score_history"] = [
        {
            "score": h["final_score"],
            "tier": h["lending_tier"],
            "date": h["scored_at"].isoformat() if h.get("scored_at") else None,
        }
        for h in history
    ]

    return final


@app.get("/score/{merchant_id}/history")
async def score_history(merchant_id: str):
    history = await get_score_history(merchant_id, limit=10)
    return {
        "merchant_id": merchant_id,
        "history": [
            {
                "final_score": h["final_score"],
                "confidence": float(h["confidence"]) if h["confidence"] else None,
                "lending_tier": h["lending_tier"],
                "fraud_flag": h["fraud_flag"],
                "social_score": h["social_score"],
                "psychometric_score": h["psychometric_score"],
                "behavioral_score": h["behavioral_score"],
                "scored_at": h["scored_at"].isoformat() if h.get("scored_at") else None,
            }
            for h in history
        ],
    }


@app.get("/score/{merchant_id}/ml")
def ml_score(merchant_id: str):
    merchant = MERCHANT_CACHE.get(merchant_id)
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    merchant = normalise_merchant(merchant)
    try:
        return predict(merchant)
    except Exception as e:
        return {
            "repayment_risk": "unknown",
            "confidence": 0,
            "anomaly_flag": False,
            "probabilities": {},
            "error": str(e),
        }


@app.get("/graph/stats")
def graph_stats():
    return {
        "nodes": GRAPH.number_of_nodes(),
        "edges": GRAPH.number_of_edges(),
        "density": round(nx.density(GRAPH), 4),
        "avg_clustering": round(nx.average_clustering(GRAPH.to_undirected()), 4),
    }


@app.get("/graph/neighbors/{merchant_id}")
async def get_graph_neighbors(merchant_id: str):
    data = await get_vouch_neighbors(merchant_id)
    return data


@app.get("/graph/d3")
async def graph_d3():
    """Full graph data for D3 force visualization."""
    return await get_graph_data_for_d3()


@app.post("/ml-score")
def ml_score_merchant(merchant: dict):
    result = predict(merchant)
    return result


@app.get("/ml-score/{merchant_id}")
def ml_score_by_id(merchant_id: str):
    merchant = MERCHANT_CACHE.get(merchant_id)
    if not merchant:
        raise HTTPException(404, "Merchant not found")
    merchant = normalise_merchant(merchant)
    return predict(merchant)


@app.get("/score/{merchant_id}/latest")
async def get_latest_score(merchant_id: str):
    history = await get_score_history(merchant_id, limit=1)
    if not history:
        return None
    result = history[0].get("full_result")
    if result is None:
        return None
    if isinstance(result, str):
        import json

        return json.loads(result)
    return dict(result)


@app.get("/merchants/{merchant_id}/transactions")
async def merchant_transactions(
    merchant_id: str,
    limit: int = 100,
    txn_type: str = None,
    month: int = None,
    year: int = None,
):
    """All transactions for a merchant, filterable by type/month/year."""
    from db import get_merchant_transactions

    merchant = MERCHANT_CACHE.get(merchant_id)
    if not merchant:
        raise HTTPException(404, "Merchant not found")
    txns = await get_merchant_transactions(merchant_id, limit, txn_type, month, year)
    # Serialize dates to string
    for t in txns:
        if hasattr(t.get("txn_date"), "isoformat"):
            t["txn_date"] = t["txn_date"].isoformat()
        if hasattr(t.get("created_at"), "isoformat"):
            t["created_at"] = t["created_at"].isoformat()
    return txns


@app.get("/merchants/{merchant_id}/monthly-summary")
async def merchant_monthly_summary(merchant_id: str):
    """Monthly credits/debits/net for charts."""
    from db import get_merchant_monthly_summary

    merchant = MERCHANT_CACHE.get(merchant_id)
    if not merchant:
        raise HTTPException(404, "Merchant not found")
    return await get_merchant_monthly_summary(merchant_id)


@app.get("/merchants/{merchant_id}/transaction-stats")
async def merchant_transaction_stats(merchant_id: str):
    """Aggregate stats: total txns, credits, debits, payment delay avg."""
    from db import get_transaction_stats

    merchant = MERCHANT_CACHE.get(merchant_id)
    if not merchant:
        raise HTTPException(404, "Merchant not found")
    stats = await get_transaction_stats(merchant_id)
    # Serialize decimals
    return {k: float(v) if v is not None else None for k, v in stats.items()}


def normalise_merchant(m: dict) -> dict:
    """
    Converts any merchant schema (flat TB-2026 or nested USR-M) into
    a unified shape that all scoring engines expect.
    Returns the merchant with business_metadata and layer_3_behavioral
    always present, so no engine ever hits a KeyError.
    """
    # Already has business_metadata — old 3-layer schema, nothing to do
    if "business_metadata" in m:
        return m

    # ── Flat TB-2026 schema → build the nested keys engines expect ───────────

    months_active = m.get("months_active", 12)
    data_maturity = round(min(0.60 + (months_active / 12) * 0.40, 1.00), 2)

    # Build business_metadata
    m["business_metadata"] = {
        "owner_name": m.get("owner_name", ""),
        "legal_name": m.get("legal_name", ""),
        "location": m.get("district", m.get("location", "")),
        "business_type": m.get("business_type", ""),
        "segment": m.get("segment", "Cash Dominant"),
        "months_active": months_active,
        "data_maturity_discount_applied": data_maturity,
        # Extra flat fields forwarded so fusion can read them if needed
        "region": m.get("region", ""),
        "owner_age": m.get("owner_age", 0),
        "household_size": m.get("household_size", 0),
    }

    # Build layer_1_social_graph (no real graph data in flat schema — use defaults)
    m["layer_1_social_graph"] = {
        "node_type": "MERCHANT",
        "pagerank_score": 0.015,
        "vouch_metrics": {
            "vouches_given": 0,
            "vouches_received": 0,
            "trusted_anchor_vouched": False,
            "new_vouches_last_30_days": 0,
            "vouch_edge_weight": 1.0,
            "vouch_age_months": 0,
        },
        "network_relationships": {
            "repeat_customers_count": 0,
            "total_unique_customers_30d": 0,
            "avg_visits_per_customer_month": 0,
            "longest_relationship_months": 0,
            "supplier_buyer_loop_detected": False,
            "temporal_clustering_flag": False,
            "calculated_customer_loyalty_score": round(
                min(
                    m.get("qr_success_rate", 0.5) * 0.6
                    + (1 - m.get("inactive_days", 30) / 90) * 0.4,
                    1.0,
                ),
                3,
            ),
        },
        "fraud_ring_risk": {
            "star_fraud_anchor_suspicious": False,
            "thin_file_collusion": False,
            "is_fraud_ring_participant": False,
            "fraud_penalty_multiplier": 1.0,
            "temporal_vouching_burst": False,
        },
    }

    # Build layer_2_psychometric (empty until assessment done)
    if "layer_2_psychometric" not in m:
        m["layer_2_psychometric"] = {
            "telemetry": {
                "avg_response_time_seconds": 0,
                "response_time_signal": "neutral",
                "multi_session_score_drift_2w": 0,
                "consistency_trap_failed": False,
            },
            "deterministic_base_scores": {
                "loss_aversion_asymmetry": 50,
                "in_group_trust_radius": 50,
                "time_discounting": 50,
                "locus_of_control": 50,
            },
            "llm_adjusted_scores": {
                "loss_aversion_asymmetry": 50,
                "in_group_trust_radius": 50,
                "time_discounting": 50,
                "locus_of_control": 50,
            },
            "llm_explanation": "Not yet assessed.",
        }

    # Build layer_3_behavioral from flat fields
    credits = m.get("monthly_credits", [])
    last3 = credits[-3:] if len(credits) >= 3 else credits
    # Estimate debits as (1 - utility_score) * credits as a rough proxy
    utility = m.get("utility_score", 0.6)
    debits3 = [round(c * (1 - utility * 0.3)) for c in last3]
    net3 = [last3[i] - debits3[i] for i in range(len(last3))]
    cov3 = [round(last3[i] / max(debits3[i], 1), 3) for i in range(len(last3))]
    neg_months = sum(1 for n in net3 if n < 0)

    nea_ontime = m.get("nea_on_time", [])
    nea_streak = sum(nea_ontime[-6:]) if nea_ontime else 0

    m["layer_3_behavioral"] = {
        "current_regime": (
            "stressed"
            if m.get("nea_arrears_months", 0) >= 6
            else "recovery"
            if m.get("revenue_trend", 0) > 0
            else "stable"
        ),
        "historical_regime_transitions": ["stable"],
        "seasonal_business_flag": m.get("seasonal_migration", 0) == 1,
        "financial_telemetry_3mo": {
            "monthly_credits_npr": last3,
            "monthly_debits_npr": debits3,
            "net_cash_flow_npr": net3,
            "coverage_ratio": cov3 if cov3 else [1.0, 1.0, 1.0],
            "consecutive_negative_months": neg_months,
            "festival_spike_normalized": True,
        },
        "proxy_features": {
            "nea_bill_consecutive_on_time_months": nea_streak,
            "water_bill_consecutive_on_time_months": round(
                m.get("water_payment_rate", 0.5) * 6
            )
            if m.get("has_water_bill", 0)
            else 0,
            "airtime_topup_regularity_index": m.get("airtime_regularity", 0.5),
            "days_to_payment_variance": round(
                m.get("khata_avg_days_to_repay", 10) * 0.3, 1
            )
            if m.get("khata_avg_days_to_repay", -1) >= 0
            else 5.0,
            "payment_delays_raw_3mo": [],
            "cross_utility_correlation_stress": (
                m.get("nea_arrears_months", 0) >= 5 and m.get("water_arrears", 0) >= 3
            ),
        },
    }

    return m
