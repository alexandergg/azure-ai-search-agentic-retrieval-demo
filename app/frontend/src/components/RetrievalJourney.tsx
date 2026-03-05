import { useState } from "react";
import type { RetrievalJourney, RetrievalActivity } from "../types";

interface RetrievalJourneyPanelProps {
  journey: RetrievalJourney;
}

const RETRIEVAL_TYPES = new Set([
  "searchIndex", "azureBlob", "web", "remoteSharePoint",
  "indexedSharePoint", "indexedOneLake",
]);

function fmtMs(ms?: number): string {
  if (ms == null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

function fmtTokens(n?: number): string {
  if (n == null || n === 0) return "—";
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

function getSearchQuery(act: RetrievalActivity): string {
  for (const key of ["searchIndexArguments", "azureBlobArguments", "webArguments"] as const) {
    const args = act[key as keyof RetrievalActivity] as { search: string } | undefined;
    if (args && "search" in args) return args.search;
  }
  return "—";
}

export default function RetrievalJourneyPanel({ journey }: RetrievalJourneyPanelProps) {
  const [expanded, setExpanded] = useState(false);

  const { activity, references, summary } = journey;
  const planning = activity.filter((a) => a.type === "modelQueryPlanning");
  const searches = activity.filter((a) => RETRIEVAL_TYPES.has(a.type));
  const reasoning = activity.filter((a) => a.type === "agenticReasoning");
  const synthesis = activity.filter((a) => a.type === "modelAnswerSynthesis");

  const summaryParts: string[] = [];
  if (summary.num_subqueries > 0) summaryParts.push(`${summary.num_subqueries} sub-queries`);
  if (summary.total_docs_retrieved > 0) summaryParts.push(`${summary.total_docs_retrieved} docs retrieved`);
  if (summary.num_references > 0) summaryParts.push(`${summary.num_references} references`);
  if (summary.total_time_ms > 0) summaryParts.push(fmtMs(summary.total_time_ms));

  return (
    <div className="journey-panel">
      <button className="journey-toggle" onClick={() => setExpanded(!expanded)}>
        🔍 Retrieval journey {summaryParts.length > 0 && `· ${summaryParts.join(" · ")}`} {expanded ? "▾" : "▸"}
      </button>
      {expanded && (
        <div className="journey-content">
          <div className="journey-summary">
            {summary.num_subqueries > 0 && (
              <span className="journey-summary-item">
                <span className="journey-summary-value">{summary.num_subqueries}</span> sub-queries
              </span>
            )}
            {summary.total_docs_retrieved > 0 && (
              <span className="journey-summary-item">
                <span className="journey-summary-value">{summary.total_docs_retrieved}</span> docs retrieved
              </span>
            )}
            {summary.num_references > 0 && (
              <span className="journey-summary-item">
                <span className="journey-summary-value">{summary.num_references}</span> references cited
              </span>
            )}
            {summary.total_time_ms > 0 && (
              <span className="journey-summary-item">
                <span className="journey-summary-value">{fmtMs(summary.total_time_ms)}</span> total
              </span>
            )}
          </div>

          <div className="journey-timeline">
            {/* Query Planning */}
            {planning.map((p, i) => (
              <div key={`plan-${i}`} className="journey-step">
                <span className="journey-step-icon">🧠</span>
                <div className="journey-step-title">
                  Query Planning{planning.length > 1 ? ` (round ${i + 1})` : ""}
                </div>
                <div className="journey-step-detail">
                  <span className="highlight">{fmtTokens(p.inputTokens)}</span> in /{" "}
                  <span className="highlight">{fmtTokens(p.outputTokens)}</span> out · {fmtMs(p.elapsedMs)}
                  {searches.length > 0 && (
                    <div style={{ marginTop: 4 }}>
                      → Decomposed into <span className="highlight">{searches.length}</span> sub-queries
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* Search Execution */}
            {searches.length > 0 && (
              <div className="journey-step">
                <span className="journey-step-icon">🔍</span>
                <div className="journey-step-title">
                  Search Execution
                </div>
                <div className="journey-step-detail">
                  <span className="highlight">{searches.length}</span> queries ·{" "}
                  <span className="highlight">{summary.total_docs_retrieved}</span> docs ·{" "}
                  {fmtMs(searches.reduce((acc, s) => acc + (s.elapsedMs || 0), 0))}
                </div>
                <div className="journey-subqueries">
                  {searches.map((s, i) => (
                    <div key={i} className="journey-subquery">
                      <em>"{getSearchQuery(s)}"</em> →{" "}
                      <span className="highlight">{s.count || 0}</span> docs from{" "}
                      {s.knowledgeSourceName || "?"} · {fmtMs(s.elapsedMs)}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Agentic Reasoning */}
            {reasoning.map((r, i) => (
              <div key={`reason-${i}`} className="journey-step">
                <span className="journey-step-icon">⚡</span>
                <div className="journey-step-title">Agentic Reasoning</div>
                <div className="journey-step-detail">
                  <span className="highlight">{fmtTokens(r.reasoningTokens)}</span> tokens ·
                  effort={r.retrievalReasoningEffort?.kind || "?"} · {fmtMs(r.elapsedMs)}
                </div>
              </div>
            ))}

            {/* Answer Synthesis */}
            {synthesis.map((s, i) => (
              <div key={`synth-${i}`} className="journey-step">
                <span className="journey-step-icon">📝</span>
                <div className="journey-step-title">Answer Synthesis</div>
                <div className="journey-step-detail">
                  <span className="highlight">{fmtTokens(s.inputTokens)}</span> in /{" "}
                  <span className="highlight">{fmtTokens(s.outputTokens)}</span> out · {fmtMs(s.elapsedMs)}
                </div>
              </div>
            ))}

            {/* References */}
            {references.length > 0 && (
              <div className="journey-step">
                <span className="journey-step-icon">📚</span>
                <div className="journey-step-title">References</div>
                <div className="journey-step-detail">
                  <span className="highlight">{references.length}</span> sources cited
                </div>
                <div className="journey-references">
                  {references.slice(0, 10).map((ref, i) => (
                    <div key={i} className="journey-ref">
                      <span>{ref.docKey || ref.id || "?"}</span>
                      <span className="journey-ref-score">
                        ({ref.type}{ref.rerankerScore != null ? ` · score=${ref.rerankerScore.toFixed(4)}` : ""})
                      </span>
                    </div>
                  ))}
                  {references.length > 10 && (
                    <div className="journey-ref">… and {references.length - 10} more</div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Token Usage Table */}
          {(planning.length > 0 || synthesis.length > 0 || reasoning.length > 0) && (
            <table className="token-table">
              <thead>
                <tr>
                  <th>Phase</th>
                  <th>Input</th>
                  <th>Output</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {planning.map((p, i) => (
                  <tr key={`tp-${i}`}>
                    <td>Query Planning</td>
                    <td>{fmtTokens(p.inputTokens)}</td>
                    <td>{fmtTokens(p.outputTokens)}</td>
                    <td>{fmtMs(p.elapsedMs)}</td>
                  </tr>
                ))}
                {searches.length > 0 && (
                  <tr>
                    <td>Search ({searches.length} queries)</td>
                    <td>—</td>
                    <td>{summary.total_docs_retrieved} docs</td>
                    <td>{fmtMs(searches.reduce((a, s) => a + (s.elapsedMs || 0), 0))}</td>
                  </tr>
                )}
                {reasoning.map((r, i) => (
                  <tr key={`tr-${i}`}>
                    <td>Reasoning</td>
                    <td>—</td>
                    <td>{fmtTokens(r.reasoningTokens)}</td>
                    <td>{fmtMs(r.elapsedMs)}</td>
                  </tr>
                ))}
                {synthesis.map((s, i) => (
                  <tr key={`ts-${i}`}>
                    <td>Synthesis</td>
                    <td>{fmtTokens(s.inputTokens)}</td>
                    <td>{fmtTokens(s.outputTokens)}</td>
                    <td>{fmtMs(s.elapsedMs)}</td>
                  </tr>
                ))}
                <tr>
                  <td>Total</td>
                  <td>{fmtTokens(summary.total_input_tokens)}</td>
                  <td>{fmtTokens(summary.total_output_tokens + summary.total_reasoning_tokens)}</td>
                  <td>{fmtMs(summary.total_time_ms)}</td>
                </tr>
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
