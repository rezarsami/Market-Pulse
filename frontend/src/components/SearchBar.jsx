import { useState } from "react";

const STRATEGIES = [
  { value: "", label: "Default (server config)" },
  { value: "router", label: "Router (classify → dispatch)" },
  { value: "agentic", label: "Agentic (model decides)" },
];

export default function SearchBar({ onSubmit, loading }) {
  const [ticker, setTicker] = useState("");
  const [question, setQuestion] = useState("");
  const [strategy, setStrategy] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  function handleSubmit(e) {
    e.preventDefault();
    if (!ticker.trim() || loading) return;
    onSubmit({ ticker: ticker.trim(), question: question.trim(), strategyOverride: strategy || undefined });
  }

  return (
    <form className="searchbar" onSubmit={handleSubmit}>
      <div className="searchbar__row">
        <label className="sr-only" htmlFor="ticker-input">
          Ticker symbol
        </label>
        <input
          id="ticker-input"
          className="searchbar__ticker"
          type="text"
          placeholder="TICKER"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          maxLength={10}
          autoComplete="off"
          spellCheck={false}
        />
        <input
          className="searchbar__question"
          type="text"
          placeholder="Optional question — e.g. why did it move this week?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={500}
        />
        <button className="searchbar__submit" type="submit" disabled={loading || !ticker.trim()}>
          {loading ? "Analyzing…" : "Analyze"}
        </button>
      </div>

      <button
        type="button"
        className="searchbar__advanced-toggle"
        onClick={() => setShowAdvanced((s) => !s)}
        aria-expanded={showAdvanced}
      >
        {showAdvanced ? "− advanced" : "+ advanced"}
      </button>

      {showAdvanced && (
        <div className="searchbar__advanced">
          <label htmlFor="strategy-select">tool-selection strategy</label>
          <select id="strategy-select" value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            {STRATEGIES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          <span className="searchbar__advanced-hint">
            overrides the server's configured default for this request only — see README for the eval numbers behind the default
          </span>
        </div>
      )}
    </form>
  );
}
