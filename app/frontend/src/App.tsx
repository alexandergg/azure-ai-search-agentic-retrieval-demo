import { useState, useCallback, useRef } from "react";
import type { Message } from "./types";
import { createSessionId, sendMessageStreaming, clearSession } from "./api";
import ChatLayout from "./components/ChatLayout";

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [loadingText, setLoadingText] = useState("Processing...");
  const [sessionId, setSessionId] = useState(() => createSessionId());
  const streamingTextRef = useRef("");

  const handleSend = useCallback(async (text?: string) => {
    const messageText = text || input;
    if (!messageText.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: messageText };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setLoadingText("Routing query...");
    streamingTextRef.current = "";

    // Add empty assistant message that will be populated by streaming
    const assistantMessage: Message = { role: "assistant", content: "" };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      await sendMessageStreaming(messageText, sessionId, {
        onRoute: (agent) => {
          const name = agent?.replace("-agent", "") || "";
          setLoadingText(`${name} agent processing...`);
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = { ...updated[updated.length - 1], agent };
            return updated;
          });
        },
        onDelta: (deltaText) => {
          streamingTextRef.current += deltaText;
          const currentText = streamingTextRef.current;
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: currentText,
            };
            return updated;
          });
        },
        onMetadata: (data) => {
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: data.clean_text,
              sources: data.sources,
              retrieval_journey: data.retrieval_journey ?? undefined,
              suggested_questions: data.suggested_questions ?? undefined,
            };
            return updated;
          });
        },
        onError: (error) => {
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: `Error: ${error}`,
            };
            return updated;
          });
        },
        onDone: () => {
          // Done handled in finally
        },
      });
    } catch (error) {
      setMessages((prev) => {
        const updated = [...prev];
        if (updated[updated.length - 1]?.role === "assistant" && !updated[updated.length - 1].content) {
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: `Error: ${error}`,
          };
        } else {
          updated.push({ role: "assistant", content: `Error: ${error}` });
        }
        return updated;
      });
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, sessionId]);

  const handleNewChat = useCallback(async () => {
    await clearSession(sessionId);
    setMessages([]);
    setInput("");
    setSessionId(createSessionId());
  }, [sessionId]);

  const handleSuggestedQuestion = useCallback((question: string) => {
    handleSend(question);
  }, [handleSend]);

  return (
    <ChatLayout
      messages={messages}
      input={input}
      isLoading={isLoading}
      loadingText={loadingText}
      onInputChange={setInput}
      onSend={() => handleSend()}
      onNewChat={handleNewChat}
      onSuggestedQuestion={handleSuggestedQuestion}
    />
  );
}

export default App;
