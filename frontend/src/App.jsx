import { useState } from "react";
import SearchBar from "./components/SearchBar.jsx";
import PriceChart from "./components/PriceChart.jsx";
import AnalysisPanel from "./components/AnalysisPanel.jsx";
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
        <div className="app__brand">
          <span className="app__brand-mark">◈</span> market pulse
        </div>
        <div className="app__tagline">live-search news synthesis + price history, with cited, validated, grounded output</div>
      </header>

      <main className="app__main">
        <SearchBar onSubmit={handleSubmit} loading={loading} />

        {error && (
          <div className="app__error">
            <strong>request failed</strong>
            <div>{error.message}</div>
            {error.status === 429 && <div className="app__error-hint">rate limit — wait a moment and try again</div>}
          </div>
        )}

        {ticker && <PriceChart ticker={ticker} />}

        {loading && (
          <div className="app__loading">
            running agent: searching, reading, judging relevance, and checking grounding…
          </div>
        )}

        {response && !loading && <AnalysisPanel response={response} />}

        {!ticker && !loading && (
          <div className="app__empty-state">
            <p>enter a ticker (e.g. AAPL, TSLA, SPY) to get a live-searched, cited summary of news that could move its price, plus an interactive chart.</p>
            <p className="app__empty-state-sub">
              every news item below is validated against a strict schema and checked by a separate
              grounding pass before you see it. nothing is fabricated — if there's no data, the agent says so.
            </p>
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
