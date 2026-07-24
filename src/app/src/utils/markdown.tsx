import React from "react";

function stripLinks(input: string): string {
  // Convert markdown links to citation-style labels: [label](url) -> [label]
  let out = input.replace(/\[([^\]]+)\]\(([^)]+)\)/g, "[$1]");
  // Remove raw URLs and sandbox/file-like link fragments in parentheses.
  out = out.replace(/\bhttps?:\/\/\S+/gi, "");
  out = out.replace(/\((?:sandbox\/|\/sandbox\/|file:\/\/)[^)]+\)/gi, "");
  return out;
}

function splitTableRow(row: string): string[] {
  let s = row.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|")) s = s.slice(0, -1);
  return s.split("|").map((c) => c.trim());
}

function isTableSeparator(row: string): boolean {
  const cells = splitTableRow(row);
  return cells.length > 0 && cells.every((c) => /^:?-+:?$/.test(c));
}

type ColAlign = "left" | "right" | "center";

function alignFromSeparatorCell(cell: string): ColAlign {
  const left = cell.startsWith(":");
  const right = cell.endsWith(":");
  if (left && right) return "center";
  if (right) return "right";
  return "left";
}

/** Simple markdown to JSX — handles bold, italic, lists, headers, tables, line breaks */
export function renderMarkdown(text: string, onCitation?: (n: number) => void): React.ReactNode {
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

  // Render a citation token [N] as a blue superscript. Clickable when onCitation is provided.
  const renderCitation = (inner: string, key: React.Key): React.ReactNode => {
    if (onCitation && /^\d+$/.test(inner)) {
      const n = parseInt(inner, 10);
      return (
        <sup
          key={key}
          role="button"
          tabIndex={0}
          onClick={() => onCitation(n)}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onCitation(n); }}
          style={{ color: "#2563eb", fontSize: "0.7em", fontWeight: 600, margin: "0 1px", verticalAlign: "super", cursor: "pointer" }}
        >
          [{inner}]
        </sup>
      );
    }
    return (
      <sup key={key} style={{ color: "#2563eb", fontSize: "0.7em", fontWeight: 600, margin: "0 1px", verticalAlign: "super" }}>
        [{inner}]
      </sup>
    );
  };

  // Split a plain string into text and [citation] tokens, keeping citations blue.
  const withCitations = (s: string, prefix: string): React.ReactNode[] =>
    s.split(/(\[[^\]]+\])/g).map((part, i) => {
      if (part.startsWith("[") && part.endsWith("]")) {
        return renderCitation(part.slice(1, -1), `${prefix}-${i}`);
      }
      return <React.Fragment key={`${prefix}-${i}`}>{part}</React.Fragment>;
    });

  const inlineFormat = (s: string): React.ReactNode => {
    // Process inline formatting: **bold**, *italic*, `code`, [citation]
    const parts = s.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\])/g);
    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={i}>{withCitations(part.slice(2, -2), `b${i}`)}</strong>;
      }
      if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
        return <em key={i}>{withCitations(part.slice(1, -1), `i${i}`)}</em>;
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return <code key={i} style={{ background: "#f1f5f9", padding: "1px 4px", borderRadius: 3, fontSize: "0.9em" }}>{part.slice(1, -1)}</code>;
      }
      if (part.startsWith("[") && part.endsWith("]")) {
        return renderCitation(part.slice(1, -1), i);
      }
      return part;
    });
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // GFM table: a header row followed by a separator row (| --- | --- |)
    if (trimmed.includes("|") && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      flushList();
      const headerCells = splitTableRow(trimmed);
      const aligns = splitTableRow(lines[i + 1]).map(alignFromSeparatorCell);
      const bodyRows: string[][] = [];
      let j = i + 2;
      while (j < lines.length && lines[j].trim() !== "" && lines[j].includes("|")) {
        bodyRows.push(splitTableRow(lines[j]));
        j++;
      }
      elements.push(
        <div key={`tbl-${i}`} style={{ overflowX: "auto", margin: "8px 0" }}>
          <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 13 }}>
            <thead>
              <tr>
                {headerCells.map((h, k) => (
                  <th
                    key={k}
                    style={{
                      textAlign: aligns[k] || "left",
                      padding: "6px 10px",
                      borderBottom: "2px solid #cbd5e1",
                      background: "#f8fafc",
                      fontWeight: 600,
                      color: "#0f172a",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {inlineFormat(h)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bodyRows.map((r, ri) => (
                <tr key={ri}>
                  {headerCells.map((_, ci) => (
                    <td
                      key={ci}
                      style={{
                        textAlign: aligns[ci] || "left",
                        padding: "6px 10px",
                        borderBottom: "1px solid #e2e8f0",
                        color: "#334155",
                      }}
                    >
                      {inlineFormat(r[ci] ?? "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      i = j - 1;
      continue;
    }

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
