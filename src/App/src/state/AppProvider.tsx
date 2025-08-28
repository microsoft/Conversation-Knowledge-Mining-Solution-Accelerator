import { useReducer, createContext, type ReactNode, useEffect } from "react";
import {
  type AppConfig,
  type ChartConfigItem,
  type ChatMessage,
  type Conversation,
  type CosmosDBHealth,
  CosmosDBStatus,
  type FilterMetaData,
  type SelectedFilters,
} from "../types/AppTypes";
import { appReducer } from "./AppReducer";
import { actionConstants } from "./ActionConstants";
import { defaultSelectedFilters, generateUUIDv4 } from "../configs/Utils";
import { historyEnsure } from "../api/api";

export type AppState = {
  dashboards: {
    filtersMetaFetched: boolean;
    initialChartsDataFetched: boolean;
    filtersMeta: FilterMetaData;
    charts: ChartConfigItem[];
    selectedFilters: SelectedFilters;
    fetchingFilters: boolean;
    fetchingCharts: boolean
  };
  chat: {
    generatingResponse: boolean;
    messages: ChatMessage[];
    userMessage: string;
    lastRagResponse: string | null;
    isStreamingInProgress: boolean;
    citations: string |null;
  };
  citation: {
    activeCitation?: any;
    showCitation: boolean;
    currentConversationIdForCitation?: string;
  };
  chatHistory: {
    list: Conversation[];
    fetchingConversations: boolean;
    isFetchingConvMessages: boolean;
    isHistoryUpdateAPIPending: boolean;
  };
  selectedConversationId: string;
  generatedConversationId: string;
  config: {
    appConfig: AppConfig;
    charts: ChartConfigItem[];
  };
  cosmosInfo: CosmosDBHealth;
  showAppSpinner: boolean;
};

const initialState: AppState = {
  dashboards: {
    filtersMetaFetched: false,
    initialChartsDataFetched: false,
    filtersMeta: {
      Sentiment: [],
      Topic: [],
      DateRange: [],
    },
    charts: [],
    selectedFilters: { ...defaultSelectedFilters },
    fetchingCharts: true,
    fetchingFilters: true
  },
  chat: {
    generatingResponse: false,
    messages: [],
    userMessage: "",
    lastRagResponse: null,
    citations: "",
    isStreamingInProgress: false,
  },
  citation: {
    activeCitation: null,
    showCitation: false,
    currentConversationIdForCitation: '',
  },
  chatHistory: {
    list: [],
    fetchingConversations: false,
    isFetchingConvMessages: false,
    isHistoryUpdateAPIPending: false,
  },
  selectedConversationId: "",
  generatedConversationId: generateUUIDv4(),
  config: {
    appConfig: null,
    charts: [],
  },
  cosmosInfo: { cosmosDB: false, status: "" },
  showAppSpinner: false,
};

export type Action =
  | {
      type: typeof actionConstants.SET_FILTERS;
      payload: FilterMetaData;
    }
  | {
      type: typeof actionConstants.UPDATE_FILTERS_FETCHED_FLAG;
      payload: boolean;
    }
  | {
      type: typeof actionConstants.UPDATE_CHARTS_DATA;
      payload: ChartConfigItem[];
    }
  | {
      type: typeof actionConstants.UPDATE_INITIAL_CHARTS_FETCHED_FLAG;
      payload: boolean;
    }
  | {
      type: typeof actionConstants.UPDATE_SELECTED_FILTERS;
      payload: SelectedFilters;
    }
  | {
      type: typeof actionConstants.UPDATE_USER_MESSAGE;
      payload: string;
    }
  | {
      type: typeof actionConstants.UPDATE_GENERATING_RESPONSE_FLAG;
      payload: boolean;
    }
  | {
      type: typeof actionConstants.UPDATE_MESSAGES;
      payload: ChatMessage[];
    }
  | {
      type: typeof actionConstants.ADD_CONVERSATIONS_TO_LIST;
      payload: Conversation[];
    }
  | {
      type: typeof actionConstants.SAVE_CONFIG;
      payload: AppState["config"];
    }
  | {
      type: typeof actionConstants.UPDATE_SELECTED_CONV_ID;
      payload: string;
    }
  | {
      type: typeof actionConstants.UPDATE_GENERATED_CONV_ID;
      payload: string;
    }
  | {
      type: typeof actionConstants.NEW_CONVERSATION_START;
    }
  | {
      type: typeof actionConstants.UPDATE_CONVERSATIONS_FETCHING_FLAG;
      payload: boolean;
    }
  | {
      type: typeof actionConstants.UPDATE_CONVERSATION_TITLE;
      payload: { id: string; newTitle: string };
    }
  | {
      type: typeof actionConstants.UPDATE_ON_CLEAR_ALL_CONVERSATIONS;
    }
  | {
      type: typeof actionConstants.SHOW_CHATHISTORY_CONVERSATION;
      payload: { id: string; messages: ChatMessage[] };
    }
  | {
      type: typeof actionConstants.UPDATE_CHATHISTORY_CONVERSATION_FLAG;
      payload: boolean;
    }
  | {
      type: typeof actionConstants.DELETE_CONVERSATION_FROM_LIST;
      payload: string;
    }
  | {
      type: typeof actionConstants.STORE_COSMOS_INFO;
      payload: CosmosDBHealth;
    }
  | {
      type: typeof actionConstants.ADD_NEW_CONVERSATION_TO_CHAT_HISTORY;
      payload: Conversation;
    }
  | {
      type: typeof actionConstants.UPDATE_APP_SPINNER_STATUS;
      payload: boolean;
    }
  | {
      type: typeof actionConstants.UPDATE_HISTORY_UPDATE_API_FLAG;
      payload: boolean;
    }
  | {
      type: typeof actionConstants.SET_LAST_RAG_RESPONSE;
      payload: string | null;
    }
  | {
      type: typeof actionConstants.UPDATE_MESSAGE_BY_ID;
      payload: ChatMessage;
    }
  | {
      type: typeof actionConstants.UPDATE_STREAMING_FLAG;
      payload: boolean;
    }
  | {
      type: typeof actionConstants.UPDATE_CHARTS_FETCHING_FLAG;
      payload: boolean;
    }
  | {
      type: typeof actionConstants.UPDATE_FILTERS_FETCHING_FLAG;
      payload: boolean;
    }
  | {
    type: typeof actionConstants.UPDATE_CITATION;
    payload: {activeCitation?: any, showCitation: boolean, currentConversationIdForCitation?: string};
  };

export const AppContext = createContext<{
  state: AppState;
  dispatch: React.Dispatch<Action>;
}>({ state: initialState, dispatch: () => {} });

export const AppProvider = ({ children }: { children: ReactNode }) => {
  const [state, dispatch] = useReducer(appReducer, initialState);

  useEffect(() => {
    const getHistoryEnsure = async () => {
      // dispatch({ type: 'UPDATE_CHAT_HISTORY_LOADING_STATE', payload: ChatHistoryLoadingState.Loading })
      historyEnsure()
        .then((response) => {
          if (response?.cosmosDB) {
            console.log("COSMOS DB IS OKAY ");
            dispatch({
              type: actionConstants.STORE_COSMOS_INFO,
              payload: response,
            });
            // fetchChatHistory()
            //   .then(res => {
            //     if (res) {
            //       // dispatch({ type: 'UPDATE_CHAT_HISTORY_LOADING_STATE', payload: ChatHistoryLoadingState.Success })
            //     } else {
            //       // dispatch({ type: 'UPDATE_CHAT_HISTORY_LOADING_STATE', payload: ChatHistoryLoadingState.Fail })
            //       // dispatch({
            //       //   type: 'SET_COSMOSDB_STATUS',
            //       //   payload: { cosmosDB: false, status: CosmosDBStatus.NotWorking }
            //       // })
            //     }
            //   })
            //   .catch(_err => {
            //     // dispatch({ type: 'UPDATE_CHAT_HISTORY_LOADING_STATE', payload: ChatHistoryLoadingState.Fail })
            //     // dispatch({
            //     //   type: 'SET_COSMOSDB_STATUS',
            //     //   payload: { cosmosDB: false, status: CosmosDBStatus.NotWorking }
            //     // })
            //   })
          } else {
            dispatch({
              type: actionConstants.STORE_COSMOS_INFO,
              payload: response,
            });
          }
        })
        .catch((_err) => {
          dispatch({
            type: actionConstants.STORE_COSMOS_INFO,
            payload: { cosmosDB: false, status: CosmosDBStatus.NotConfigured },
          });
        });
    };
    // getHistoryEnsure();
  }, []);

  return (
    <AppContext.Provider value={{ state, dispatch: dispatch }}>
      {children}
    </AppContext.Provider>
  );
};

export default AppProvider;
