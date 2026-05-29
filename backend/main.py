import json
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Optional
import networkx as nx

from engines.social_graph import build_graph, score_merchant_social
from engines.psychometric import run_psychometric_assessment, get_questions
from engines.behavioral import compute_behavioral_score
from engines.fusion import fuse_scores

app = FastAPI(
    title="TrustBridge API",
    description="Alternative Trust Middleware for Unbanked Merchants — Nepal",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Load mock data at startup
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "mock_merchants.json")

with open(DATA_PATH, "r", encoding="utf-8") as f:
    MERCHANTS = json.load(f)

MERCHANT_MAP = {m["merchant_id"]: m for m in MERCHANTS}
GRAPH = build_graph(MERCHANTS)


# ── Pydantic models ──────────────────────────────────────────────────────────

class PsychometricRequest(BaseModel):
    merchant_id: str
    responses: Dict[str, str]

class ScoreRequest(BaseModel):
    merchant_id: str
    psychometric_responses: Optional[Dict[str, str]] = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "name": "TrustBridge",
        "version": "1.0.0",
        "status": "running",
        "merchants_loaded": len(MERCHANTS)
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/merchants")
def list_merchants():
    return [
        {
            "merchant_id": m["merchant_id"],
            "name": m["name"],
            "district": m["district"],
            "business_type": m["business_type"],
            "digital_footprint": m["digital_footprint"],
            "years_in_business": m["years_in_business"],
            "esewa_registered": m.get("esewa_registered", False),
            "khalti_registered": m.get("khalti_registered", False),
        }
        for m in MERCHANTS
    ]

@app.get("/merchants/{merchant_id}")
def get_merchant(merchant_id: str):
    m = MERCHANT_MAP.get(merchant_id)
    if not m:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return m

@app.get("/psychometric/questions")
def psychometric_questions():
    return get_questions()

@app.post("/score/{merchant_id}")
def compute_full_score(merchant_id: str, body: ScoreRequest):
    merchant = MERCHANT_MAP.get(merchant_id)
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    # Layer 1: Social graph
    social_result = score_merchant_social(merchant_id, GRAPH)

    # Layer 2: Psychometric
    responses = body.psychometric_responses or {}
    if responses:
        psychometric_result = run_psychometric_assessment(merchant_id, merchant["name"], responses)
    else:
        psychometric_result = {"psychometric_score": 0, "credit_personality": "Not assessed", "insight": "", "red_flags": "N/A", "strengths": ""}

    # Layer 3: Behavioral
    behavioral_result = compute_behavioral_score(merchant)

    # Fusion
    return fuse_scores(merchant, social_result, psychometric_result, behavioral_result)

@app.get("/graph/stats")
def graph_stats():
    return {
        "nodes": GRAPH.number_of_nodes(),
        "edges": GRAPH.number_of_edges(),
        "density": round(nx.density(GRAPH), 4),
        "avg_clustering": round(nx.average_clustering(GRAPH.to_undirected()), 4)
    }

@app.get("/graph/neighbors/{merchant_id}")
def get_graph_neighbors(merchant_id: str):
    if merchant_id not in GRAPH:
        raise HTTPException(status_code=404, detail="Merchant not in graph")
    vouchers = list(GRAPH.predecessors(merchant_id))
    vouched_for = list(GRAPH.successors(merchant_id))
    return {
        "merchant_id": merchant_id,
        "vouched_by": [
            {"id": v, "name": MERCHANT_MAP.get(v, {}).get("name", v)}
            for v in vouchers
        ],
        "vouches_for": [
            {"id": v, "name": MERCHANT_MAP.get(v, {}).get("name", v)}
            for v in vouched_for
        ]
    }
