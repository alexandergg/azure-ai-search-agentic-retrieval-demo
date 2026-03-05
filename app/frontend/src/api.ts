import { v4 as uuidv4 } from "uuid";
import type { ChatResponse } from "./types";

export function createSessionId(): string {
  return uuidv4();
}

export async function sendMessage(
  message: string,
  sessionId: string,
): Promise<ChatResponse> {
  const response = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  return response.json();
}

export interface StreamCallbacks {
  onRoute: (agent: string) => void;
  onDelta: (text: string) => void;
  onMetadata: (data: {
    sources: import("./types").SourceInfo[];
    suggested_questions: string[];
    retrieval_journey: import("./types").RetrievalJourney | null;
    clean_text: string;
  }) => void;
  onError: (error: string) => void;
  onDone: () => void;
}

export async function sendMessageStreaming(
  message: string,
  sessionId: string,
  callbacks: StreamCallbacks,
): Promise<void> {
  const response = await fetch("/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    let currentEvent = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        const data = JSON.parse(line.slice(6));
        switch (currentEvent) {
          case "route":
            callbacks.onRoute(data.agent);
            break;
          case "delta":
            callbacks.onDelta(data.text);
            break;
          case "metadata":
            callbacks.onMetadata(data);
            break;
          case "error":
            callbacks.onError(data.error);
            break;
          case "done":
            callbacks.onDone();
            break;
        }
        currentEvent = "";
      }
    }
  }
}

export async function clearSession(sessionId: string): Promise<void> {
  await fetch(`/chat/${sessionId}`, { method: "DELETE" });
}
