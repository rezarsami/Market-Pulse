import { useEffect, useMemo, useState } from "react";
import Plot from "../lib/plotly.js";
import { fetchPriceHistory } from "../lib/api.js";

const PERIODS = ["1D", "1W", "1M", "1Y", "5Y"];

const POS = "#0080FF";
const NEG = "#DC2626";

function fmtDate(iso, period) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  if (period === "1D" || period === "1W") {
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  }
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function PriceChart({ ticker }) {
  const [period, setPeriod] = useState("1M");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [hover, setHover] = useState(null);

  useEffect(() => {
    if (!ticker) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setHover(null);
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

  const bars = data?.bars || [];

  const firstClose = bars.length ? bars[0].close : null;
  const lastClose = bars.length ? bars[bars.length - 1].close : null;
  const periodUp = firstClose != null && lastClose != null ? lastClose >= firstClose : true;
  const lineColor = periodUp ? POS : NEG;

  const readoutClose = hover ? hover.close : lastClose;
  const readoutDate = hover ? hover.date : bars.length ? bars[bars.length - 1].date : null;
  const pctFromStart =
    firstClose != null && readoutClose != null && firstClose !== 0
      ? ((readoutClose - firstClose) / firstClose) * 100
      : null;
  const readoutUp = pctFromStart != null ? pctFromStart >= 0 : periodUp;

  const plotData = useMemo(() => {
    if (!bars.length) return null;
    const x = bars.map((b) => b.date);
    const y = bars.map((b) => b.close);
    const fill = periodUp ? "rgba(0,128,255,0.14)" : "rgba(220,38,38,0.10)";
    // Per-point % change from the period's first close, and a preformatted
    // date, passed as customdata so the native tooltip can show real
    // per-point analysis (price varies per point; market cap / volume do not,
    // so those stay in the stats table where they're accurate).
    const base = bars[0].close;
    const customdata = bars.map((b) => {
      const pct = base ? ((b.close - base) / base) * 100 : 0;
      const sign = pct >= 0 ? "+" : "";
      return [`${sign}${pct.toFixed(2)}%`, fmtDate(b.date, period)];
    });
    const cur = data?.currency || "";
    return [
      {
        type: "scatter",
        mode: "lines",
        x,
        y,
        customdata,
        line: { color: lineColor, width: 2, shape: "linear" },
        fill: "tozeroy",
        fillcolor: fill,
        hovertemplate:
          `<b>%{y:.2f} ${cur}</b>   %{customdata[0]}<br>` +
          `%{customdata[1]}<extra></extra>`,
      },
    ];
  }, [bars, periodUp, lineColor, data, period]);

  const yRange = useMemo(() => {
    if (!bars.length) return null;
    const ys = bars.map((b) => b.close);
    const min = Math.min(...ys);
    const max = Math.max(...ys);
    const pad = (max - min) * 0.08 || max * 0.02 || 1;
    return [min - pad, max + pad];
  }, [bars]);

  return (
    <div className="pricechart">
      <div className="pricechart__header">
        <div className="pricechart__heading">
          <h2 className="pricechart__title">
            {ticker} <span className="pricechart__currency">{data?.currency || ""}</span>
          </h2>
          {readoutClose != null && (
            <div className="pricechart__readout">
              <span className="pricechart__readout-price">
                {readoutClose.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </span>
              {pctFromStart != null && (
                <span
                  className={`pricechart__readout-pct ${readoutUp ? "is-pos" : "is-neg"}`}
                >
                  {pctFromStart >= 0 ? "\u25B2" : "\u25BC"} {pctFromStart >= 0 ? "+" : ""}
                  {pctFromStart.toFixed(2)}%
                </span>
              )}
              <span className="pricechart__readout-date">
                {readoutDate ? fmtDate(readoutDate, period) : ""}
                {hover ? "" : "  \u00B7 latest"}
              </span>
            </div>
          )}
        </div>
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

      {loading && <div className="pricechart__status">loading {period}\u2026</div>}
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
            margin: { l: 0, r: 8, t: 8, b: 28 },
            paper_bgcolor: "transparent",
            plot_bgcolor: "transparent",
            font: { family: "Fira Code, monospace", color: "#475569", size: 11 },
            hovermode: "x",
            hoverlabel: {
              bgcolor: "#FFFFFF",
              bordercolor: "#DBEAFE",
              font: { family: "IBM Plex Mono, monospace", color: "#1E3A8A", size: 12 },
              align: "left",
            },
            xaxis: {
              showgrid: false,
              zeroline: false,
              type: "date",
              showspikes: true,
              spikecolor: "#7C8AA0",
              spikethickness: 1,
              spikedash: "dot",
              spikemode: "across",
              spikesnap: "cursor",
            },
            yaxis: {
              gridcolor: "#E9EEF6",
              zeroline: false,
              side: "right",
              fixedrange: true,
              range: yRange || undefined,
              showticklabels: true,
              tickfont: { size: 10 },
            },
            dragmode: false,
          }}
          config={{
            displayModeBar: false,
            displaylogo: false,
            responsive: true,
          }}
          style={{ width: "100%", height: "100%" }}
          useResizeHandler
          onHover={(e) => {
            const p = e && e.points && e.points[0];
            if (p) setHover({ close: p.y, date: p.x });
          }}
          onUnhover={() => setHover(null)}
        />
      )}
    </div>
  );
}
