import React from "react";

function stripLinks(input: string): string {
  // Convert markdown links to citation-style labels: [label](url) -> [label]
  let out = input.replace(/\[([^\]]+)\]\(([^)]+)\)/g, "[$1]");
  // Remove raw URLs and sandbox/file-like link fragments in parentheses.
  out = out.replace(/\bhttps?:\/\/\S+/gi, "");
  out = out.replace(/\((?:sandbox\/|\/sandbox\/|file:\/\/)[^)]+\)/gi, "");
  return out;
}

/** Simple markdown to JSX — handles bold, italic, lists, headers, line breaks */
export function renderMarkdown(text: string): React.ReactNode {
  const cleanText = stripLinks(text);
  // Normalize line endings
  const lines = cleanText.replace(/\r\n/g, "\n").split("\n");
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
        return (
          <sup key={i} style={{ color: "#2563eb", fontSize: "0.7em", fontWeight: 600, margin: "0 1px", verticalAlign: "super" }}>
            [{part.slice(1, -1)}]
          </sup>
        );
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

    // Empty line — but don't break lists if the next non-empty line continues the list
    if (!trimmed) {
      if (listItems.length > 0) {
        const next = lines.slice(i + 1).find(l => l.trim() !== "");
        const nextIsNumbered = next && /^\s*\d+[.):]\s+/.test(next);
        const nextIsBullet = next && /^\s*[-•*]\s+/.test(next);
        if ((isNumbered && nextIsNumbered) || (!isNumbered && nextIsBullet)) {
          continue; // stay in list mode — LLMs often put blank lines between items
        }
      }
      flushList();
      if (elements.length > 0) elements.push(<div key={`sp-${i}`} style={{ height: 8 }} />);
      continue;
    }

    flushList();
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
