interface SuggestedQuestionsProps {
  questions: string[];
  onSelect: (question: string) => void;
}

export default function SuggestedQuestions({ questions, onSelect }: SuggestedQuestionsProps) {
  if (!questions || questions.length === 0) return null;

  return (
    <div className="suggested-questions">
      {questions.map((q, i) => (
        <button key={i} className="suggested-btn" onClick={() => onSelect(q)}>
          {q}
        </button>
      ))}
    </div>
  );
}
