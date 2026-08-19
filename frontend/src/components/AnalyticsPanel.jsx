import { useEffect, useState } from "react";
import { CaretDown, CaretUp } from "@phosphor-icons/react";
import { fetchAnalytics } from "../lib/api.js";

const PERIODS = ["1M", "1Y", "5Y"];

const GLOSSARY = [
  ["Cumulative return", "The total percent change in price over the selected window, start to end."],
  ["Annualized volatility", "How much the daily price bounces around, scaled to a yearly figure. Higher means bigger swings. Under ~20% is calm; over ~40% is turbulent."],
  ["Max drawdown", "The worst peak-to-trough drop within the window — if you'd bought at the high, this is the deepest loss you'd have sat through."],
  ["Beta vs. SPY", "How much the stock moves relative to the overall market (S&P 500). 1.0 = moves with the market; above 1 = amplifies market moves; below 1 = calmer than the market."],
  ["Correlation vs. SPY", "How tightly the stock tracks the market, from -1 to 1. Near 1 means they move together; near 0 means largely independent."],
  ["Positive days", "The share of trading days in the window that closed up versus down."],
  ["Best / worst day", "The single largest up day and down day (by percent) in the window."],
  ["Price vs. 50-day avg", "Where the current price sits relative to its average over the last 50 days. Above suggests recent strength; below suggests recent weakness."],
];

function pct(v, opts = {}) {
  if (v === null || v === undefined) return "—";
  const sign = opts.signed && v > 0 ? "+" : "";
  return `${sign}${v.toFixed(opts.dp ?? 2)}%`;
}

function Metric({ label, value, tone, hint }) {
  return (
    <div className="analytics__metric">
      <span className="analytics__metric-label">{label}</span>
      <span className={`analytics__metric-value ${tone ? `is-${tone}` : ""}`}>{value}</span>
      {hint && <span className="analytics__metric-hint">{hint}</span>}
    </div>
  );
}

// A short, honest, rule-based read of the numbers. Deterministic — this is
// interpretation of computed stats, not model output.
function interpretation(a) {
  const parts = [];
  if (a.annualized_volatility_pct != null) {
    const v = a.annualized_volatility_pct;
    const band = v < 20 ? "relatively low" : v < 40 ? "moderate" : "high";
    parts.push(`Annualized volatility of ${v.toFixed(1)}% is ${band} for an equity.`);
  }
  if (a.beta_vs_spy != null) {
    const b = a.beta_vs_spy;
    const rel =
      b > 1.15 ? "more volatile than the market" :
      b < 0.85 ? "less volatile than the market" :
      "roughly in line with the market";
    parts.push(`Beta of ${b.toFixed(2)} vs. SPY means it has moved ${rel} over this window.`);
  }
  if (a.max_drawdown_pct != null) {
    parts.push(`Its largest peak-to-trough decline in the window was ${Math.abs(a.max_drawdown_pct).toFixed(1)}%.`);
  }
  if (a.price_vs_sma50_pct != null) {
    const above = a.price_vs_sma50_pct >= 0;
    parts.push(`Price is ${Math.abs(a.price_vs_sma50_pct).toFixed(1)}% ${above ? "above" : "below"} its 50-day average.`);
  }
  return parts.join(" ");
}

export default function AnalyticsPanel({ ticker }) {
  const [period, setPeriod] = useState("1Y");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [glossaryOpen, setGlossaryOpen] = useState(false);

  useEffect(() => {
    if (!ticker) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    fetchAnalytics({ ticker, period })
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Failed to load analytics");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ticker, period]);

  if (loading) return <div className="analytics analytics--status">computing analytics…</div>;
  if (error) return <div className="analytics analytics--status analytics--error">analytics unavailable: {error}</div>;
  if (!data || data.no_data_found) return null;

  return (
    <section className="analytics" aria-label={`Quantitative analytics for ${data.ticker}`}>
      <div className="analytics__head">
        <h2 className="analytics__title">Quantitative analysis</h2>
        <div className="analytics__periods" role="tablist" aria-label="Analysis window">
          {PERIODS.map((p) => (
            <button
              key={p}
              role="tab"
              aria-selected={period === p}
              className={`analytics__period-btn ${period === p ? "is-active" : ""}`}
              onClick={() => setPeriod(p)}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
      <p className="analytics__subhead">
        Computed from {data.n_days} daily closes with pandas / numpy — descriptive
        statistics on real price data, not model output.
      </p>

      <div className="analytics__grid">
        <Metric
          label="Cumulative return"
          value={pct(data.cumulative_return_pct, { signed: true })}
          tone={data.cumulative_return_pct >= 0 ? "pos" : "neg"}
        />
        <Metric
          label="Annualized volatility"
          value={pct(data.annualized_volatility_pct)}
          hint="std of daily returns × √252"
        />
        <Metric
          label="Max drawdown"
          value={pct(data.max_drawdown_pct)}
          tone="neg"
          hint="largest peak-to-trough"
        />
        <Metric
          label="Beta vs. SPY"
          value={data.beta_vs_spy != null ? data.beta_vs_spy.toFixed(2) : "—"}
          hint="market sensitivity"
        />
        <Metric
          label="Correlation vs. SPY"
          value={data.correlation_vs_spy != null ? data.correlation_vs_spy.toFixed(2) : "—"}
        />
        <Metric
          label="Positive days"
          value={pct(data.positive_day_share_pct, { dp: 1 })}
          hint="share of up days"
        />
        <Metric
          label="Best / worst day"
          value={`${pct(data.best_day_pct, { signed: true })} / ${pct(data.worst_day_pct, { signed: true })}`}
        />
        <Metric
          label="Price vs. 50-day avg"
          value={pct(data.price_vs_sma50_pct, { signed: true })}
          tone={data.price_vs_sma50_pct >= 0 ? "pos" : "neg"}
        />
      </div>

      <p className="analytics__read">{interpretation(data)}</p>

      <button
        type="button"
        className="analytics__glossary-toggle"
        onClick={() => setGlossaryOpen((o) => !o)}
        aria-expanded={glossaryOpen}
      >
        {glossaryOpen ? (
          <>
            <CaretUp size={13} weight="bold" aria-hidden="true" /> Hide explanations
          </>
        ) : (
          <>
            <CaretDown size={13} weight="bold" aria-hidden="true" /> What do these mean?
          </>
        )}
      </button>

      {glossaryOpen && (
        <dl className="analytics__glossary">
          {GLOSSARY.map(([term, def]) => (
            <div key={term} className="analytics__glossary-item">
              <dt className="analytics__glossary-term">{term}</dt>
              <dd className="analytics__glossary-def">{def}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
