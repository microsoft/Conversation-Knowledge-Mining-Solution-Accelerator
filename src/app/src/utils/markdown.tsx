import React from "react";

/** Simple markdown to JSX — handles bold, italic, lists, headers, line breaks */
export function renderMarkdown(text: string): React.ReactNode {
  // Normalize line endings
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const elements: React.ReactNode[] = [];
  let listItems: string[] = [];
  let isNumbered = false;

  const flushList = () => {
    if (listItems.length > 0) {
      if (isNumbered) {
        elements.push(
          <ol key={`ol-${elements.length}`} style={{ margin: "6px 0", paddingLeft: 22 }}>
            {listItems.map((item, j) => <li key={j} style={{ marginBottom: 4 }}>{inlineFormat(item)}</li>)}
          </ol>
        );
      } else {
        elements.push(
          <ul key={`ul-${elements.length}`} style={{ margin: "6px 0", paddingLeft: 22 }}>
            {listItems.map((item, j) => <li key={j} style={{ marginBottom: 4 }}>{inlineFormat(item)}</li>)}
          </ul>
        );
      }
      listItems = [];
    }
  };

  const inlineFormat = (s: string): React.ReactNode => {
    // Process inline formatting: **bold**, *italic*, `code`, [citation]
    const parts = s.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\])/g);
    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={i}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
        return <em key={i}>{part.slice(1, -1)}</em>;
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return <code key={i} style={{ background: "#f1f5f9", padding: "1px 4px", borderRadius: 3, fontSize: "0.9em" }}>{part.slice(1, -1)}</code>;
      }
      if (part.startsWith("[") && part.endsWith("]")) {
        return <span key={i} style={{ color: "#2563eb", fontSize: "0.85em" }}>{part.slice(1, -1)}</span>;
      }
      return part;
    });
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // Bullet list (-, *, •, with optional indentation)
    if (/^\s*[-•*]\s+/.test(line)) {
      if (listItems.length === 0) isNumbered = false;
      listItems.push(trimmed.replace(/^[-•*]\s+/, ""));
      continue;
    }
    // Numbered list
    if (/^\s*\d+[.):]\s+/.test(line)) {
      if (listItems.length === 0) isNumbered = true;
      listItems.push(trimmed.replace(/^\d+[.):]\s+/, ""));
      continue;
    }

    flushList();

    // Empty line
    if (!trimmed) {
      if (elements.length > 0) elements.push(<div key={`sp-${i}`} style={{ height: 8 }} />);
      continue;
    }
    // Headers
    if (trimmed.startsWith("### ")) {
      elements.push(<div key={i} style={{ fontSize: 14, fontWeight: 600, margin: "10px 0 4px", color: "#0f172a" }}>{inlineFormat(trimmed.slice(4))}</div>);
      continue;
    }
    if (trimmed.startsWith("## ")) {
      elements.push(<div key={i} style={{ fontSize: 15, fontWeight: 700, margin: "12px 0 4px", color: "#0f172a" }}>{inlineFormat(trimmed.slice(3))}</div>);
      continue;
    }
    if (trimmed.startsWith("# ")) {
      elements.push(<div key={i} style={{ fontSize: 16, fontWeight: 700, margin: "14px 0 4px", color: "#0f172a" }}>{inlineFormat(trimmed.slice(2))}</div>);
      continue;
    }
    // Horizontal rule
    if (/^---+$/.test(trimmed)) {
      elements.push(<hr key={i} style={{ border: "none", borderTop: "1px solid #e2e8f0", margin: "8px 0" }} />);
      continue;
    }
    // Normal paragraph
    elements.push(<div key={i} style={{ marginBottom: 2 }}>{inlineFormat(trimmed)}</div>);
  }
  flushList();
  return <>{elements}</>;
}
