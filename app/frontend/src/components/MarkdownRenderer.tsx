import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { SourceInfo } from "../types";

interface MarkdownRendererProps {
  content: string;
  onCitationClick?: (index: number) => void;
  sources?: SourceInfo[];
}

function processContentWithCitations(
  content: string,
  onCitationClick?: (index: number) => void,
  sources?: SourceInfo[],
): React.ReactNode[] {
  const parts = content.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      const idx = parseInt(match[1], 10);
      const sourceUrl = sources && sources[idx - 1]?.url;
      if (sourceUrl) {
        return (
          <a
            key={i}
            className="citation-ref"
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            title={sources[idx - 1]?.title || `Source ${idx}`}
          >
            {idx}
          </a>
        );
      }
      return (
        <span
          key={i}
          className="citation-ref"
          onClick={() => onCitationClick?.(idx)}
          title={`Source ${idx}`}
        >
          {idx}
        </span>
      );
    }
    return (
      <ReactMarkdown
        key={i}
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            const code = String(children).replace(/\n$/, "");
            if (match) {
              return (
                <SyntaxHighlighter
                  style={oneLight}
                  language={match[1]}
                  PreTag="div"
                >
                  {code}
                </SyntaxHighlighter>
              );
            }
            return (
              <code className={className} {...props}>
                {children}
              </code>
            );
          },
          a({ href, children, ...props }) {
            return (
              <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                {children}
              </a>
            );
          },
        }}
      >
        {part}
      </ReactMarkdown>
    );
  });
}

export default function MarkdownRenderer({ content, onCitationClick, sources }: MarkdownRendererProps) {
  const hasCitations = /\[\d+\]/.test(content);

  if (hasCitations) {
    return (
      <div className="markdown-content">
        {processContentWithCitations(content, onCitationClick, sources)}
      </div>
    );
  }

  return (
    <div className="markdown-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            const code = String(children).replace(/\n$/, "");
            if (match) {
              return (
                <SyntaxHighlighter
                  style={oneLight}
                  language={match[1]}
                  PreTag="div"
                >
                  {code}
                </SyntaxHighlighter>
              );
            }
            return (
              <code className={className} {...props}>
                {children}
              </code>
            );
          },
          a({ href, children, ...props }) {
            return (
              <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                {children}
              </a>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
