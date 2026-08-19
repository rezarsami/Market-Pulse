import { useEffect, useState, useRef } from "react";

/*
 * Perceived-speed progress indicator.
 *
 * The /analyze request is a single blocking call (~30-60s) with no
 * intermediate signal, so instead of a dead spinner we advance through the
 * agent's REAL phases on a calibrated timeline. Each phase has a minimum
 * dwell time roughly matching observed latencies; the last phase ("grounding")
 * intentionally never auto-completes -- it holds at "in progress" until the
 * real response arrives and the parent unmounts this component. That way we
 * never show "done" before the data is actually here.
 *
 * When we later add real SSE streaming from the backend, this same component
 * can be driven by real events (pass an `activeStage` prop) instead of timers.
 */

const STAGES = [
  {
    key: "route",
    label: "routing query",
    detail: "classifying intent — news / price / calc",
    ms: 2500,
  },
  {
    key: "search",
    label: "searching the live web",
    detail: "finding recent, price-relevant news",
    ms: 18000,
  },
  {
    key: "synthesize",
    label: "synthesizing",
    detail: "reading sources, scoring materiality, drafting cited summary",
    ms: 16000,
  },
  {
    key: "validate",
    label: "validating schema",
    detail: "parsing structured output, retrying on failure",
    ms: 4000,
  },
  {
    key: "ground",
    label: "checking grounding",
    detail: "verifying each claim against retrieved evidence",
    ms: null, // holds until real response lands
  },
];

export default function ProgressStages() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(Date.now());

  // Advance through the timed stages.
  useEffect(() => {
    const timers = [];
    let cumulative = 0;
    for (let i = 0; i < STAGES.length - 1; i++) {
      cumulative += STAGES[i].ms;
      timers.push(setTimeout(() => setActiveIndex(i + 1), cumulative));
    }
    return () => timers.forEach(clearTimeout);
  }, []);

  // Live elapsed clock, so even within a long stage something ticks.
  useEffect(() => {
    const id = setInterval(() => {
      setElapsed(((Date.now() - startRef.current) / 1000));
    }, 100);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="progress" role="status" aria-live="polite">
      <div className="progress__header">
        <span className="progress__spinner" aria-hidden="true" />
        <span className="progress__title">running agent</span>
        <span className="progress__clock">{elapsed.toFixed(1)}s</span>
      </div>
      <ol className="progress__stages">
        {STAGES.map((stage, i) => {
          const state =
            i < activeIndex ? "done" : i === activeIndex ? "active" : "pending";
          return (
            <li key={stage.key} className={`progress__stage progress__stage--${state}`}>
              <span className="progress__marker" aria-hidden="true">
                {state === "done" ? "✓" : state === "active" ? "▸" : "·"}
              </span>
              <span className="progress__stage-body">
                <span className="progress__stage-label">{stage.label}</span>
                <span className="progress__stage-detail">{stage.detail}</span>
              </span>
            </li>
          );
        })}
      </ol>
      <div className="progress__note">
        live web search takes a few seconds per query — results are cited and
        grounded, not pre-fetched
      </div>
    </div>
  );
}
