import { useState } from "react";
import type { Message as MessageType } from "../types";
import MarkdownRenderer from "./MarkdownRenderer";
import CitationPanel from "./CitationPanel";
import RetrievalJourneyPanel from "./RetrievalJourney";
import SuggestedQuestions from "./SuggestedQuestions";

const agentLogos: Record<string, string> = {
  "ai-research-agent": "🧠",
  "space-science-agent": "🚀",
  "standards-agent": "📋",
  "cloud-sustainability-agent": "☁️",
  "none-agent": "🤖",
};

const agentDisplayNames: Record<string, string> = {
  "ai-research-agent": "AI Research",
  "space-science-agent": "Space Science",
  "standards-agent": "Standards",
  "cloud-sustainability-agent": "Cloud & Sustainability",
  "none-agent": "Assistant",
};

interface ChatMessageProps {
  message: MessageType;
  isLast: boolean;
  onSuggestedQuestion?: (question: string) => void;
}

export default function ChatMessage({ message, isLast, onSuggestedQuestion }: ChatMessageProps) {
  const [highlightedCitation, setHighlightedCitation] = useState<number | null>(null);

  const handleCitationClick = (index: number) => {
    setHighlightedCitation(index);
    const el = document.getElementById(`citation-${index}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
    setTimeout(() => setHighlightedCitation(null), 2000);
  };

  if (message.role === "user") {
    return (
      <div className="message user">
        <div className="message-content">{message.content}</div>
      </div>
    );
  }

  return (
    <div className="message assistant">
      {message.agent && (
        <div className="message-header">
          <span className="agent-badge">
            {agentLogos[message.agent] || "🤖"}{" "}
            {agentDisplayNames[message.agent] || message.agent}
          </span>
        </div>
      )}
      <div className="message-content">
        <MarkdownRenderer content={message.content} onCitationClick={handleCitationClick} />
      </div>

      {message.sources && message.sources.length > 0 && (
        <CitationPanel sources={message.sources} highlightedIndex={highlightedCitation} />
      )}

      {message.retrieval_journey && (
        <RetrievalJourneyPanel journey={message.retrieval_journey} />
      )}

      {isLast && message.suggested_questions && message.suggested_questions.length > 0 && onSuggestedQuestion && (
        <SuggestedQuestions questions={message.suggested_questions} onSelect={onSuggestedQuestion} />
      )}
    </div>
  );
}
