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
const baseURL = process.env.REACT_APP_API_BASE_URL;// base API URL

export const fetchChartData = async () => {
  try {
    const response = await fetch(`${baseURL}/api/fetchChartData`);
    if (!response.ok) {
      throw new Error(`Error: ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Failed to fetch chart data:", error);
    throw error; // Rethrow the error so the calling function can handle it
  }
};

export const fetchChartDataWithFilters = async (bodyData: any) => {
  try {
    const response = await fetch(`${baseURL}/api/fetchChartDataWithFilters`, {
      headers: {
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify(bodyData),
    });
    if (!response.ok) {
      throw new Error(`Error: ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Failed to fetch filtered chart data:", error);
    throw error;
  }
};

export const fetchFilterData = async () => {
  try {
    const response = await fetch(`${baseURL}/api/fetchFilterData`);
    if (!response.ok) {
      throw new Error(`Error: ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Failed to fetch filter data:", error);
    throw error;
  }
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
  const response = await fetch(`/.auth/me`);
  if (!response.ok) {
    console.error("No identity provider found. Access to chat will be blocked.");
    return [];
  }
  const payload = await response.json();
  const userClaims = payload[0]?.user_claims || [];
  const objectIdClaim = userClaims.find(
    (claim: any) =>
      claim.typ === "http://schemas.microsoft.com/identity/claims/objectidentifier"
  );
  const userId = objectIdClaim?.val;
  if (userId) {
    localStorage.setItem("userId", userId);
  }
  return payload;
}


function getUserIdFromLocalStorage(): string | null {
  return localStorage.getItem("userId");
}

export const historyRead = async (convId: string): Promise<ChatMessage[]> => {
  const userId = getUserIdFromLocalStorage();
  const response = await fetch(`${baseURL}/history/read`, {
    method: "POST",
    body: JSON.stringify({
      conversation_id: convId,
    }),
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
  })
    .then(async (res) => {
      if (!res.ok) {
        return historyReadResponse.messages.map((msg: any) => ({
          id: msg.id,
          role: msg.role,
          content: msg.content.content,
          date: msg.createdAt,
          feedback: msg.feedback ?? undefined,
          context: msg.context,
          contentType: msg.contentType,
        }));
      }
      const payload = await res.json();
      const messages: ChatMessage[] = [];

      if (Array.isArray(payload?.messages)) {
        payload.messages.forEach((msg: any) => {
          const message: ChatMessage = {
            id: msg.id,
            role: msg.role,
            content: msg.content.content,
            date: msg.createdAt,
            feedback: msg.feedback ?? undefined,
            context: msg.context,
            citations: msg.content.citations,
            contentType: msg.contentType,
          };
          messages.push(message);
        });
      }
      return messages;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.");
      return [];
    });
  return response;
};

export const historyList = async (
  offset = 0
): Promise<Conversation[] | null> => {
  const userId = getUserIdFromLocalStorage();
  let response = await fetch(`${baseURL}/history/list?offset=${offset}`, {
    method: "GET",
  headers: {
    "Content-Type": "application/json",
    "X-Ms-Client-Principal-Id": userId || "",
  },
})
    .then(async (res) => {
      let payload = await res.json();
      if (!Array.isArray(payload)) {
        console.error("There was an issue fetching your data.");
        return null;
      }
      const conversations: Conversation[] = payload.map((conv: any) => {
        const conversation: Conversation = {
          id: conv.id,
          title: conv.title,
          date: conv.createdAt,
          updatedAt: conv?.updatedAt,
          messages: [],
        };
        return conversation;
      });
      return conversations;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.", _err);
      const conversations: Conversation[] = historyListResponse.map(
        (conv: any) => {
          const conversation: Conversation = {
            id: conv.id,
            title: conv.title,
            date: conv.createdAt,
            updatedAt: conv?.updatedAt,
            messages: [],
          };
          return conversation;
        }
      );
      return conversations;
    });
  return response;
};

export const historyUpdate = async (
  messages: ChatMessage[],
  convId: string
): Promise<Response> => {
  const userId = getUserIdFromLocalStorage();
  const response = await fetch(`${baseURL}/history/update`, {
    method: "POST",
    body: JSON.stringify({
      conversation_id: convId,
      messages: messages,
    }),
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
  })
    .then(async (res) => {
      return res;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.");
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500,
      };
      return errRes;
    });
  return response;
};

export async function getLayoutConfig(): Promise<{
  appConfig: AppConfig;
  charts: ChartConfigItem[];
}> {
  const userId = getUserIdFromLocalStorage();
  const response = await fetch(`${baseURL}/api/layout-config`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
  });
  try {
    if (response.ok) {
      const layoutConfigData = await response.json();
      return layoutConfigData;
    }
  } catch {
    console.error("Failed to parse Layout config data");
  }
  return {
    appConfig: null,
    charts: [],
  };
}

export async function getIsChartDisplayDefault(): Promise<{
  isChartDisplayDefault: boolean;
}> {
  const userId = getUserIdFromLocalStorage();
  const response = await fetch(`${baseURL}/api/display-chart-default`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
  });
  try {
    if (response.ok) {
      const responseData = await response.json();
      const tempChartDisplayFlag = responseData.isChartDisplayDefault.toLowerCase() == 'true' ? true : false
      return { isChartDisplayDefault: tempChartDisplayFlag }
    }
  } catch {
    console.error("Failed to get chart config flag");
  }
  return {
    isChartDisplayDefault: true
  };
}

export async function callConversationApi(
  options: ConversationRequest,
  abortSignal: AbortSignal
): Promise<Response> {
  const userId = getUserIdFromLocalStorage();
  const response = await fetch(`${baseURL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
    body: JSON.stringify({
      messages: options.messages,
      conversation_id: options.id,
      last_rag_response: options.last_rag_response
    }),
    signal: abortSignal,
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(JSON.stringify(errorData.error));
  }

  return response;
}

export const historyRename = async (
  convId: string,
  title: string
): Promise<Response> => {
  const userId = getUserIdFromLocalStorage();
  const response = await fetch(`${baseURL}/history/rename`, {
    method: "POST",
    body: JSON.stringify({
      conversation_id: convId,
      title: title,
    }),
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
  })
    .then((res) => {
      return res;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.");
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500,
      };
      return errRes;
    });
  return response;
};

export const historyDelete = async (convId: string): Promise<Response> => {
  const userId = getUserIdFromLocalStorage();
  const response = await fetch(`${baseURL}/history/delete`, {
    method: "DELETE",
    body: JSON.stringify({
      conversation_id: convId,
    }),
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
  })
    .then((res) => {
      return res;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.");
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500,
      };
      return errRes;
    });
  return response;
};

export const historyDeleteAll = async (): Promise<Response> => {
  const userId = getUserIdFromLocalStorage();
  const response = await fetch(`${baseURL}/history/delete_all`, {
    method: "DELETE",
    body: JSON.stringify({}),
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
  })
    .then((res) => {
      return res;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.");
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500,
      };
      return errRes;
    });
  return response;
};

export const historyEnsure = async (): Promise<CosmosDBHealth> => {
  const userId = getUserIdFromLocalStorage();
  const response = await fetch(`${baseURL}/history/ensure`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
  })
    .then(async (res) => {
      const respJson = await res.json();
      let formattedResponse;
      if (respJson.message) {
        formattedResponse = CosmosDBStatus.Working;
      } else {
        if (res.status === 500) {
          formattedResponse = CosmosDBStatus.NotWorking;
        } else if (res.status === 401) {
          formattedResponse = CosmosDBStatus.InvalidCredentials;
        } else if (res.status === 422) {
          formattedResponse = respJson.error;
        } else {
          formattedResponse = CosmosDBStatus.NotConfigured;
        }
      }
      if (!res.ok) {
        return {
          cosmosDB: false,
          status: formattedResponse,
        };
      } else {
        return {
          cosmosDB: true,
          status: formattedResponse,
        };
      }
    })
    .catch((err) => {
      console.error("There was an issue fetching your data.");
      return {
        cosmosDB: false,
        status: err,
      };
    });
  return response;
};

export const historyGenerate = async (
  options: ConversationRequest,
  abortSignal: AbortSignal,
  convId?: string
): Promise<Response> => {
  let body;
  if (convId) {
    body = JSON.stringify({
      conversation_id: convId,
      messages: options.messages,
    });
  } else {
    body = JSON.stringify({
      messages: options.messages,
    });
  }
  const userId = getUserIdFromLocalStorage();
  const response = await fetch(`${baseURL}/history/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Ms-Client-Principal-Id": userId || "",
    },
    body: body,
    signal: abortSignal,
  })
    .then((res) => {
      return res;
    })
    .catch((_err) => {
      console.error("There was an issue fetching your data.");
      return new Response();
    });
  return response;
};

export const fetchCitationContent = async (body: any) => {
  try {
    const response = await fetch(`${baseURL}/api/fetch-azure-search-content`, {
      headers: {
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error(`Error: ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Failed to fetch azure search content:", error);
    throw error;
  }
};
