"""
TrustBridge — Realistic Seed Script
Generates 14 users (5 merchants, 3 suppliers, 3 vendors, 3 customers)
with 6 months of interrelated transactions (100+ per merchant per month).
Writes directly to PostgreSQL.

Run: python seed_realistic.py
Requires: pip install asyncpg python-dotenv
"""

import asyncio
import asyncpg
import os
import json
import random
import math
from datetime import date, timedelta
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://trustbridge:trustbridge@localhost:5432/trustbridge"
)

# ─────────────────────────────────────────────────────────────────────────────
# CAST OF CHARACTERS
# 5 merchants, 3 suppliers, 3 vendors, 3 customers = 14 total
# ─────────────────────────────────────────────────────────────────────────────

USERS = [
    # ── Merchants ──────────────────────────────────────────────────────────────
    {
        "user_id": "USR-M-001",
        "full_name": "Ramesh Shrestha",
        "role": "merchant",
        "phone": "9841001001",
        "location": "Asan, Kathmandu",
        "business_name": "Shrestha Kirana Pasala",
        "business_type": "Grocery & Daily Essentials",
        "esewa_id": "9841001001",
        "khalti_id": None,
        "joined_date": date(2023, 1, 15),
        # merchant profile extras
        "segment": "Digital Native",
        "months_active": 24,
        "base_daily_revenue": 8000,      # NPR per day, healthy kirana
        "regime": "stable",
    },
    {
        "user_id": "USR-M-002",
        "full_name": "Sita Gurung",
        "role": "merchant",
        "phone": "9841002002",
        "location": "Mahendrapool, Pokhara",
        "business_name": "Gurung Chiya Pasal",
        "business_type": "Tea & Local Eatery",
        "esewa_id": "9841002002",
        "khalti_id": "9841002002",
        "joined_date": date(2023, 3, 10),
        "segment": "Digital Native",
        "months_active": 22,
        "base_daily_revenue": 3500,
        "regime": "stable",
    },
    {
        "user_id": "USR-M-003",
        "full_name": "Bikram Thapa",
        "role": "merchant",
        "phone": "9851003003",
        "location": "Mahabouddha, Kathmandu",
        "business_name": "Thapa Electronics",
        "business_type": "Electronics & Wholesale",
        "esewa_id": None,
        "khalti_id": None,
        "joined_date": date(2024, 6, 1),
        "segment": "Cash Dominant",
        "months_active": 7,
        "base_daily_revenue": 15000,
        "regime": "stressed",             # new + stressed = interesting for scoring
    },
    {
        "user_id": "USR-M-004",
        "full_name": "Anjali Maharjan",
        "role": "merchant",
        "phone": "9801004004",
        "location": "Lalitpur",
        "business_name": "Maharjan Tarkari Pasala",
        "business_type": "Vegetable & Seasonal Produce",
        "esewa_id": "9801004004",
        "khalti_id": None,
        "joined_date": date(2022, 8, 20),
        "segment": "Cash Dominant",
        "months_active": 29,
        "base_daily_revenue": 4500,
        "regime": "recovery",
    },
    {
        "user_id": "USR-M-005",
        "full_name": "Deepak Tamang",
        "role": "merchant",
        "phone": "9861005005",
        "location": "Bhaktapur",
        "business_name": "Tamang Momo Center",
        "business_type": "Restaurant & Hospitality",
        "esewa_id": "9861005005",
        "khalti_id": "9861005005",
        "joined_date": date(2021, 11, 5),
        "segment": "Digital Native",
        "months_active": 38,
        "base_daily_revenue": 6000,
        "regime": "stable",
    },

    # ── Suppliers ──────────────────────────────────────────────────────────────
    {
        "user_id": "USR-S-001",
        "full_name": "Nepal Wholesale Traders",
        "role": "supplier",
        "phone": "9811010010",
        "location": "Kalimati, Kathmandu",
        "business_name": "Nepal Wholesale Traders",
        "business_type": "Wholesale Grocery",
        "esewa_id": None,
        "khalti_id": None,
        "joined_date": date(2020, 1, 1),
    },
    {
        "user_id": "USR-S-002",
        "full_name": "Himalayan Electronics Dist.",
        "role": "supplier",
        "phone": "9811020020",
        "location": "New Road, Kathmandu",
        "business_name": "Himalayan Electronics Distributors",
        "business_type": "Electronics Wholesale",
        "esewa_id": None,
        "khalti_id": None,
        "joined_date": date(2019, 5, 10),
    },
    {
        "user_id": "USR-S-003",
        "full_name": "Pokhara Agro Suppliers",
        "role": "supplier",
        "phone": "9811030030",
        "location": "Pokhara",
        "business_name": "Pokhara Agro Suppliers",
        "business_type": "Agribusiness",
        "esewa_id": None,
        "khalti_id": None,
        "joined_date": date(2021, 3, 15),
    },

    # ── Vendors (services: internet, repairs, packaging) ──────────────────────
    {
        "user_id": "USR-V-001",
        "full_name": "Worldlink ISP",
        "role": "vendor",
        "phone": "01-5970000",
        "location": "Kathmandu",
        "business_name": "Worldlink Communications",
        "business_type": "Internet Service",
        "esewa_id": None,
        "khalti_id": None,
        "joined_date": date(2018, 1, 1),
    },
    {
        "user_id": "USR-V-002",
        "full_name": "Sharma Packaging",
        "role": "vendor",
        "phone": "9841040040",
        "location": "Patan, Lalitpur",
        "business_name": "Sharma Packaging Solutions",
        "business_type": "Packaging & Supplies",
        "esewa_id": None,
        "khalti_id": None,
        "joined_date": date(2020, 6, 1),
    },
    {
        "user_id": "USR-V-003",
        "full_name": "Nepal Electricity Authority",
        "role": "vendor",
        "phone": "1155",
        "location": "Kathmandu",
        "business_name": "NEA",
        "business_type": "Electricity Provider",
        "esewa_id": None,
        "khalti_id": None,
        "joined_date": date(2000, 1, 1),
    },

    # ── Customers ──────────────────────────────────────────────────────────────
    {
        "user_id": "USR-C-001",
        "full_name": "Priya Adhikari",
        "role": "customer",
        "phone": "9841050050",
        "location": "Baneshwor, Kathmandu",
        "business_name": None,
        "business_type": None,
        "esewa_id": "9841050050",
        "khalti_id": None,
        "joined_date": date(2023, 2, 1),
    },
    {
        "user_id": "USR-C-002",
        "full_name": "Rohan Basnet",
        "role": "customer",
        "phone": "9851060060",
        "location": "Lalitpur",
        "business_name": None,
        "business_type": None,
        "esewa_id": None,
        "khalti_id": "9851060060",
        "joined_date": date(2022, 7, 15),
    },
    {
        "user_id": "USR-C-003",
        "full_name": "Kamala Rai",
        "role": "customer",
        "phone": "9841070070",
        "location": "Bhaktapur",
        "business_name": None,
        "business_type": None,
        "esewa_id": "9841070070",
        "khalti_id": None,
        "joined_date": date(2023, 9, 1),
    },
]

MERCHANTS = [u for u in USERS if u["role"] == "merchant"]
SUPPLIERS = [u for u in USERS if u["role"] == "supplier"]
VENDORS   = [u for u in USERS if u["role"] == "vendor"]
CUSTOMERS = [u for u in USERS if u["role"] == "customer"]

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def clamp(v, lo, hi): return max(lo, min(hi, v))

def rand_date_in_month(year, month):
    """Random date within a calendar month."""
    import calendar
    last = calendar.monthrange(year, month)[1]
    return date(year, month, random.randint(1, last))

def festival_multiplier(month):
    """Dashain=Oct(10), Tihar=Nov(11), Teej=Aug(8)."""
    return {10: random.uniform(2.0, 2.8), 11: random.uniform(1.8, 2.4),
            8: random.uniform(1.3, 1.6)}.get(month, 1.0)

def payment_method_for(merchant):
    if merchant.get("esewa_id") and merchant.get("khalti_id"):
        return random.choices(["cash","esewa","khalti"], weights=[0.4,0.35,0.25])[0]
    elif merchant.get("esewa_id"):
        return random.choices(["cash","esewa"], weights=[0.5,0.5])[0]
    return "cash"

# Supplier affinity: which supplier each merchant buys from
MERCHANT_SUPPLIER_MAP = {
    "USR-M-001": "USR-S-001",   # Kirana → Wholesale grocery
    "USR-M-002": "USR-S-003",   # Tea → Agro
    "USR-M-003": "USR-S-002",   # Electronics → Electronics dist
    "USR-M-004": "USR-S-003",   # Vegetable → Agro
    "USR-M-005": "USR-S-001",   # Momo → Wholesale grocery
}
# Which vendors each merchant uses
MERCHANT_VENDOR_MAP = {
    "USR-M-001": ["USR-V-003", "USR-V-001"],   # NEA + internet
    "USR-M-002": ["USR-V-003"],                 # NEA only
    "USR-M-003": ["USR-V-003", "USR-V-001"],
    "USR-M-004": ["USR-V-003", "USR-V-002"],   # NEA + packaging
    "USR-M-005": ["USR-V-003", "USR-V-002"],   # NEA + packaging
}
# Which customers visit each merchant regularly
MERCHANT_CUSTOMER_MAP = {
    "USR-M-001": ["USR-C-001", "USR-C-002", "USR-C-003"],
    "USR-M-002": ["USR-C-001", "USR-C-003"],
    "USR-M-003": ["USR-C-002"],
    "USR-M-004": ["USR-C-001", "USR-C-002", "USR-C-003"],
    "USR-M-005": ["USR-C-001", "USR-C-002", "USR-C-003"],
}

# ─────────────────────────────────────────────────────────────────────────────
# TRANSACTION GENERATORS
# ─────────────────────────────────────────────────────────────────────────────

txn_counter = 0

def next_txn_id():
    global txn_counter
    txn_counter += 1
    return f"TXN-2025-{txn_counter:06d}"

def generate_month_transactions(merchant, year, month):
    """
    Generate 100+ interrelated transactions for one merchant for one month.
    Returns list of txn dicts.
    """
    txns = []
    mid  = merchant["user_id"]
    supplier_id = MERCHANT_SUPPLIER_MAP[mid]
    vendor_ids  = MERCHANT_VENDOR_MAP[mid]
    customer_ids = MERCHANT_CUSTOMER_MAP[mid]

    regime = merchant["regime"]
    base   = merchant["base_daily_revenue"]
    fm     = festival_multiplier(month)

    # Revenue modifier by regime
    if regime == "stable":
        rev_mod = fm * random.uniform(0.88, 1.12)
        exp_mod = random.uniform(0.72, 0.88)
    elif regime == "stressed":
        rev_mod = fm * random.uniform(0.55, 0.78)
        exp_mod = random.uniform(0.95, 1.15)
    else:  # recovery
        rev_mod = fm * random.uniform(0.78, 0.96)
        exp_mod = random.uniform(0.84, 0.93)

    import calendar
    days_in_month = calendar.monthrange(year, month)[1]

    # ── 1. Daily sales to customers (~4-6 per customer per day active) ────────
    # Each merchant sells every day; customers visit 3-5x per week
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        # Skip some days randomly (closed 2-3 days/month)
        if random.random() < 0.08:
            continue
        daily_target = base * rev_mod
        sales_so_far = 0
        for cust_id in customer_ids:
            # Each customer visits ~70% of open days
            if random.random() > 0.70:
                continue
            # 2-5 transactions per customer visit (different items)
            n_items = random.randint(2, 5)
            for _ in range(n_items):
                amount = round(random.uniform(50, min(1500, daily_target * 0.08)), 2)
                method = payment_method_for(merchant)
                txns.append({
                    "txn_id": next_txn_id(),
                    "from_user_id": cust_id,
                    "to_user_id": mid,
                    "amount_npr": amount,
                    "txn_type": "sale",
                    "status": "completed",
                    "payment_method": method,
                    "description": f"Sale at {merchant['business_name']}",
                    "txn_date": d,
                    "days_to_pay": 0,
                })
                sales_so_far += amount

    # ── 2. Purchases from supplier (3-5x per month, bulk restocking) ──────────
    total_revenue_est = base * rev_mod * days_in_month
    monthly_purchase_budget = total_revenue_est * exp_mod * 0.65  # ~65% of expenses
    n_purchases = random.randint(3, 5)
    per_purchase = monthly_purchase_budget / n_purchases

    for i in range(n_purchases):
        d = rand_date_in_month(year, month)
        # Stressed merchants pay late
        delay = random.randint(5, 14) if regime == "stressed" else random.randint(0, 3)
        amount = round(per_purchase * random.uniform(0.8, 1.2), 2)
        txns.append({
            "txn_id": next_txn_id(),
            "from_user_id": mid,
            "to_user_id": supplier_id,
            "amount_npr": amount,
            "txn_type": "purchase",
            "status": "completed",
            "payment_method": "cash",
            "description": f"Stock purchase from {supplier_id}",
            "txn_date": d,
            "days_to_pay": delay,
        })

    # ── 3. NEA electricity bill (once per month) ──────────────────────────────
    nea_id = "USR-V-003"
    nea_amount = round(random.uniform(800, 3500), 2)
    nea_day = random.randint(1, 28)
    nea_delay = 0
    if regime == "stressed":
        nea_delay = random.randint(5, 20)
    elif regime == "recovery":
        nea_delay = random.randint(0, 5)

    txns.append({
        "txn_id": next_txn_id(),
        "from_user_id": mid,
        "to_user_id": nea_id,
        "amount_npr": nea_amount,
        "txn_type": "utility_nea",
        "status": "completed" if nea_delay < 10 else random.choice(["completed","pending"]),
        "payment_method": "esewa" if merchant.get("esewa_id") else "cash",
        "description": "Monthly NEA electricity bill",
        "txn_date": date(year, month, nea_day),
        "days_to_pay": nea_delay,
    })

    # ── 4. Internet bill (monthly, if applicable) ─────────────────────────────
    if "USR-V-001" in vendor_ids:
        internet_amount = round(random.uniform(1200, 2500), 2)
        txns.append({
            "txn_id": next_txn_id(),
            "from_user_id": mid,
            "to_user_id": "USR-V-001",
            "amount_npr": internet_amount,
            "txn_type": "utility_internet",
            "status": "completed",
            "payment_method": "esewa" if merchant.get("esewa_id") else "cash",
            "description": "Monthly internet bill",
            "txn_date": date(year, month, random.randint(1, 10)),
            "days_to_pay": 0,
        })

    # ── 5. Packaging / vendor services (2-4x per month) ──────────────────────
    if "USR-V-002" in vendor_ids:
        for _ in range(random.randint(2, 4)):
            txns.append({
                "txn_id": next_txn_id(),
                "from_user_id": mid,
                "to_user_id": "USR-V-002",
                "amount_npr": round(random.uniform(300, 1200), 2),
                "txn_type": "vendor_service",
                "status": "completed",
                "payment_method": "cash",
                "description": "Packaging materials",
                "txn_date": rand_date_in_month(year, month),
                "days_to_pay": 0,
            })

    # ── 6. Airtime top-ups (2-6x per month, regularity signals credit) ────────
    n_topups = random.randint(2, 6) if regime != "stressed" else random.randint(0, 2)
    for _ in range(n_topups):
        txns.append({
            "txn_id": next_txn_id(),
            "from_user_id": mid,
            "to_user_id": mid,           # self-topup
            "amount_npr": random.choice([100, 200, 300, 500]),
            "txn_type": "airtime_topup",
            "status": "completed",
            "payment_method": "esewa" if merchant.get("esewa_id") else "cash",
            "description": "Mobile airtime top-up",
            "txn_date": rand_date_in_month(year, month),
            "days_to_pay": 0,
        })

    # ── 7. Peer transfers between merchants (social graph signal) ─────────────
    # Merchants lend/borrow small amounts from each other occasionally
    other_merchants = [m for m in MERCHANTS if m["user_id"] != mid]
    if random.random() < 0.35:   # ~35% chance any given month
        peer = random.choice(other_merchants)
        direction = random.choice(["send", "receive"])
        amt = round(random.uniform(500, 5000), 2)
        txns.append({
            "txn_id": next_txn_id(),
            "from_user_id": mid if direction == "send" else peer["user_id"],
            "to_user_id":   peer["user_id"] if direction == "send" else mid,
            "amount_npr": amt,
            "txn_type": "transfer",
            "status": "completed",
            "payment_method": "esewa" if merchant.get("esewa_id") else "cash",
            "description": "Merchant peer transfer",
            "txn_date": rand_date_in_month(year, month),
            "days_to_pay": 0,
        })

    # ── 8. Refunds (occasional, ~2% of sales) ────────────────────────────────
    if random.random() < 0.40:   # 40% chance of at least one refund per month
        cust = random.choice(customer_ids)
        txns.append({
            "txn_id": next_txn_id(),
            "from_user_id": mid,
            "to_user_id": cust,
            "amount_npr": round(random.uniform(50, 500), 2),
            "txn_type": "refund",
            "status": "completed",
            "payment_method": "cash",
            "description": "Customer refund",
            "txn_date": rand_date_in_month(year, month),
            "days_to_pay": 0,
        })

    return txns


# ─────────────────────────────────────────────────────────────────────────────
# MERCHANT FULL_DATA (3-layer profile derived from transactions)
# ─────────────────────────────────────────────────────────────────────────────

def derive_merchant_full_data(merchant, all_txns_for_merchant):
    """Build the 3-layer JSON from actual transaction history."""
    from collections import defaultdict

    mid = merchant["user_id"]

    # Group by month
    monthly = defaultdict(lambda: {"credits": 0, "debits": 0, "txns": []})
    for t in all_txns_for_merchant:
        m_key = (t["txn_date"].year, t["txn_date"].month)
        if t["to_user_id"] == mid:
            monthly[m_key]["credits"] += float(t["amount_npr"])
        if t["from_user_id"] == mid:
            monthly[m_key]["debits"] += float(t["amount_npr"])
        monthly[m_key]["txns"].append(t)

    months_sorted = sorted(monthly.keys())[-3:]   # last 3 months for telemetry
    credits_3mo, debits_3mo, net_3mo, coverage_3mo = [], [], [], []
    for mk in months_sorted:
        c = monthly[mk]["credits"]
        d = monthly[mk]["debits"]
        credits_3mo.append(int(c))
        debits_3mo.append(int(d))
        net_3mo.append(int(c - d))
        coverage_3mo.append(round(c / max(d, 1), 3))

    # NEA streak: count months where NEA was paid on time (days_to_pay < 5)
    nea_txns = [t for t in all_txns_for_merchant
                if t["txn_type"] == "utility_nea" and t["from_user_id"] == mid]
    nea_streak = sum(1 for t in nea_txns if t["days_to_pay"] < 5)

    # Airtime regularity: months with at least 1 topup / total months
    topup_months = set(
        (t["txn_date"].year, t["txn_date"].month)
        for t in all_txns_for_merchant
        if t["txn_type"] == "airtime_topup"
    )
    topup_regularity = round(len(topup_months) / 6, 2)

    # Payment variance
    delays = [t["days_to_pay"] for t in all_txns_for_merchant
              if t["from_user_id"] == mid and t["days_to_pay"] >= 0]
    if len(delays) > 1:
        mean = sum(delays) / len(delays)
        var  = sum((x - mean)**2 for x in delays) / len(delays)
        payment_variance = round(math.sqrt(var), 2)
    else:
        payment_variance = 0.0

    # Unique customers
    customers = set(t["from_user_id"] for t in all_txns_for_merchant
                    if t["txn_type"] == "sale")
    repeat_customers = len(customers)

    # Consecutive negative months
    neg = 0
    max_neg = 0
    for nf in net_3mo:
        if nf < 0:
            neg += 1
            max_neg = max(max_neg, neg)
        else:
            neg = 0

    months_active = merchant["months_active"]
    data_maturity = round(clamp(0.60 + (months_active / 12) * 0.40, 0.60, 1.00), 2)
    regime        = merchant["regime"]

    utility_stress = (nea_streak < 2)
    cross_utility  = utility_stress and (nea_streak < 2)

    pagerank       = round(random.uniform(0.015, 0.04), 4)
    loyalty_score  = round(
        (repeat_customers / max(len(MERCHANT_CUSTOMER_MAP[mid]) * 20, 1)) * 0.5 +
        min(topup_regularity, 1.0) * 0.3 +
        min(months_active / 24, 1.0) * 0.2,
        3
    )

    return {
        "merchant_id": mid,
        "business_metadata": {
            "legal_name":    merchant["business_name"],
            "owner_name":    merchant["full_name"],
            "location":      merchant["location"],
            "business_type": merchant["business_type"],
            "months_active": months_active,
            "segment":       merchant["segment"],
            "data_maturity_discount_applied": data_maturity,
        },
        "layer_1_social_graph": {
            "node_type": "MERCHANT",
            "pagerank_score": pagerank,
            "vouch_metrics": {
                "vouches_given":            random.randint(1, 4),
                "vouches_received":         random.randint(1, 6),
                "trusted_anchor_vouched":   pagerank > 0.025,
                "new_vouches_last_30_days": random.randint(0, 2),
                "vouch_edge_weight":        round(random.uniform(0.7, 1.0), 2),
                "vouch_age_months":         min(months_active, random.randint(3, 18)),
            },
            "network_relationships": {
                "repeat_customers_count":        repeat_customers,
                "total_unique_customers_30d":    len(customers),
                "avg_visits_per_customer_month": round(random.uniform(2.0, 5.0), 1),
                "longest_relationship_months":   min(months_active - 1, random.randint(3, 24)),
                "supplier_buyer_loop_detected":  False,
                "temporal_clustering_flag":      False,
                "calculated_customer_loyalty_score": loyalty_score,
            },
            "fraud_ring_risk": {
                "star_fraud_anchor_suspicious": False,
                "thin_file_collusion":          False,
                "is_fraud_ring_participant":    False,
                "fraud_penalty_multiplier":     1.0,
                "temporal_vouching_burst":      False,
            },
        },
        "layer_2_psychometric": {
            "telemetry": {
                "avg_response_time_seconds":    round(random.uniform(2.5, 7.0), 1),
                "response_time_signal":         "neutral",
                "multi_session_score_drift_2w": round(random.uniform(1.5, 6.0), 1),
                "consistency_trap_failed":      False,
            },
            "deterministic_base_scores": {
                "loss_aversion_asymmetry": random.randint(55, 85),
                "in_group_trust_radius":   random.randint(50, 80),
                "time_discounting":        random.randint(50, 80),
                "locus_of_control":        random.randint(55, 85),
            },
            "llm_adjusted_scores": {
                "loss_aversion_asymmetry": random.randint(55, 85),
                "in_group_trust_radius":   random.randint(50, 80),
                "time_discounting":        random.randint(50, 80),
                "locus_of_control":        random.randint(55, 85),
            },
            "llm_explanation": "Derived from 6-month transaction history.",
        },
        "layer_3_behavioral": {
            "current_regime":                regime,
            "historical_regime_transitions": ["stable", regime],
            "seasonal_business_flag":        merchant["business_type"] == "Seasonal Photography",
            "financial_telemetry_3mo": {
                "monthly_credits_npr":          credits_3mo,
                "monthly_debits_npr":           debits_3mo,
                "net_cash_flow_npr":            net_3mo,
                "coverage_ratio":               coverage_3mo,
                "consecutive_negative_months":  max_neg,
                "festival_spike_normalized":    True,
            },
            "proxy_features": {
                "nea_bill_consecutive_on_time_months":   nea_streak,
                "water_bill_consecutive_on_time_months": random.randint(3, 6),
                "airtime_topup_regularity_index":        topup_regularity,
                "days_to_payment_variance":              payment_variance,
                "payment_delays_raw_3mo":                [t["days_to_pay"] for t in nea_txns[-3:]],
                "cross_utility_correlation_stress":      cross_utility,
            },
        },
        "household_correlation": {
            "same_household_merchants": [],
            "correlated_risk_flag":     False,
        },
        "trust_score": {
            "final_trust_score":     0,
            "score_band_plus_minus": 5,
            "score_status":          "pending",
            "lending_tier":          "Tier 3 — Conditional / Pilot",
            "ml_label": {"repayment_risk": "medium", "default_probability_band": "0.25-0.55"},
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# VOUCH EDGES (merchants vouch for each other)
# ─────────────────────────────────────────────────────────────────────────────

VOUCH_EDGES = [
    ("USR-M-001", "USR-M-002", 0.9),
    ("USR-M-001", "USR-M-004", 0.8),
    ("USR-M-005", "USR-M-001", 0.85),
    ("USR-M-002", "USR-M-005", 0.75),
    ("USR-M-004", "USR-M-002", 0.7),
]


# ─────────────────────────────────────────────────────────────────────────────
# DB WRITE
# ─────────────────────────────────────────────────────────────────────────────

async def seed(conn):
    print("Seeding users...")
    for u in USERS:
        await conn.execute("""
            INSERT INTO users
                (user_id, full_name, role, phone, location, business_name,
                 business_type, esewa_id, khalti_id, joined_date)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            ON CONFLICT (user_id) DO NOTHING
        """, u["user_id"], u["full_name"], u["role"], u.get("phone"),
             u.get("location"), u.get("business_name"), u.get("business_type"),
             u.get("esewa_id"), u.get("khalti_id"), u["joined_date"])
    print(f"  {len(USERS)} users inserted")

    print("Generating transactions for 6 months (Jan–Jun 2025)...")
    all_txns = []
    merchant_txn_map = defaultdict(list)

    for merchant in MERCHANTS:
        for month in range(1, 7):
            month_txns = generate_month_transactions(merchant, 2025, month)
            all_txns.extend(month_txns)
            for t in month_txns:
                if t["from_user_id"] == merchant["user_id"] or t["to_user_id"] == merchant["user_id"]:
                    merchant_txn_map[merchant["user_id"]].append(t)

    print(f"  {len(all_txns)} total transactions generated")

    # Batch insert transactions
    await conn.executemany("""
        INSERT INTO transactions
            (txn_id, from_user_id, to_user_id, amount_npr, txn_type,
             status, payment_method, description, txn_date, days_to_pay)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        ON CONFLICT (txn_id) DO NOTHING
    """, [(
        t["txn_id"], t["from_user_id"], t["to_user_id"],
        t["amount_npr"], t["txn_type"], t["status"],
        t["payment_method"], t["description"], t["txn_date"], t["days_to_pay"]
    ) for t in all_txns])
    print(f"  Transactions written to DB")

    print("Seeding merchants with derived full_data...")
    for merchant in MERCHANTS:
        mid      = merchant["user_id"]
        txns     = merchant_txn_map[mid]
        full_data = derive_merchant_full_data(merchant, txns)
        is_digital = bool(merchant.get("esewa_id"))

        await conn.execute("""
            INSERT INTO merchants
                (merchant_id, owner_name, legal_name, location, business_type,
                 segment, months_active, digital_footprint, esewa_registered,
                 khalti_registered, full_data)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            ON CONFLICT (merchant_id) DO NOTHING
        """,
            mid,
            merchant["full_name"],
            merchant["business_name"],
            merchant["location"],
            merchant["business_type"],
            merchant["segment"],
            merchant["months_active"],
            is_digital,
            bool(merchant.get("esewa_id")),
            bool(merchant.get("khalti_id")),
            json.dumps(full_data)
        )

    print("Seeding vouch edges...")
    for (frm, to, weight) in VOUCH_EDGES:
        await conn.execute("""
            INSERT INTO vouch_edges (from_merchant_id, to_merchant_id, edge_weight)
            VALUES ($1,$2,$3)
            ON CONFLICT DO NOTHING
        """, frm, to, weight)

    # Summary stats
    txn_count   = await conn.fetchval("SELECT COUNT(*) FROM transactions")
    user_count  = await conn.fetchval("SELECT COUNT(*) FROM users")
    merch_count = await conn.fetchval("SELECT COUNT(*) FROM merchants")
    edge_count  = await conn.fetchval("SELECT COUNT(*) FROM vouch_edges")

    print(f"\n✅ Done!")
    print(f"   Users:        {user_count}")
    print(f"   Merchants:    {merch_count}")
    print(f"   Transactions: {txn_count}")
    print(f"   Vouch edges:  {edge_count}")

    # Per-merchant breakdown
    print("\n   Per-merchant transaction counts:")
    for merchant in MERCHANTS:
        mid = merchant["user_id"]
        c = await conn.fetchval(
            "SELECT COUNT(*) FROM transactions WHERE from_user_id=$1 OR to_user_id=$1", mid
        )
        print(f"     {mid} ({merchant['full_name'][:20]:<20}): {c} txns")


async def main():
    print(f"Connecting to {DATABASE_URL}...")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Create tables
        with open(os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")) as f:
            schema = f.read()
        # Run each statement separately (skip \c and CREATE DATABASE)
        for stmt in schema.split(";"):
            stmt = stmt.strip()
            if not stmt or stmt.startswith("--") or stmt.startswith("\\") or "CREATE DATABASE" in stmt:
                continue
            try:
                await conn.execute(stmt)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    print(f"  Schema warning: {e}")

        await seed(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())