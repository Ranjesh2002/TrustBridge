import { useState } from "react";

const BIZ_LABELS = {
  vegetables: "🥦",
  tea_shop: "🍵",
  clothing: "👗",
  hardware: "🔧",
  dairy: "🥛",
  pharmacy: "💊",
  Pharmacy: "💊",
  "Kirana Pasala": "🛒",
  "Krishi Supplier": "🌾",
  Homestay: "🏠",
  Handicraft: "🧶",
  "Pashu Aahar": "🐄",
  "Restaurant & Hospitality": "🍜",
  "Tea & Local Eatery": "🍵",
  "Grocery & Daily Essentials": "🛒",
  "Electronics & Wholesale": "📱",
  "Vegetable & Seasonal Produce": "🥦",
  "Textiles & Apparel": "👗",
};

const RISK_STYLE = {
  low: { color: "var(--accent)", label: "low" },
  medium: { color: "var(--amber)", label: "med" },
  high: { color: "var(--red)", label: "high" },
};

const SEGMENT_DOT = {
  "Digital Native": { color: "var(--accent)", label: "digital" },
  "Cash Dominant": { color: "var(--amber)", label: "cash" },
  "New Merchant": { color: "var(--text-muted)", label: "new" },
};

export function Sidebar({ merchants, selectedId, onSelect }) {
  const [search, setSearch] = useState("");
  const [filterRisk, setFilterRisk] = useState("all");
  const [filterRegion, setFilterRegion] = useState("all");

  // Collect unique regions from merchant list
  const regions = [
    "all",
    ...new Set(merchants.map((m) => m.region).filter(Boolean)),
  ];

  const filtered = merchants.filter((m) => {
    const q = search.toLowerCase();
    const matchSearch =
      (m.name || "").toLowerCase().includes(q) ||
      (m.district || "").toLowerCase().includes(q) ||
      (m.business_type || "").toLowerCase().includes(q) ||
      (m.region || "").toLowerCase().includes(q);

    const matchRisk = filterRisk === "all" || m.repayment_risk === filterRisk;
    const matchRegion = filterRegion === "all" || m.region === filterRegion;

    return matchSearch && matchRisk && matchRegion;
  });

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <h1>
          Trust<span>Bridge</span>
        </h1>
        <p>Alternative Trust Layer · Nepal</p>
      </div>

      <div className="sidebar-search">
        <input
          type="text"
          placeholder="Search merchants..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* ── Filters ── */}
      <div
        style={{
          display: "flex",
          gap: 6,
          padding: "0 12px 10px",
          flexWrap: "wrap",
        }}
      >
        {/* Risk filter */}
        {["all", "low", "medium", "high"].map((r) => (
          <button
            key={r}
            onClick={() => setFilterRisk(r)}
            style={{
              fontSize: 10,
              padding: "2px 8px",
              borderRadius: 12,
              border: "1px solid",
              cursor: "pointer",
              fontFamily: "var(--font-mono)",
              background: filterRisk === r ? "var(--accent)" : "transparent",
              borderColor: filterRisk === r ? "var(--accent)" : "var(--border)",
              color: filterRisk === r ? "#000" : "var(--text-muted)",
            }}
          >
            {r === "all" ? "all risk" : r}
          </button>
        ))}
      </div>

      {/* Region filter */}
      {regions.length > 2 && (
        <div
          style={{
            display: "flex",
            gap: 6,
            padding: "0 12px 10px",
            flexWrap: "wrap",
          }}
        >
          {regions.map((r) => (
            <button
              key={r}
              onClick={() => setFilterRegion(r)}
              style={{
                fontSize: 10,
                padding: "2px 8px",
                borderRadius: 12,
                border: "1px solid",
                cursor: "pointer",
                fontFamily: "var(--font-mono)",
                background:
                  filterRegion === r ? "var(--accent-dim)" : "transparent",
                borderColor:
                  filterRegion === r ? "var(--accent)" : "var(--border)",
                color:
                  filterRegion === r ? "var(--accent)" : "var(--text-muted)",
              }}
            >
              {r === "all" ? "all regions" : r}
            </button>
          ))}
        </div>
      )}

      <div className="sidebar-label">{filtered.length} merchants</div>

      <div className="merchant-list">
        {filtered.map((m) => {
          const risk = RISK_STYLE[m.repayment_risk];
          const seg = SEGMENT_DOT[m.segment];
          return (
            <div
              key={m.merchant_id}
              className={`merchant-item ${selectedId === m.merchant_id ? "active" : ""}`}
              onClick={() => onSelect(m.merchant_id)}
            >
              <div className="merchant-item-name">
                {BIZ_LABELS[m.business_type] || "🏪"} {m.name}
              </div>

              <div className="merchant-item-meta">
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    color: "var(--text-dim)",
                  }}
                >
                  {m.merchant_id}
                </span>
                <span>·</span>
                <span>{m.district || m.location}</span>
                {m.region && (
                  <>
                    <span>·</span>
                    <span style={{ color: "var(--text-muted)", fontSize: 10 }}>
                      {m.region}
                    </span>
                  </>
                )}
              </div>

              <div
                style={{
                  display: "flex",
                  gap: 6,
                  marginTop: 4,
                  alignItems: "center",
                }}
              >
                {/* Segment dot */}
                {seg && (
                  <span style={{ color: seg.color, fontSize: 10 }}>
                    ● {seg.label}
                  </span>
                )}

                {/* Risk badge */}
                {risk && (
                  <span
                    style={{
                      fontSize: 9,
                      padding: "1px 6px",
                      borderRadius: 10,
                      border: `1px solid ${risk.color}`,
                      color: risk.color,
                      fontFamily: "var(--font-mono)",
                      marginLeft: "auto",
                    }}
                  >
                    {risk.label}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
