import {
  historyListResponse,
  historyReadResponse,
} from "../configs/StaticData";
import {
  type AppConfig,
  type ChartConfigItem,
  type ChatMessage,
  type Conversation,
  type ConversationRequest,
  type CosmosDBHealth,
  CosmosDBStatus,
} from "../types/AppTypes";
import httpClient from "./httpClient";
import {
  createErrorResponse,
  RequestCache,
  retryRequest,
} from "../utils/apiUtils";

const layoutConfigCache = new RequestCache<{
  appConfig: AppConfig;
  charts: ChartConfigItem[];
}>();

const mapConversation = (conversation: any): Conversation => ({
  id: conversation.id,
  title: conversation.title,
  date: conversation.createdAt,
  updatedAt: conversation?.updatedAt,
  messages: Array.isArray(conversation.messages) ? conversation.messages : [],
});

const mapHistoryMessage = (message: any): ChatMessage => ({
  id: message.id,
  role: message.role,
  content: message.content?.content ?? message.content,
  date: message.createdAt,
  feedback: message.feedback ?? undefined,
  context: message.context,
  citations: message.content?.citations ?? message.citations,
  contentType: message.contentType,
});

const parseResponseJson = async <T>(response: Response): Promise<T | null> => {
  try {
    return (await response.json()) as T;
  } catch {
    return null;
  }
};

export const fetchChartData = async () => {
  const response = await retryRequest(() => httpClient.get("/api/fetchChartData"));
  if (!response.ok) {
    throw new Error(`Error: ${response.status} ${response.statusText}`);
  }

  return response.json();
};

export const fetchChartDataWithFilters = async (bodyData: any) => {
  const response = await httpClient.post(
    "/api/fetchChartDataWithFilters",
    bodyData
  );

  if (!response.ok) {
    throw new Error(`Error: ${response.status} ${response.statusText}`);
  }

  return response.json();
};

export const fetchFilterData = async () => {
  const response = await httpClient.get("/api/fetchFilterData");
  if (!response.ok) {
    throw new Error(`Error: ${response.status} ${response.statusText}`);
  }

  return response.json();
};

export type UserInfo = {
  access_token: string;
  expires_on: string;
  id_token: string;
  provider_name: string;
  user_claims: any[];
  user_id: string;
};

export async function getUserInfo(): Promise<UserInfo[]> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 15000);
  let response: Response;

  try {
    response = await fetch(`${window.location.origin}/.auth/me`, {
      signal: controller.signal,
    });
  } catch {
    return [];
  } finally {
    window.clearTimeout(timeoutId);
  }

  if (!response.ok) {
    return [];
  }

  const payload = await parseResponseJson<UserInfo[]>(response);
  const userClaims = payload?.[0]?.user_claims ?? [];
  const objectIdClaim = userClaims.find(
    (claim: any) =>
      claim.typ === "http://schemas.microsoft.com/identity/claims/objectidentifier"
  );
  const userId = objectIdClaim?.val;

  if (userId) {
    localStorage.setItem("userId", userId);
  }

  return payload ?? [];
}

export const historyRead = async (convId: string): Promise<ChatMessage[]> => {
  try {
    const response = await retryRequest(() =>
      httpClient.post("/history/read", {
        conversation_id: convId,
      })
    );

    if (!response.ok) {
      return historyReadResponse.messages.map(mapHistoryMessage);
    }

    const payload = await parseResponseJson<{ messages?: any[] }>(response);
    return Array.isArray(payload?.messages)
      ? (payload?.messages ?? []).map(mapHistoryMessage)
      : [];
  } catch {
    return [];
  }
};

export const historyList = async (
  offset = 0
): Promise<Conversation[] | null> => {
  try {
    const response = await httpClient.get("/history/list", {
      params: { offset },
    });
    const payload = await parseResponseJson<any[]>(response);

    if (!Array.isArray(payload)) {
      return null;
    }

    return payload.map(mapConversation);
  } catch {
    return historyListResponse.map(mapConversation);
  }
};

export const historyUpdate = async (
  messages: ChatMessage[],
  convId: string
): Promise<Response> => {
  try {
    return await httpClient.post("/history/update", {
      conversation_id: convId,
      messages,
    });
  } catch {
    return createErrorResponse(500, "There was an issue updating chat history.");
  }
};

export async function getLayoutConfig(): Promise<{
  appConfig: AppConfig;
  charts: ChartConfigItem[];
}> {
  try {
    return await layoutConfigCache.getOrCreate("layout-config", async () => {
      const response = await httpClient.get("/api/layout-config");
      if (!response.ok) {
        return {
          appConfig: null,
          charts: [],
        };
      }

      const layoutConfigData = await parseResponseJson<{
        appConfig: AppConfig;
        charts: ChartConfigItem[];
      }>(response);

      return (
        layoutConfigData ?? {
          appConfig: null,
          charts: [],
        }
      );
    });
  } catch {
    layoutConfigCache.clear("layout-config");
    return {
      appConfig: null,
      charts: [],
    };
  }
}

export async function getIsChartDisplayDefault(): Promise<{
  isChartDisplayDefault: boolean;
}> {
  try {
    const response = await httpClient.get("/api/display-chart-default");
    if (!response.ok) {
      return { isChartDisplayDefault: true };
    }

    const responseData = await parseResponseJson<{
      isChartDisplayDefault?: string | boolean;
    }>(response);
    const rawValue = responseData?.isChartDisplayDefault;

    return {
      isChartDisplayDefault:
        typeof rawValue === "string"
          ? rawValue.toLowerCase() === "true"
          : Boolean(rawValue),
    };
  } catch {
    return {
      isChartDisplayDefault: true,
    };
  }
}

export async function callConversationApi(
  options: ConversationRequest,
  abortSignal: AbortSignal
): Promise<Response> {
  const response = await httpClient.post(
    "/api/chat",
    {
      query: options.query,
      conversation_id: options.id,
    },
    {
      signal: abortSignal,
      timeout: 120000,
    }
  );

  if (!response.ok) {
    const errorData = await parseResponseJson<{ error?: unknown }>(response);
    throw new Error(JSON.stringify(errorData?.error ?? "Chat request failed."));
  }

  return response;
}

export const historyRename = async (
  convId: string,
  title: string
): Promise<Response> => {
  try {
    return await httpClient.post("/history/rename", {
      conversation_id: convId,
      title,
    });
  } catch {
    return createErrorResponse(500, "There was an issue renaming the conversation.");
  }
};

export const historyDelete = async (convId: string): Promise<Response> => {
  try {
    return await httpClient.delete("/history/delete", {
      conversation_id: convId,
    });
  } catch {
    return createErrorResponse(500, "There was an issue deleting the conversation.");
  }
};

export const historyDeleteAll = async (): Promise<Response> => {
  try {
    return await httpClient.delete("/history/delete_all", {});
  } catch {
    return createErrorResponse(500, "There was an issue clearing chat history.");
  }
};

export const historyEnsure = async (): Promise<CosmosDBHealth> => {
  try {
    const response = await httpClient.get("/history/ensure");
    if (response.status === 404) {
      return {
        cosmosDB: false,
        status: CosmosDBStatus.NotConfigured,
      };
    }

    const responseJson = await parseResponseJson<{
      message?: string;
      error?: string;
    }>(response);

    let status: string = CosmosDBStatus.NotConfigured;
    if (responseJson?.message) {
      status = CosmosDBStatus.Working;
    } else if (response.status === 500) {
      status = CosmosDBStatus.NotWorking;
    } else if (response.status === 401) {
      status = CosmosDBStatus.InvalidCredentials;
    } else if (response.status === 422) {
      status = responseJson?.error ?? CosmosDBStatus.NotConfigured;
    }

    return {
      cosmosDB: response.ok,
      status,
    };
  } catch (error) {
    return {
      cosmosDB: false,
      status: error instanceof Error ? error.message : CosmosDBStatus.NotConfigured,
    };
  }
};

export const fetchCitationContent = async (body: any) => {
  const response = await httpClient.post("/api/fetch-azure-search-content", body);
  if (!response.ok) {
    throw new Error(`Error: ${response.status} ${response.statusText}`);
  }

  return response.json();
};
