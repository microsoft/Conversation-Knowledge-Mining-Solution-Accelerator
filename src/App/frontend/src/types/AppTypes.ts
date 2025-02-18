import { ReactNode } from "react";

export type FilterObject = {
  key: string;
  displayValue: string;
};
export type FilterMetaData = Record<string, FilterObject[]>;
export type SelectedFilters = Record<string, string | string[]>;

type Roles = "assistant" | "user" | "error";

export enum Feedback {
  Neutral = "neutral",
  Positive = "positive",
  Negative = "negative",
  MissingCitation = "missing_citation",
  WrongCitation = "wrong_citation",
  OutOfScope = "out_of_scope",
  InaccurateOrIrrelevant = "inaccurate_or_irrelevant",
  OtherUnhelpful = "other_unhelpful",
  HateSpeech = "hate_speech",
  Violent = "violent",
  Sexual = "sexual",
  Manipulative = "manipulative",
  OtherHarmful = "other_harmlful",
}

export type ChatMessage = {
  id: string;
  role: string;
  content: string | ChartDataResponse;
  end_turn?: boolean;
  date: string;
  feedback?: Feedback;
  context?: string;
  contentType?: "text" | "image";
  citations?: string
};

export type ConversationRequest = {
  id?: string;
  messages: ChatMessage[];
  last_rag_response: string | null;
};

export type AskResponse = {
  answer: string;
  citations: Citation[];
  error?: string;
};

export type Conversation = {
  id: string;
  title: string;
  messages: ChatMessage[];
  date: string;
  updatedAt?: string;
};

export type AppConfig = Record<
  string,
  Record<string, number> | Record<string, Record<string, number>>
> | null;

export interface ChartLayout {
  row: number;
  col: number;
  width?: string;
}
export interface ChartDataItem {
  [x: string]: any;
  name: string;
  count: number;
  value: string;
  text: string;
  size: number;
  color?: string;
  percentage?: number;
  description?: string;
  unit_of_measurement?: string;
  average_sentiment: "positive" | "negative" | "neutral";
}
export interface ChartConfigItem {
  type: string;
  title: string;
  data: ChartDataItem[];
  layout: ChartLayout;
  id: string;
  domId: string;
}

export enum ChatCompletionType {
  ChatCompletion = "chat.completion",
  ChatCompletionChunk = "chat.completion.chunk",
}

export type ChatResponseChoice = {
  messages: ChatMessage[];
};

export type ChartDataResponse = {
  data: any,
  options: any,
  type: string
};

export type ChatResponse = {
  id: string;
  model: string;
  created: number;
  object: ChatCompletionType | any;
  choices: ChatResponseChoice[];
  history_metadata: {
    conversation_id: string;
    title: string;
    date: string;
  };
  error?: any;
  chartType?: string;
  chartOptions: any;
  chartData: {
    datasets?: any[];
    labels: any[];
  };
};

export enum CosmosDBStatus {
  NotConfigured = "CosmosDB is not configured",
  NotWorking = "CosmosDB is not working",
  InvalidCredentials = "CosmosDB has invalid credentials",
  InvalidDatabase = "Invalid CosmosDB database name",
  InvalidContainer = "Invalid CosmosDB container name",
  Working = "CosmosDB is configured and working",
}

export type CosmosDBHealth = {
  cosmosDB: boolean;
  status: string;
};

export type HistoryMetaData = {
  conversation_id: string;
  title: string;
  date: string;
};

export type ParsedChunk = {
  error?: string;
  id: string;
  model: string;
  created: number;
  object: string;
  choices: [
    {
      messages: [
        {
          content: string;
          role: string;
        }
      ];
      history_metadata: object;
    }
  ];
  "apim-request-id": string;
};

export type ToolMessageContent = {
  citations: Citation[]
}

export type Citation = {
  content: string;
  id: string;
  title: string | null;
  filepath: string | null;
  url: string | null;
  metadata: string | null;
  chunk_id: string | null;
  reindex_id: string | null;
}