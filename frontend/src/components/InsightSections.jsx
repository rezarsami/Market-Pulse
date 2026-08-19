/*
 * The analytical layer under the news items. Two sections beyond the summary:
 *
 *  - "how this affects the market": second-order / ripple effects, each framed
 *    as hedged reasoning about a related entity (supplier, competitor, sector).
 *  - "what actually matters": a RELATIVE materiality read across the items the
 *    agent found -- which move the needle vs. which are routine. Deliberately
 *    not framed as "priced-in vs. new", since that would require a market
 *    baseline the agent doesn't have.
 *
 * Both render only when the agent produced them, so older responses or
 * no-data cases degrade cleanly to nothing.
 */

const DIR_CLASS = {
  positive: "insight__dir--pos",
  negative: "insight__dir--neg",
  neutral: "insight__dir--neutral",
  mixed: "insight__dir--mixed",
};

const WEIGHT_META = {
  high: { label: "high", dots: 3, cls: "insight__weight--high" },
  medium: { label: "medium", dots: 2, cls: "insight__weight--medium" },
  routine: { label: "routine", dots: 1, cls: "insight__weight--routine" },
};

function WeightDots({ weight }) {
  const meta = WEIGHT_META[weight] || WEIGHT_META.routine;
  return (
    <span className={`insight__weight ${meta.cls}`} aria-label={`${meta.label} materiality`}>
      <span className="insight__weight-dots" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={`insight__dot ${i < meta.dots ? "is-on" : ""}`}
          />
        ))}
      </span>
      {meta.label}
    </span>
  );
}

export default function InsightSections({ analysis, flaggedClaimTexts = [] }) {
  const effects = analysis.market_effects || [];
  const materiality = analysis.materiality || [];

  if (effects.length === 0 && materiality.length === 0) return null;

  // A materiality entry is flagged if the grounding pass flagged a claim
  // (prefixed "[materiality]") that references this headline.
  const isMaterialityFlagged = (headline) =>
    flaggedClaimTexts.some(
      (c) =>
        c.toLowerCase().includes("[materiality]") &&
        headline &&
        c.toLowerCase().includes(headline.toLowerCase().slice(0, 40))
    );

  return (
    <div className="insight">
      {effects.length > 0 && (
        <section className="insight__section" aria-label="How this affects the market">
          <h3 className="insight__eyebrow">how this affects the market</h3>
          <p className="insight__note">
            second-order effects on related companies and sectors — reasoning, not
            assertions · inference, so not covered by the grounding check
          </p>
          <ul className="insight__effects">
            {effects.map((e, i) => (
              <li key={i} className="insight__effect">
                <div className="insight__effect-head">
                  <span className="insight__entity">{e.entity}</span>
                  <span className={`insight__dir ${DIR_CLASS[e.direction] || ""}`}>
                    {e.direction}
                  </span>
                </div>
                <p className="insight__effect-body">{e.reasoning}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {materiality.length > 0 && (
        <section className="insight__section" aria-label="What actually matters">
          <h3 className="insight__eyebrow">what actually matters</h3>
          <p className="insight__note">
            relative materiality across what was found — which items move the needle vs.
            routine coverage · verified against retrieved evidence by the grounding check
          </p>
          <ul className="insight__materiality">
            {materiality.map((m, i) => {
              const flagged = isMaterialityFlagged(m.headline);
              return (
                <li
                  key={i}
                  className={`insight__mat ${flagged ? "insight__mat--flagged" : ""}`}
                >
                  <div className="insight__mat-head">
                    <WeightDots weight={m.weight} />
                    <span className="insight__mat-headline">{m.headline}</span>
                  </div>
                  <p className="insight__mat-why">{m.why}</p>
                  {flagged && (
                    <p className="insight__mat-flag">
                      ⚠ flagged by grounding check — headline or supporting detail not
                      traceable to a retrieved item
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}
