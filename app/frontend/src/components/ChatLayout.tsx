import { useRef, useEffect } from "react";
import type { Message } from "../types";
import ChatMessage from "./ChatMessage";
import ChatInput from "./ChatInput";
import WelcomeScreen from "./WelcomeScreen";

interface ChatLayoutProps {
  messages: Message[];
  input: string;
  isLoading: boolean;
  loadingText: string;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onNewChat: () => void;
  onSuggestedQuestion: (question: string) => void;
}

export default function ChatLayout({
  messages,
  input,
  isLoading,
  loadingText,
  onInputChange,
  onSend,
  onNewChat,
  onSuggestedQuestion,
}: ChatLayoutProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1>FoundryIQ</h1>
        </div>
        <div className="header-right">
          <button className="new-chat-btn" onClick={onNewChat}>
            + New Chat
          </button>
        </div>
      </header>

      <div className="chat-container">
        {messages.length === 0 && !isLoading ? (
          <WelcomeScreen onQuestionSelect={onSuggestedQuestion} />
        ) : (
          <div className="messages-area">
            <div className="messages-inner">
              {messages.map((msg, i) => (
                <ChatMessage
                  key={i}
                  message={msg}
                  isLast={i === messages.length - 1 && msg.role === "assistant"}
                  onSuggestedQuestion={onSuggestedQuestion}
                />
              ))}
              {isLoading && messages[messages.length - 1]?.content === "" && (
                <div className="loading-message">
                  <div className="loading-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                  <span className="loading-text">{loadingText}</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        )}

        <ChatInput
          value={input}
          onChange={onInputChange}
          onSend={onSend}
          disabled={isLoading}
        />
      </div>
    </div>
  );
}
