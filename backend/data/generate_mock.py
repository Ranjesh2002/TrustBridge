import json
import random
import math
from faker import Faker
from datetime import datetime, timedelta

fake = Faker()
random.seed(42)

DISTRICTS = ["Kathmandu", "Lalitpur", "Bhaktapur", "Pokhara", "Butwal", "Biratnagar"]
BUSINESS_TYPES = ["vegetables", "tea_shop", "clothing", "hardware", "dairy", "pharmacy"]
RELATIONSHIP_TYPES = ["supplier", "peer_merchant", "community_elder", "family_member"]

HARVEST_CALENDAR = {
    "vegetables": [1, 2, 3, 9, 10, 11],
    "dairy":      [4, 5, 6, 10, 11, 12],
    "tea_shop":   list(range(1, 13)),
    "clothing":   [10, 11, 12, 1, 2],
    "hardware":   [3, 4, 5, 9, 10],
    "pharmacy":   list(range(1, 13)),
}

NEPALI_FIRST_NAMES = [
    "Sita", "Ram", "Maya", "Hari", "Gita", "Krishna", "Laxmi", "Bikash",
    "Sunita", "Rajesh", "Anita", "Suresh", "Kamala", "Deepak", "Binita",
    "Nabin", "Puja", "Sanjay", "Mina", "Prakash"
]
NEPALI_LAST_NAMES = [
    "Sharma", "Thapa", "Tamang", "Gurung", "Shrestha", "Maharjan",
    "Lama", "Rai", "Karki", "Adhikari", "Bhattarai", "Pandey"
]

def nepali_name():
    return f"{random.choice(NEPALI_FIRST_NAMES)} {random.choice(NEPALI_LAST_NAMES)}"


def generate_monthly_revenue(business_type, months=18):
    base = random.uniform(15000, 80000)
    harvest_months = HARVEST_CALENDAR.get(business_type, list(range(1, 13)))
    revenue = []
    today = datetime.now()
    for i in range(months, 0, -1):
        month_date = today - timedelta(days=i * 30)
        month_num = month_date.month
        seasonal_boost = 1.4 if month_num in harvest_months else 0.85
        noise = random.uniform(0.85, 1.15)
        revenue.append({
            "month": month_date.strftime("%Y-%m"),
            "amount": round(base * seasonal_boost * noise, 2)
        })
    return revenue


def generate_utility_payments(months=18):
    payments = []
    today = datetime.now()
    for i in range(months, 0, -1):
        month_date = today - timedelta(days=i * 30)
        on_time = random.random() > 0.15
        partial = (not on_time) and random.random() > 0.5
        payments.append({
            "month": month_date.strftime("%Y-%m"),
            "utility": "NEA",
            "amount_due": random.randint(300, 1200),
            "paid_on_time": on_time,
            "partial_payment": partial,
            "days_late": 0 if on_time else random.randint(3, 45)
        })
    return payments


def generate_airtime_topups(months=18):
    topups = []
    today = datetime.now()
    for i in range(months, 0, -1):
        month_date = today - timedelta(days=i * 30)
        count = random.randint(2, 8)
        topups.append({
            "month": month_date.strftime("%Y-%m"),
            "provider": random.choice(["Ncell", "NTC"]),
            "topup_count": count,
            "total_amount": count * random.randint(50, 200)
        })
    return topups


def generate_khata_entries(months=6):
    entries = []
    today = datetime.now()
    for i in range(random.randint(8, 25)):
        entry_date = today - timedelta(days=random.randint(0, months * 30))
        amount = random.randint(200, 5000)
        repaid = random.random() > 0.2
        entries.append({
            "date": entry_date.strftime("%Y-%m-%d"),
            "counterparty": nepali_name(),
            "type": random.choice(["credit_given", "debt_taken"]),
            "amount": amount,
            "repaid": repaid,
            "days_to_repay": random.randint(1, 60) if repaid else None
        })
    return entries


def generate_vouchers(merchant_id, all_ids, count=3):
    available = [m for m in all_ids if m != merchant_id]
    chosen = random.sample(available, min(count, len(available)))
    return [
        {
            "voucher_id": vid,
            "relationship": random.choice(RELATIONSHIP_TYPES),
            "months_known": random.randint(3, 60),
            "voucher_trust_score": random.randint(40, 90)
        }
        for vid in chosen
    ]


def generate_merchants(n=30):
    merchants = []
    ids = [f"M{str(i).zfill(3)}" for i in range(1, n + 1)]

    for mid in ids:
        btype = random.choice(BUSINESS_TYPES)
        digital = random.random() > 0.4
        name = nepali_name()
        merchant = {
            "merchant_id": mid,
            "name": name,
            "district": random.choice(DISTRICTS),
            "business_type": btype,
            "business_name": f"{name.split()[-1]} {btype.replace('_', ' ').title()}",
            "phone": f"98{random.randint(10000000, 99999999)}",
            "years_in_business": round(random.uniform(0.5, 15), 1),
            "digital_footprint": digital,
            "esewa_registered": digital and random.random() > 0.3,
            "khalti_registered": digital and random.random() > 0.4,
            "vouchers": [],
            "revenue_history": generate_monthly_revenue(btype),
            "utility_payments": generate_utility_payments(),
            "airtime_topups": generate_airtime_topups(),
            "khata_entries": generate_khata_entries() if not digital else [],
            "created_at": datetime.now().isoformat()
        }
        merchants.append(merchant)

    for merchant in merchants:
        merchant["vouchers"] = generate_vouchers(
            merchant["merchant_id"], ids, count=random.randint(1, 4)
        )

    return merchants


if __name__ == "__main__":
    import os
    os.makedirs("backend/data", exist_ok=True)
    data = generate_merchants(30)
    with open("backend/data/mock_merchants.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Generated {len(data)} merchants → backend/data/mock_merchants.json")
