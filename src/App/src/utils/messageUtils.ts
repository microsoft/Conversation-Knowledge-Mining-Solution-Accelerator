import { type Citation } from "../types/AppTypes";

const CHART_KEYWORDS = ["chart", "graph", "visualize", "plot"];

export const isChartQuery = (query: string) =>
  CHART_KEYWORDS.some((keyword) => query.toLowerCase().includes(keyword));

export const parseCitationFromMessage = (message: unknown): Citation[] => {
  if (!message) {
    return [];
  }

  try {
    let parsedMessage: any;

    if (typeof message === "string") {
      if (message.trim().startsWith('"citations":')) {
        const wrappedMessage = `{${message.trim()}}`;
        parsedMessage = JSON.parse(wrappedMessage.replace(/\}\}$/, "}"));
      } else {
        parsedMessage = JSON.parse(message);
      }
    } else {
      parsedMessage = message;
    }

    if (Array.isArray(parsedMessage)) {
      return parsedMessage.map((item: any, index: number) => ({
        content: item.content || "",
        id: String(index + 1),
        title: item.title || null,
        filepath: item.filepath || null,
        url: item.url || null,
        metadata: item.metadata || null,
        chunk_id: item.chunk_id || null,
        reindex_id: String(index + 1),
      }));
    }

    if (Array.isArray(parsedMessage?.citations)) {
      return parsedMessage.citations;
    }
  } catch {
    return [];
  }

  return [];
};
