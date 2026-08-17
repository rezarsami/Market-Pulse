const DIRECTION_LABEL = {
  positive: "▲ positive",
  negative: "▼ negative",
  neutral: "● neutral",
  mixed: "◆ mixed",
};

const DIRECTION_CLASS = {
  positive: "is-positive",
  negative: "is-negative",
  neutral: "is-neutral",
  mixed: "is-mixed",
};

function RelevanceBars({ score }) {
  // Signature element: relevance rendered as filled/empty ticks rather
  // than a generic numeric badge -- makes the 1-5 schema field legible
  // at a glance without a legend.
  const ticks = [1, 2, 3, 4, 5].map((n) => (n <= score ? "▮" : "▯"));
  return (
    <span className="relevance-bars" aria-label={`relevance ${score} of 5`} title={`relevance ${score}/5`}>
      {ticks.join("")}
    </span>
  );
}

export default function NewsItemCard({ item, flaggedClaimTexts }) {
  const isFlagged = flaggedClaimTexts.some((claim) =>
    item.rationale.toLowerCase().includes(claim.toLowerCase().slice(0, 30))
  );

  return (
    <article className={`news-item ${isFlagged ? "news-item--flagged" : ""}`}>
      <div className="news-item__meta-row">
        <RelevanceBars score={item.relevance_score} />
        <span className={`news-item__direction ${DIRECTION_CLASS[item.impact_direction] || ""}`}>
          {DIRECTION_LABEL[item.impact_direction] || item.impact_direction}
        </span>
        <span className="news-item__date">{item.published_at}</span>
      </div>

      <h3 className="news-item__headline">
        <a href={item.url} target="_blank" rel="noopener noreferrer">
          {item.headline}
        </a>
      </h3>

      <div className="news-item__source">{item.source}</div>
      <p className="news-item__rationale">{item.rationale}</p>

      {isFlagged && (
        <div className="news-item__flag">
          ⚠ grounding check could not verify a related claim in the summary against this evidence — see flagged
          claims below
        </div>
      )}
    </article>
  );
}
