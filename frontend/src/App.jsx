import { useState } from "react";
import { Pulse as PulseIcon } from "@phosphor-icons/react";
import SearchBar from "./components/SearchBar.jsx";
import PriceChart from "./components/PriceChart.jsx";
import AnalyticsPanel from "./components/AnalyticsPanel.jsx";
import AnalysisPanel from "./components/AnalysisPanel.jsx";
import ProgressStages from "./components/ProgressStages.jsx";
import { analyzeTicker } from "./lib/api.js";
import "./App.css";

export default function App() {
  const [ticker, setTicker] = useState(null);
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit({ ticker: t, question, strategyOverride }) {
    setLoading(true);
    setError(null);
    setResponse(null);
    setTicker(t);
    try {
      const res = await analyzeTicker({ ticker: t, question, strategyOverride });
      setResponse(res);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__brand-row">
          <div className="app__brand">
            <PulseIcon size={20} weight="bold" className="app__brand-mark" aria-hidden="true" />
            <span className="app__brand-name">market pulse</span>
          </div>
          <div className="app__brand-meta">news synthesis · grounded · cited</div>
        </div>
        <div className="app__statusbar" role="status">
          <span className="app__status-item">
            <span className="app__status-dot" aria-hidden="true" /> live
          </span>
          <span className="app__status-sep">/</span>
          <span className="app__status-item">anthropic messages api</span>
          <span className="app__status-sep">/</span>
          <span className="app__status-item">hand-rolled agent loop</span>
          <span className="app__status-sep">/</span>
          <span className="app__status-item">yfinance price data</span>
        </div>
      </header>

      <div className="app__intro">
        <p className="app__intro-lead">
          Enter a ticker to get a live-searched, cited read on the news that could move it —
          each claim verified against its source before you see it.
        </p>
      </div>

      <main className="app__main">
        <SearchBar onSubmit={handleSubmit} loading={loading} />

        {error && (
          <div className="app__error">
            <strong>request failed</strong>
            <div>{error.message}</div>
            {error.status === 429 && <div className="app__error-hint">rate limit — wait a moment and try again</div>}
          </div>
        )}

        {ticker && (
          <div className="market-row">
            <div className="market-row__chart">
              <PriceChart ticker={ticker} />
            </div>
            <div className="market-row__analytics">
              <AnalyticsPanel ticker={ticker} />
            </div>
          </div>
        )}

        {loading && <ProgressStages />}

        {response && !loading && <AnalysisPanel response={response} />}

        {!ticker && !loading && (
          <div className="app__empty-state">
            <span className="app__empty-label">Try</span>
            {["AAPL", "TSLA", "NVDA", "SPY", "MSFT"].map((t) => (
              <button
                key={t}
                className="app__example-chip"
                onClick={() => handleSubmit({ ticker: t })}
              >
                {t}
              </button>
            ))}
          </div>
        )}
      </main>

      <footer className="app__footer">
        <a href="https://github.com" target="_blank" rel="noopener noreferrer">
          source
        </a>
        <span>·</span>
        <span>built on the Anthropic Messages API, hand-rolled agent loop, no framework</span>
      </footer>
    </div>
  );
}
