interface WelcomeScreenProps {
  onQuestionSelect: (question: string) => void;
}

const predefinedQuestions = [
  { icon: "🧠", text: "What is the Transformer architecture and how does attention work?" },
  { icon: "🚀", text: "What does NASA's Earth at Night research reveal about light pollution?" },
  { icon: "📋", text: "What is the NIST Cybersecurity Framework?" },
  { icon: "☁️", text: "How does Microsoft approach sustainability in cloud infrastructure?" },
];

export default function WelcomeScreen({ onQuestionSelect }: WelcomeScreenProps) {
  return (
    <div className="welcome-screen">
      <h1 className="welcome-title">What can I help you with?</h1>
      <p className="welcome-subtitle">
        Ask about AI research, space science, standards, or cloud &amp; sustainability
      </p>
      <div className="welcome-cards">
        {predefinedQuestions.map((q, i) => (
          <button key={i} className="welcome-card" onClick={() => onQuestionSelect(q.text)}>
            <span className="welcome-card-icon">{q.icon}</span>
            <span className="welcome-card-text">{q.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
