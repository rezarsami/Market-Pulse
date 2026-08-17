export default function GroundingBanner({ report }) {
  if (report.is_fully_grounded) {
    return (
      <div className="grounding-banner grounding-banner--ok">
        ✓ grounding check passed — {report.checked_claims} claim(s) verified against retrieved evidence
      </div>
    );
  }

  return (
    <div className="grounding-banner grounding-banner--warn">
      <div className="grounding-banner__title">
        ⚠ grounding check flagged {report.flagged_claims.length} unsupported claim
        {report.flagged_claims.length === 1 ? "" : "s"}
      </div>
      <ul className="grounding-banner__list">
        {report.flagged_claims.map((flag, i) => (
          <li key={i}>
            <span className="grounding-banner__claim">"{flag.claim}"</span>
            <span className="grounding-banner__reason"> — {flag.reason}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
