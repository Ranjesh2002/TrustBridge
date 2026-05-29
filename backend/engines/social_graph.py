import networkx as nx
from typing import Dict, List


def build_graph(merchants: List[Dict]) -> nx.DiGraph:
    G = nx.DiGraph()
    for m in merchants:
        G.add_node(
            m["merchant_id"],
            name=m["name"],
            business_type=m["business_type"],
            district=m["district"]
        )

    relationship_weights = {
        "supplier":        1.0,
        "peer_merchant":   0.8,
        "community_elder": 0.6,
        "family_member":   0.4
    }

    for m in merchants:
        for v in m.get("vouchers", []):
            weight = (
                relationship_weights.get(v["relationship"], 0.5)
                * (v["voucher_trust_score"] / 100)
                * min(v["months_known"] / 24, 1.0)
            )
            G.add_edge(
                v["voucher_id"],
                m["merchant_id"],
                weight=weight,
                relationship=v["relationship"],
                months_known=v["months_known"]
            )
    return G


def detect_fraud_rings(G: nx.DiGraph) -> List[List[str]]:
    undirected = G.to_undirected()
    cliques = list(nx.find_cliques(undirected))
    suspicious = []
    for clique in cliques:
        if len(clique) >= 3:
            clique_set = set(clique)
            external_edges = sum(
                1 for n in clique
                for neighbor in G.neighbors(n)
                if neighbor not in clique_set
            )
            if external_edges == 0:
                suspicious.append(clique)
    return suspicious


def compute_pagerank_scores(G: nx.DiGraph) -> Dict[str, float]:
    if len(G.nodes) == 0:
        return {}
    try:
        scores = nx.pagerank(G, weight="weight", alpha=0.85, max_iter=200)
    except nx.PowerIterationFailedConvergence:
        scores = {n: 1 / len(G.nodes) for n in G.nodes}
    return scores


def score_merchant_social(merchant_id: str, G: nx.DiGraph) -> Dict:
    fraud_rings = detect_fraud_rings(G)
    fraud_flag = any(merchant_id in ring for ring in fraud_rings)

    pagerank_scores = compute_pagerank_scores(G)
    pr_raw = pagerank_scores.get(merchant_id, 0.0)

    all_scores = list(pagerank_scores.values())
    if max(all_scores) > 0:
        pr_normalized = (pr_raw / max(all_scores)) * 100
    else:
        pr_normalized = 0

    in_edges = list(G.in_edges(merchant_id, data=True))
    voucher_count = len(in_edges)
    rel_types = set(d.get("relationship") for _, _, d in in_edges)
    diversity_bonus = min(len(rel_types) * 5, 15)

    raw_score = pr_normalized + diversity_bonus
    fraud_penalty = 0.4 if fraud_flag else 0.0
    final_score = round(min(raw_score * (1 - fraud_penalty), 100))

    explanation = (
        f"Vouched by {voucher_count} merchants "
        f"({'FRAUD FLAG — mutual ring detected' if fraud_flag else 'no fraud detected'}). "
        f"Relationship diversity: {len(rel_types)} type(s)."
    )

    return {
        "social_score": final_score,
        "fraud_flag": fraud_flag,
        "pagerank_raw": round(pr_raw, 6),
        "voucher_count": voucher_count,
        "relationship_diversity": len(rel_types),
        "explanation": explanation
    }
