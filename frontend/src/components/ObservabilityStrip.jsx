export default function ObservabilityStrip({ response }) {
  const {
    strategy_used,
    schema_validation_retries,
    tool_calls,
    total_estimated_cost_usd,
    total_latency_ms,
    request_id,
  } = response;

  return (
    <details className="observability">
      <summary className="observability__summary">
        <span className="observability__pill">{strategy_used} strategy</span>
        <span className="observability__pill">{tool_calls.length} tool call{tool_calls.length === 1 ? "" : "s"}</span>
        <span className="observability__pill">{(total_latency_ms / 1000).toFixed(1)}s</span>
        <span className="observability__pill">${total_estimated_cost_usd.toFixed(4)}</span>
        {schema_validation_retries > 0 && (
          <span className="observability__pill observability__pill--warn">
            {schema_validation_retries} schema retry{schema_validation_retries === 1 ? "" : "ies"}
          </span>
        )}
        <span className="observability__expand-hint">request trace ▾</span>
      </summary>

      <div className="observability__detail">
        <div className="observability__request-id">request_id: {request_id}</div>
        <table className="observability__table">
          <thead>
            <tr>
              <th>tool</th>
              <th>latency</th>
              <th>result</th>
            </tr>
          </thead>
          <tbody>
            {tool_calls.map((tc, i) => (
              <tr key={i}>
                <td>{tc.tool_name}</td>
                <td>{tc.latency_ms.toFixed(0)}ms</td>
                <td className="observability__table-summary">{tc.output_summary}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <table className="observability__table">
          <thead>
            <tr>
              <th>model call</th>
              <th>tokens in/out</th>
              <th>cost</th>
            </tr>
          </thead>
          <tbody>
            {response.cost_breakdown.map((cb, i) => (
              <tr key={i}>
                <td>{cb.model}</td>
                <td>
                  {cb.input_tokens}/{cb.output_tokens}
                  {cb.web_searches > 0 ? ` (+${cb.web_searches} search)` : ""}
                </td>
                <td>${cb.estimated_cost_usd.toFixed(5)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
