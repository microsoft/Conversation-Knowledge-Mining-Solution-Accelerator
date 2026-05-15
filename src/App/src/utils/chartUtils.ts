import { type ChartDataResponse } from "../types/AppTypes";

export const parseChartContent = (content: string): unknown => {
  try {
    const parsedResponse = JSON.parse(content);

    if (parsedResponse?.error) {
      return parsedResponse.error;
    }

    if (parsedResponse?.object) {
      return parsedResponse.object;
    }

    return parsedResponse;
  } catch {
    return content;
  }
};

export const hasChartContent = (content: unknown): content is ChartDataResponse => {
  if (!content || typeof content === "string") {
    return false;
  }

  const chartContent = content as ChartDataResponse;
  return Boolean(chartContent.type && chartContent.data);
};

export const getSentimentColor = (label: string): string => {
  switch (label.toLowerCase()) {
    case "positive":
      return "#6576F9";
    case "neutral":
      return "#B2BBFC";
    case "negative":
      return "#FF749B";
    default:
      return "#ccc";
  }
};
