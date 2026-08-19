import { TrendUp, TrendDown, Minus, Diamond } from "@phosphor-icons/react";

const DIRECTION_META = {
  positive: { label: "positive", cls: "is-positive", Icon: TrendUp },
  negative: { label: "negative", cls: "is-negative", Icon: TrendDown },
  neutral: { label: "neutral", cls: "is-neutral", Icon: Minus },
  mixed: { label: "mixed", cls: "is-mixed", Icon: Diamond },
};

function RelevanceBars({ score }) {
  // Relevance as 5 filled/empty ticks — SVG-free but token-driven, not emoji.
  return (
    <span className="relevance-bars" aria-label={`relevance ${score} of 5`} title={`relevance ${score}/5`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <span key={n} className={`relevance-bars__tick ${n <= score ? "is-on" : ""}`} aria-hidden="true" />
      ))}
    </span>
  );
}

const WEIGHT_META = {
  high: { label: "high impact", cls: "is-high" },
  medium: { label: "medium impact", cls: "is-medium" },
  routine: { label: "routine", cls: "is-routine" },
};

export default function NewsItemCard({ item, materiality, flaggedClaimTexts }) {
  const isFlagged = flaggedClaimTexts.some((claim) =>
    item.rationale.toLowerCase().includes(claim.toLowerCase().slice(0, 30))
  );
  const weight = materiality ? WEIGHT_META[materiality.weight] : null;
  const dir = DIRECTION_META[item.impact_direction] || DIRECTION_META.neutral;
  const DirIcon = dir.Icon;

  return (
    <article className={`news-item ${isFlagged ? "news-item--flagged" : ""}`}>
      <div className="news-item__meta-row">
        <RelevanceBars score={item.relevance_score} />
        <span className={`news-item__direction ${dir.cls}`}>
          <DirIcon size={14} weight="bold" aria-hidden="true" /> {dir.label}
        </span>
        {weight && (
          <span className={`news-item__weight ${weight.cls}`} title={materiality.why}>
            {weight.label}
          </span>
        )}
        <span className="news-item__date">{item.published_at}</span>
      </div>

      <h3 className="news-item__headline">
        <a href={item.url} target="_blank" rel="noopener noreferrer">
          {item.headline}
        </a>
      </h3>

      <div className="news-item__source">{item.source}</div>
      <p className="news-item__rationale">{item.rationale}</p>

      {materiality && materiality.why && (
        <p className="news-item__weight-why">
          <span className="news-item__weight-why-label">why it matters:</span> {materiality.why}
        </p>
      )}

      {isFlagged && (
        <div className="news-item__flag">
          ⚠ grounding check could not verify a related claim in the summary against this evidence — see flagged
          claims below
        </div>
      )}
    </article>
  );
}
