import { useState } from "react";

const formatMarkdown = (text: string): string => {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/\n/g, "<br />");
};

interface SourceInfo {
  kb: string;
  title?: string;
  filepath?: string;
  url?: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  agent?: string;
  sources?: SourceInfo[];
}

type WorkflowStep = "idle" | "routing" | "ai-research" | "space-science" | "standards" | "cloud-sustainability" | "complete";

type NodeId =
  | "input"
  | "orchestrator"
  | "ai-research"
  | "space-science"
  | "standards"
  | "cloud-sustainability"
  | "complete"
  | "idle";

interface TraceLog {
  timestamp: string;
  type: "info" | "route" | "query" | "response";
  message: string;
}

interface AgentInfo {
  id: string;
  name: string;
  icon: string;
  description: string;
  model: string;
  connectedKB: string | null;
  knowledgeSources: string[];
}

interface KBInfo {
  id: string;
  name: string;
  icon: string;
  description: string;
  retrievalMode: string;
  model: string;
  knowledgeSources: string[];
}

const agents: AgentInfo[] = [
  {
    id: "orchestrator",
    name: "Orchestrator",
    icon: "🎯",
    description: "Routes user queries to the appropriate specialist agent based on intent analysis.",
    model: "gpt-4o",
    connectedKB: null,
    knowledgeSources: [],
  },
  {
    id: "ai-research",
    name: "AI Research Agent",
    icon: "🧠",
    description: "Handles AI/ML research papers, transformer architecture, attention mechanisms, BERT, GPT, and deep learning.",
    model: "gpt-4o",
    connectedKB: "ks-ai-research",
    knowledgeSources: ["ks-ai-research"],
  },
  {
    id: "space-science",
    name: "Space Science Agent",
    icon: "🚀",
    description: "Handles NASA publications, earth observation, satellite imagery, and space exploration research.",
    model: "gpt-4o",
    connectedKB: "ks-space-science",
    knowledgeSources: ["ks-space-science"],
  },
  {
    id: "standards",
    name: "Standards Agent",
    icon: "📋",
    description: "Handles NIST frameworks, cybersecurity standards, AI risk management, and governance.",
    model: "gpt-4o",
    connectedKB: "ks-standards",
    knowledgeSources: ["ks-standards"],
  },
  {
    id: "cloud-sustainability",
    name: "Cloud & Sustainability Agent",
    icon: "☁️",
    description: "Handles Azure architecture, Microsoft whitepapers, sustainability, and enterprise cloud solutions.",
    model: "gpt-4o",
    connectedKB: "ks-cloud-sustainability",
    knowledgeSources: ["ks-cloud-sustainability"],
  },
];

const knowledgeBases: KBInfo[] = [
  {
    id: "ks-ai-research",
    name: "AI Research KB",
    icon: "🧪",
    description: "ArXiv papers on transformers, attention mechanisms, BERT, GPT, and deep learning architectures.",
    retrievalMode: "Agentic Retrieval",
    model: "text-embedding-3-large",
    knowledgeSources: ["ks-ai-research"],
  },
  {
    id: "ks-space-science",
    name: "Space Science KB",
    icon: "🌍",
    description: "NASA publications on earth observation, satellite imagery, light pollution, and space science.",
    retrievalMode: "Agentic Retrieval",
    model: "text-embedding-3-large",
    knowledgeSources: ["ks-space-science"],
  },
  {
    id: "ks-standards",
    name: "Standards KB",
    icon: "🔒",
    description: "NIST cybersecurity framework, AI risk management framework, and governance standards.",
    retrievalMode: "Agentic Retrieval",
    model: "text-embedding-3-large",
    knowledgeSources: ["ks-standards"],
  },
  {
    id: "ks-cloud-sustainability",
    name: "Cloud & Sustainability KB",
    icon: "🌱",
    description: "Azure whitepapers, Microsoft sustainability reports, and enterprise cloud architecture guides.",
    retrievalMode: "Agentic Retrieval",
    model: "text-embedding-3-large",
    knowledgeSources: ["ks-cloud-sustainability"],
  },
];

const sourceLogos: Record<string, string> = {
  "ai-research-agent": "🧠",
  "space-science-agent": "🚀",
  "standards-agent": "📋",
  "cloud-sustainability-agent": "☁️",
  "ks-ai-research": "🧪",
  "ks-space-science": "🌍",
  "ks-standards": "🔒",
  "ks-cloud-sustainability": "🌱",
};

const predefinedQuestions = [
  { text: "What is the Transformer architecture and how does attention work?", agent: "AI Research" },
  { text: "What does NASA's Earth at Night research reveal about light pollution?", agent: "Space Science" },
  { text: "What is the NIST Cybersecurity Framework?", agent: "Standards" },
  { text: "How does Microsoft approach sustainability in cloud infrastructure?", agent: "Cloud" },
];

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [workflowStep, setWorkflowStep] = useState<WorkflowStep>("idle");
  const [activeAgent, setActiveAgent] = useState<string>("");
  const [selectedAgent, setSelectedAgent] = useState<AgentInfo | null>(null);
  const [selectedKB, setSelectedKB] = useState<KBInfo | null>(null);
  const [traceLogs, setTraceLogs] = useState<TraceLog[]>([]);

  const addTrace = (type: TraceLog["type"], message: string) => {
    const now = new Date();
    const timestamp = now.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    setTraceLogs((prev) => [...prev, { timestamp, type, message }]);
  };

  const sendMessage = async (text?: string) => {
    const messageText = text || input;
    if (!messageText.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: messageText };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setWorkflowStep("routing");
    setActiveAgent("Orchestrator");
    setSelectedAgent(null);
    setSelectedKB(null);

    addTrace("info", `User query: "${messageText}"`);
    addTrace("route", "Orchestrator analyzing query intent...");

    try {
      const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: messageText }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const data = await response.json();
      const agentName = data.agent?.replace("-agent", "") || "unknown";

      addTrace("route", `Routed to: ${agentName} agent`);
      setWorkflowStep(agentName as WorkflowStep);
      setActiveAgent(`${agentName.charAt(0).toUpperCase() + agentName.slice(1)} Agent`);

      addTrace("query", `${agentName} agent querying knowledge base...`);

      await new Promise((r) => setTimeout(r, 300));

      addTrace("response", `Response received from ${agentName} agent`);

      const assistantMessage: Message = {
        role: "assistant",
        content: data.message,
        agent: data.agent,
        sources: data.sources,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setWorkflowStep("complete");
    } catch (error) {
      addTrace("info", `Error: ${error}`);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${error}` },
      ]);
    } finally {
      setIsLoading(false);
      setTimeout(() => setWorkflowStep("idle"), 2000);
    }
  };

  const getNodeStatus = (nodeId: NodeId): string => {
    const step: string = workflowStep;
    if (step === "idle") return "idle";
    if (nodeId === "input") return "active";
    if (nodeId === "orchestrator") return step === "routing" ? "active" : "done";
    if (["ai-research", "space-science", "standards", "cloud-sustainability"].includes(nodeId)) {
      return step === nodeId ? "active" : "idle";
    }
    if (nodeId === "complete") return step === "complete" ? "active" : "idle";
    return "idle";
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1>FoundryIQ Multi-Agent Demo</h1>
          <span className="header-subtitle">Azure AI Foundry + Agent Framework — Frontier Research &amp; Innovation</span>
        </div>
        <div className="header-right">
          <span className="status-indicator">
            <span className={`dot ${isLoading ? "pulse" : "green"}`}></span>
            {isLoading ? "Processing" : "Ready"}
          </span>
        </div>
      </header>

      <div className="app-content">
        {/* Sidebar: Agent & KB Cards */}
        <aside className="sidebar">
          <div className="sidebar-section">
            <h3>Agents</h3>
            {agents.map((agent) => (
              <div
                key={agent.id}
                className={`agent-card ${selectedAgent?.id === agent.id ? "selected" : ""} ${workflowStep === agent.id ? "active" : ""}`}
                onClick={() => { setSelectedAgent(agent); setSelectedKB(null); }}
              >
                <div className="agent-card-header">
                  <span className="agent-icon">{agent.icon}</span>
                  <span className="agent-name">{agent.name}</span>
                </div>
                {agent.connectedKB && (
                  <div className="agent-kb">
                    <span className="kb-badge">{agent.connectedKB}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="sidebar-section">
            <h3>Knowledge Bases</h3>
            {knowledgeBases.map((kb) => (
              <div
                key={kb.id}
                className={`kb-card ${selectedKB?.id === kb.id ? "selected" : ""}`}
                onClick={() => { setSelectedKB(kb); setSelectedAgent(null); }}
              >
                <div className="kb-card-header">
                  <span className="kb-icon">{kb.icon}</span>
                  <span className="kb-name">{kb.name}</span>
                </div>
                <div className="kb-mode">{kb.retrievalMode}</div>
              </div>
            ))}
          </div>

          {/* Detail Panel */}
          {(selectedAgent || selectedKB) && (
            <div className="detail-panel">
              {selectedAgent && (
                <>
                  <h4>{selectedAgent.icon} {selectedAgent.name}</h4>
                  <p>{selectedAgent.description}</p>
                  <div className="detail-meta">
                    <span>Model: {selectedAgent.model}</span>
                    {selectedAgent.connectedKB && <span>KB: {selectedAgent.connectedKB}</span>}
                  </div>
                </>
              )}
              {selectedKB && (
                <>
                  <h4>{selectedKB.icon} {selectedKB.name}</h4>
                  <p>{selectedKB.description}</p>
                  <div className="detail-meta">
                    <span>Mode: {selectedKB.retrievalMode}</span>
                    <span>Embedding: {selectedKB.model}</span>
                  </div>
                </>
              )}
            </div>
          )}
        </aside>

        {/* Main: Workflow + Trace */}
        <main className="main-content">
          <div className="workflow-canvas">
            <div className={`workflow-node input-node ${getNodeStatus("input")}`}>
              <div className="node-status"></div>
              <div className="node-content"><span className="node-title">User Query</span></div>
            </div>

            <div className="connector-down"></div>

            <div className={`workflow-node orchestrator-node ${getNodeStatus("orchestrator")}`}>
              <div className="node-status"></div>
              <div className="node-content">
                <span className="node-icon">🎯</span>
                <span className="node-title">Orchestrator</span>
              </div>
              <div className="node-meta">Intent analysis &amp; routing</div>
            </div>

            <div className="connector-split">
              <div className="split-line"></div>
              <div className="split-line"></div>
              <div className="split-line"></div>
              <div className="split-line"></div>
            </div>

            <div className="specialist-nodes">
              {(["ai-research", "space-science", "standards", "cloud-sustainability"] as const).map((id) => {
                const agent = agents.find((a) => a.id === id)!;
                return (
                  <div key={id} className={`workflow-node specialist-node ${getNodeStatus(id)}`}>
                    <div className="node-status"></div>
                    <div className="node-content">
                      <span className="node-icon">{agent.icon}</span>
                      <span className="node-title">{agent.name.replace(" Agent", "")}</span>
                    </div>
                    <div className="node-meta">
                      <span className="kb-badge">{agent.connectedKB}</span>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="connector-merge">
              <div className="merge-line"></div>
              <div className="merge-line"></div>
              <div className="merge-line"></div>
              <div className="merge-line"></div>
            </div>

            <div className={`workflow-node output-node ${workflowStep === "complete" ? "complete" : "idle"}`}>
              <div className="node-status"></div>
              <div className="node-content"><span className="node-title">Response</span></div>
              <div className="node-meta">Grounded answer with citations</div>
            </div>
          </div>

          {/* Trace Logs */}
          <div className="trace-panel">
            <div className="trace-header">
              <span className="trace-title">Execution Trace</span>
              {traceLogs.length > 0 && (
                <button className="trace-clear" onClick={() => setTraceLogs([])}>Clear</button>
              )}
            </div>
            <div className="trace-logs">
              {traceLogs.length === 0 ? (
                <div className="trace-empty">Waiting for query execution...</div>
              ) : (
                traceLogs.map((log, i) => (
                  <div key={i} className={`trace-log ${log.type}`}>
                    <span className="trace-time">{log.timestamp}</span>
                    <span className={`trace-type ${log.type}`}>
                      {log.type === "info" ? "INFO" : log.type === "route" ? "ROUTE" : log.type === "query" ? "QUERY" : "RESP"}
                    </span>
                    <span className="trace-msg">{log.message}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </main>

        {/* Chat Panel */}
        <aside className="chat-panel">
          <div className="chat-header">
            <h2>Chat</h2>
            <div className="chat-status">
              {isLoading && <span className="status-dot pulse"></span>}
              <span>{isLoading ? "Processing..." : "Ready"}</span>
            </div>
          </div>

          <div className="quick-actions">
            {predefinedQuestions.map((q, i) => (
              <button key={i} className="quick-action-btn" onClick={() => sendMessage(q.text)} disabled={isLoading}>
                {q.text}
              </button>
            ))}
          </div>

          <div className="messages">
            {messages.length === 0 && (
              <div className="empty-state">
                <div className="empty-text">Start a conversation</div>
                <div className="empty-subtext">Ask a question or click a quick action above</div>
              </div>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`message ${msg.role}`}>
                {msg.agent && (
                  <div className="message-header">
                    <span className="agent-icon">{sourceLogos[msg.agent] || "🤖"}</span>
                    <span className="agent-name">{msg.agent}</span>
                  </div>
                )}
                <div className="message-content" dangerouslySetInnerHTML={{ __html: formatMarkdown(msg.content) }} />
                {msg.sources && msg.sources.length > 0 && (
                  <div className="message-sources">
                    <span className="source-label">Sources:</span>
                    <div className="source-list">
                      {msg.sources.map((src, idx) => (
                        <span key={idx} className="source-doc">
                          <span className="source-doc-title">{src.title || src.filepath || "Document"}</span>
                          <span className="source-doc-kb">({src.kb})</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
            {isLoading && (
              <div className="message assistant loading">
                <div className="loading-indicator"><span></span><span></span><span></span></div>
                <span className="loading-text">
                  {workflowStep === "routing" ? "Routing query..." : `${activeAgent} processing...`}
                </span>
              </div>
            )}
          </div>

          <div className="input-area">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && sendMessage()}
              placeholder="Ask a question..."
              disabled={isLoading}
            />
            <button onClick={() => sendMessage()} disabled={isLoading || !input.trim()}>Send</button>
          </div>
        </aside>
      </div>
    </div>
  );
}

export default App;
