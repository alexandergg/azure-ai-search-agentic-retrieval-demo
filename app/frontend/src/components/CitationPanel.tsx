import { useState } from "react";
import type { SourceInfo } from "../types";

interface CitationPanelProps {
  sources: SourceInfo[];
  highlightedIndex?: number | null;
}

export default function CitationPanel({ sources, highlightedIndex }: CitationPanelProps) {
  const [expanded, setExpanded] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="citation-panel">
      <button className="citation-toggle" onClick={() => setExpanded(!expanded)}>
        📚 {sources.length} source{sources.length !== 1 ? "s" : ""} {expanded ? "▾" : "▸"}
      </button>
      {expanded && (
        <div className="citation-list">
          {sources.map((src, idx) => (
            <div
              key={idx}
              className={`citation-card ${highlightedIndex === idx + 1 ? "highlighted" : ""}`}
              id={`citation-${idx + 1}`}
            >
              <span className="citation-number">{idx + 1}</span>
              <div className="citation-info">
                <div className="citation-title">
                  {src.url ? (
                    <a href={src.url} target="_blank" rel="noopener noreferrer">
                      {src.title || src.filepath || "Document"}
                    </a>
                  ) : (
                    src.title || src.filepath || "Document"
                  )}
                </div>
                <div className="citation-meta">
                  {src.kb}
                  {src.rerankerScore != null && ` · score: ${src.rerankerScore.toFixed(4)}`}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
