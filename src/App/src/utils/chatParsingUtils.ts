/**
 * Shared utilities for parsing streaming chat responses.
 *
 * Extracted from the inline logic that was duplicated inside
 * `useChatApi.ts` so every call-site benefits from a single,
 * well-tested implementation.
 */

import { safeParse } from "./jsonUtils";

// ──────────────────────────────────────────────
//  extractAnswerAndCitations
// ──────────────────────────────────────────────

export interface AnswerAndCitations {
  /** Cleaned answer text, with `\\n` replaced by real line-breaks. */
  answer: string;
  /** Raw citation string (everything from `"citations":` onward), or empty. */
  citations: string;
  /** The role found in the parsed chunk (defaults to `"assistant"`). */
  role: string;
}

/**
 * Given the raw `content` string from a `ParsedChunk.choices[0].messages[0]`,
 * locate the `"answer":` and `"citations":` keys and return the cleaned values.
 *
 * The server streams partial JSON where the answer text appears between
 * `"answer":` and `"citations":` (when citations are present), so we use
 * substring extraction rather than full JSON parsing.
 */
export function extractAnswerAndCitations(
  responseContent: string,
  role = "assistant"
): AnswerAndCitations {
  const answerKey = `"answer":`;
  const citationsKey = `"citations":`;

  let answerTextStart = 0;
  const answerStartIndex = responseContent.indexOf(answerKey);
  if (answerStartIndex !== -1) {
    answerTextStart = answerStartIndex + answerKey.length;
  }

  let answerText: string;
  let citationString = "";

  const citationsStartIndex = responseContent.indexOf(citationsKey);
  if (citationsStartIndex > answerTextStart) {
    answerText = responseContent
      .substring(answerTextStart, citationsStartIndex)
      .trim();
    citationString = responseContent.substring(citationsStartIndex).trim();
  } else {
    answerText = responseContent.substring(answerTextStart).trim();
  }

  // Strip leading/trailing quotes, trailing commas, and convert escaped newlines
  answerText = answerText.replace(/^"+|"+$|,$/g, "");
  answerText = answerText.replace(/[",]+$/, "");
  answerText = answerText.replace(/\\n/g, "  \n");

  return { answer: answerText, citations: citationString, role };
}

// ──────────────────────────────────────────────
//  parseChartContent
// ──────────────────────────────────────────────

export interface ChartParseResult {
  /** `"chart"` when valid chart data is found, `"error"` on failure, `null` otherwise. */
  kind: "chart" | "error" | null;
  /** The chart data object (when `kind === "chart"`). */
  chartData?: { type: string; data: any; [key: string]: any };
  /** An error / fallback message (when `kind === "error"`). */
  errorMessage?: string;
}

/**
 * Parse the accumulated `runningText` from a streaming chat response
 * and attempt to extract structured chart data.
 *
 * The server may concatenate multiple JSON objects (separated by `}{`),
 * and the chart payload is typically in the last chunk.
 */
export function parseChartContent(runningText: string): ChartParseResult {
  const splitRunningText = runningText.split("}{");
  const lastSegment = splitRunningText[splitRunningText.length - 1]?.trim() ?? "";
  const normalizedSegment = lastSegment.startsWith("{")
    ? lastSegment
    : `{${lastSegment}`;
  const parsedChartResponse = safeParse<any>(normalizedSegment, null);

  if (!parsedChartResponse) return { kind: null };

  const rawContent =
    parsedChartResponse?.choices?.[0]?.messages?.[0]?.content;
  let chartResponse: any = safeParse<any>(
    typeof rawContent === "string" ? rawContent : "",
    rawContent
  );

  // Unwrap `{ answer: <chartData> }` envelope
  if (typeof chartResponse === "object" && "answer" in chartResponse) {
    const ans = chartResponse.answer;
    if (
      ans === "" ||
      ans === undefined ||
      (typeof ans === "object" && Object.keys(ans).length === 0)
    ) {
      return {
        kind: "error",
        errorMessage: "Chart can't be generated, please try again.",
      };
    }
    chartResponse = ans;
  }

  // Valid chart payload
  if (chartResponse?.type && chartResponse?.data) {
    return { kind: "chart", chartData: chartResponse };
  }

  // Fall back to error message from the response
  const errorMsg =
    parsedChartResponse?.error ||
    parsedChartResponse?.choices?.[0]?.messages?.[0]?.content;
  if (errorMsg) {
    return { kind: "error", errorMessage: errorMsg };
  }

  return { kind: null };
}
