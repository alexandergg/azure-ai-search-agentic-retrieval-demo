export interface SourceInfo {
  kb: string;
  title?: string;
  filepath?: string;
  url?: string;
  snippet?: string;
  rerankerScore?: number;
}

export interface RetrievalActivity {
  id?: number;
  type: string;
  inputTokens?: number;
  outputTokens?: number;
  reasoningTokens?: number;
  elapsedMs?: number;
  count?: number;
  knowledgeSourceName?: string;
  searchIndexArguments?: { search: string };
  azureBlobArguments?: { search: string };
  webArguments?: { search: string };
  retrievalReasoningEffort?: { kind: string };
}

export interface RetrievalReference {
  docKey?: string;
  id?: string;
  type?: string;
  rerankerScore?: number;
}

export interface RetrievalJourneySummary {
  total_time_ms: number;
  total_docs_retrieved: number;
  num_subqueries: number;
  num_references: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_reasoning_tokens: number;
}

export interface RetrievalJourney {
  route: string;
  agent_name: string;
  activity: RetrievalActivity[];
  references: RetrievalReference[];
  summary: RetrievalJourneySummary;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  agent?: string;
  sources?: SourceInfo[];
  retrieval_journey?: RetrievalJourney;
  suggested_questions?: string[];
}

export interface ChatResponse {
  message: string;
  agent: string;
  sources: SourceInfo[];
  retrieval_journey?: RetrievalJourney;
  suggested_questions?: string[];
}
