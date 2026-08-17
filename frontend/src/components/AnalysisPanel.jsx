import GroundingBanner from "./GroundingBanner.jsx";
import NewsItemCard from "./NewsItemCard.jsx";
import ObservabilityStrip from "./ObservabilityStrip.jsx";

export default function AnalysisPanel({ response }) {
  const { news_analysis, grounding_report } = response;
  const flaggedClaimTexts = grounding_report.flagged_claims.map((f) => f.claim);

  return (
    <section className="analysis">
      <div className="analysis__summary-block">
        <h2 className="analysis__eyebrow">synthesis</h2>
        <p className="analysis__summary">{news_analysis.summary}</p>
      </div>

      <GroundingBanner report={grounding_report} />

      {news_analysis.no_data_found ? (
        <div className="analysis__empty">
          no material recent news was found for {response.ticker}. the agent did not fabricate a
          placeholder answer — this reflects an actual empty search result.
        </div>
      ) : (
        <div className="analysis__items">
          {news_analysis.items.map((item, i) => (
            <NewsItemCard key={i} item={item} flaggedClaimTexts={flaggedClaimTexts} />
          ))}
        </div>
      )}

      <ObservabilityStrip response={response} />
    </section>
  );
}
