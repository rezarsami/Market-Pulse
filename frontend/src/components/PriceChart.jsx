import { useEffect, useMemo, useState } from "react";
import Plot from "../lib/plotly.js";
import { fetchPriceHistory } from "../lib/api.js";

const PERIODS = ["1D", "1W", "1M", "1Y", "5Y"];

export default function PriceChart({ ticker }) {
  const [period, setPeriod] = useState("1M");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!ticker) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchPriceHistory({ ticker, period })
      .then((res) => {
        if (cancelled) return;
        setData(res);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message || "Failed to load price history");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ticker, period]);

  const plotData = useMemo(() => {
    if (!data || !data.bars || data.bars.length === 0) return null;
    return [
      {
        type: "candlestick",
        x: data.bars.map((b) => b.date),
        open: data.bars.map((b) => b.open),
        high: data.bars.map((b) => b.high),
        low: data.bars.map((b) => b.low),
        close: data.bars.map((b) => b.close),
        increasing: { line: { color: "#3ddc84" } },
        decreasing: { line: { color: "#e8555a" } },
      },
    ];
  }, [data]);

  return (
    <div className="pricechart">
      <div className="pricechart__header">
        <h2 className="pricechart__title">
          {ticker} <span className="pricechart__currency">{data?.currency || ""}</span>
        </h2>
        <div className="pricechart__periods" role="tablist" aria-label="Chart period">
          {PERIODS.map((p) => (
            <button
              key={p}
              role="tab"
              aria-selected={period === p}
              className={`pricechart__period-btn ${period === p ? "is-active" : ""}`}
              onClick={() => setPeriod(p)}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="pricechart__status">loading {period} bars…</div>}
      {error && <div className="pricechart__status pricechart__status--error">error: {error}</div>}
      {!loading && !error && data?.no_data_found && (
        <div className="pricechart__status pricechart__status--empty">
          no price data found for {ticker} — this ticker may be invalid, delisted, or not covered by the data
          source. no chart is shown because no real data exists to plot.
        </div>
      )}

      {!loading && !error && plotData && (
        <Plot
          data={plotData}
          layout={{
            autosize: true,
            height: 420,
            margin: { l: 50, r: 20, t: 10, b: 40 },
            paper_bgcolor: "transparent",
            plot_bgcolor: "transparent",
            font: { family: "IBM Plex Mono, monospace", color: "#8b9099", size: 11 },
            xaxis: {
              rangeslider: { visible: true, bgcolor: "#12151a", bordercolor: "#23272e" },
              gridcolor: "#1a1d23",
              type: "date",
            },
            yaxis: {
              gridcolor: "#1a1d23",
              side: "right",
              fixedrange: false,
            },
            dragmode: "pan",
          }}
          config={{
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ["lasso2d", "select2d"],
            responsive: true,
          }}
          style={{ width: "100%" }}
          useResizeHandler
        />
      )}
    </div>
  );
}
