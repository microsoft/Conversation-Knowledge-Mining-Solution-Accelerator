import {
  historyListResponse,
  historyReadResponse,
} from "../configs/StaticData";
import {
  AppConfig,
  ChartConfigItem,
  ChatMessage,
  Conversation,
  ConversationRequest,
  CosmosDBHealth,
  CosmosDBStatus,
} from "../types/AppTypes";
import httpClient from "./httpClient";
import { createErrorResponse } from "../utils/apiUtils";

// ---------------------------------------------------------------------------
// Chart data
// ---------------------------------------------------------------------------

export const fetchChartData = async () => {
  try {
    return await httpClient.get("/api/fetchChartData");
  } catch (error) {
    console.error("Failed to fetch chart data:", error);
    throw error;
  }
};

export const fetchChartDataWithFilters = async (bodyData: any) => {
  try {
    return await httpClient.post("/api/fetchChartDataWithFilters", bodyData);
  } catch (error) {
    console.error("Failed to fetch filtered chart data:", error);
    throw error;
  }
};

export const fetchFilterData = async () => {
  try {
    return await httpClient.get("/api/fetchFilterData");
  } catch (error) {
    console.error("Failed to fetch filter data:", error);
    throw error;
  }
};

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export type UserInfo = {
  access_token: string;
  expires_on: string;
  id_token: string;
  provider_name: string;
  user_claims: any[];
  user_id: string;
};

export async function getUserInfo(): Promise<UserInfo[]> {
  try {
    // /.auth/me is an absolute path outside the API base URL
    const response = await fetch("/.auth/me");
    if (!response.ok) {
      console.error(
        "No identity provider found. Access to chat will be blocked."
      );
      return [];
    }
    const payload = await response.json();
    const userClaims = payload[0]?.user_claims || [];
    const objectIdClaim = userClaims.find(
      (claim: any) =>
        claim.typ ===
        "http://schemas.microsoft.com/identity/claims/objectidentifier"
    );
    const userId = objectIdClaim?.val;
    if (userId) {
      localStorage.setItem("userId", userId);
    }
    return payload;
  } catch {
    console.error("Failed to fetch user info");
    return [];
  }
}

// ---------------------------------------------------------------------------
// Conversation history
// ---------------------------------------------------------------------------

export const historyRead = async (convId: string): Promise<ChatMessage[]> => {
  try {
    const res = await httpClient.request<Response>("/history/read", {
      method: "POST",
      body: { conversation_id: convId },
      rawResponse: true,
    });

    if (!res.ok) {
      return historyReadResponse.messages.map((msg: any) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content.content,
        date: msg.createdAt,
        feedback: msg.feedback ?? undefined,
        context: msg.context,
        citations: msg.content.citations,
        contentType: msg.contentType,
      }));
    }

    const payload = await res.json();
    const messages: ChatMessage[] = [];
    if (Array.isArray(payload?.messages)) {
      payload.messages.forEach((msg: any) => {
        messages.push({
          id: msg.id,
          role: msg.role,
          content: msg.content.content,
          date: msg.createdAt,
          feedback: msg.feedback ?? undefined,
          context: msg.context,
          citations: msg.content.citations,
          contentType: msg.contentType,
        });
      });
    }
    return messages;
  } catch {
    return [];
  }
};

export const historyList = async (
  offset = 0
): Promise<Conversation[] | null> => {
  try {
    const payload = await httpClient.get("/history/list", {
      params: { offset },
    });
    if (!Array.isArray(payload)) {
      console.error("There was an issue fetching your data.");
      return null;
    }
    return payload.map((conv: any): Conversation => ({
      id: conv.id,
      title: conv.title,
      date: conv.createdAt,
      updatedAt: conv?.updatedAt,
      messages: [],
    }));
  } catch {
    console.error("There was an issue fetching your data.");
    return historyListResponse.map(
      (conv: any): Conversation => ({
        id: conv.id,
        title: conv.title,
        date: conv.createdAt,
        updatedAt: conv?.updatedAt,
        messages: [],
      })
    );
  }
};

export const historyUpdate = async (
  messages: ChatMessage[],
  convId: string
): Promise<Response> => {
  try {
    return await httpClient.request<Response>("/history/update", {
      method: "POST",
      body: { conversation_id: convId, messages },
      rawResponse: true,
    });
  } catch {
    return createErrorResponse();
  }
};

// ---------------------------------------------------------------------------
// Layout & config
// ---------------------------------------------------------------------------

export async function getLayoutConfig(): Promise<{
  appConfig: AppConfig;
  charts: ChartConfigItem[];
}> {
  try {
    const data = await httpClient.get("/api/layout-config");
    if (data) return data;
  } catch {
    console.error("Failed to parse Layout config data");
  }
  return { appConfig: null, charts: [] };
}

export async function getIsChartDisplayDefault(): Promise<{
  isChartDisplayDefault: boolean;
}> {
  try {
    const responseData = await httpClient.get("/api/display-chart-default");
    if (responseData) {
      const tempChartDisplayFlag =
        String(responseData.isChartDisplayDefault).toLowerCase() === "true";
      return { isChartDisplayDefault: tempChartDisplayFlag };
    }
  } catch {
    console.error("Failed to get chart config flag");
  }
  return { isChartDisplayDefault: true };
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

export async function callConversationApi(
  options: ConversationRequest,
  abortSignal: AbortSignal
): Promise<Response> {
  const response = await httpClient.request<Response>("/api/chat", {
    method: "POST",
    body: { query: options.query, conversation_id: options.id },
    signal: abortSignal,
    rawResponse: true,
    timeout: 0, // no client-side timeout – caller controls via abortSignal
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(JSON.stringify(errorData.error));
  }
  return response;
}

// ---------------------------------------------------------------------------
// History management
// ---------------------------------------------------------------------------

export const historyRename = async (
  convId: string,
  title: string
): Promise<Response> => {
  try {
    return await httpClient.request<Response>("/history/rename", {
      method: "POST",
      body: { conversation_id: convId, title },
      rawResponse: true,
    });
  } catch {
    return createErrorResponse();
  }
};

export const historyDelete = async (convId: string): Promise<Response> => {
  try {
    return await httpClient.request<Response>("/history/delete", {
      method: "DELETE",
      body: { conversation_id: convId },
      rawResponse: true,
    });
  } catch {
    return createErrorResponse();
  }
};

export const historyDeleteAll = async (): Promise<Response> => {
  try {
    return await httpClient.request<Response>("/history/delete_all", {
      method: "DELETE",
      body: {},
      rawResponse: true,
    });
  } catch {
    return createErrorResponse();
  }
};

export const historyEnsure = async (): Promise<CosmosDBHealth> => {
  try {
    const res = await httpClient.request<Response>("/history/ensure", {
      rawResponse: true,
    });
    const respJson = await res.json();
    let formattedResponse;
    if (respJson.message) {
      formattedResponse = CosmosDBStatus.Working;
    } else if (res.status === 500) {
      formattedResponse = CosmosDBStatus.NotWorking;
    } else if (res.status === 401) {
      formattedResponse = CosmosDBStatus.InvalidCredentials;
    } else if (res.status === 422) {
      formattedResponse = respJson.error;
    } else {
      formattedResponse = CosmosDBStatus.NotConfigured;
    }
    return {
      cosmosDB: res.ok,
      status: formattedResponse,
    };
  } catch (err) {
    console.error("There was an issue fetching your data.");
    return { cosmosDB: false, status: err instanceof Error ? err.message : String(err) };
  }
};

// ---------------------------------------------------------------------------
// Citations
// ---------------------------------------------------------------------------

export const fetchCitationContent = async (body: any) => {
  try {
    return await httpClient.post("/api/fetch-azure-search-content", body);
  } catch (error) {
    console.error("Failed to fetch azure search content:", error);
    throw error;
  }
};
