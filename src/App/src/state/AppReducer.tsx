import { generateUUIDv4 } from "../configs/Utils";
import { actionConstants } from "./ActionConstants";
import { Action, type AppState } from "./AppProvider";

const appReducer = (state: AppState, action: Action): AppState => {
  switch (action.type) {
    case actionConstants.SET_FILTERS:
      return {
        ...state,
        dashboards: { ...state.dashboards, filtersMeta: action.payload },
      };
    case actionConstants.UPDATE_FILTERS_FETCHED_FLAG:
      return {
        ...state,
        dashboards: { ...state.dashboards, filtersMetaFetched: action.payload },
      };
    case actionConstants.UPDATE_CHARTS_DATA:
      return {
        ...state,
        dashboards: { ...state.dashboards, charts: action.payload },
      };
    case actionConstants.UPDATE_INITIAL_CHARTS_FETCHED_FLAG:
      return {
        ...state,
        dashboards: {
          ...state.dashboards,
          initialChartsDataFetched: action.payload,
        },
      };
    case actionConstants.UPDATE_SELECTED_FILTERS:
      return {
        ...state,
        dashboards: {
          ...state.dashboards,
          selectedFilters: action.payload,
        },
      };
    case actionConstants.UPDATE_USER_MESSAGE:
      return {
        ...state,
        chat: {
          ...state.chat,
          userMessage: action.payload,
        },
      };
    case actionConstants.UPDATE_GENERATING_RESPONSE_FLAG:
      return {
        ...state,
        chat: {
          ...state.chat,
          generatingResponse: action.payload,
        },
      };
    case actionConstants.UPDATE_MESSAGES:
      return {
        ...state,
        chat: {
          ...state.chat,
          messages: [...state.chat.messages, ...action.payload],
        },
      };
    case actionConstants.ADD_CONVERSATIONS_TO_LIST:
      return {
        ...state,
        chatHistory: {
          ...state.chatHistory,
          list: [...state.chatHistory.list, ...action.payload],
        },
      };
    case actionConstants.SAVE_CONFIG:
      return {
        ...state,
        config: {
          ...state.config,
          ...action.payload,
        },
      };
    case actionConstants.UPDATE_SELECTED_CONV_ID:
      return {
        ...state,
        selectedConversationId: action.payload,
      };
    case actionConstants.UPDATE_GENERATED_CONV_ID:
      return {
        ...state,
        generatedConversationId: generateUUIDv4(),
      };
    case actionConstants.NEW_CONVERSATION_START:
      return {
        ...state,
        chat: { ...state.chat, messages: [], lastRagResponse: null },
        selectedConversationId: "",
        generatedConversationId: generateUUIDv4(),
      };
    case actionConstants.UPDATE_CONVERSATIONS_FETCHING_FLAG:
      return {
        ...state,
        chatHistory: {
          ...state.chatHistory,
          fetchingConversations: action.payload,
        },
      };
    case actionConstants.UPDATE_CONVERSATION_TITLE:
      const tempConvsList = [...state.chatHistory.list];
      const index = tempConvsList.findIndex(
        (obj) => obj.id === action.payload.id
      );
      if (index > -1) {
        tempConvsList[index].title = action.payload.newTitle;
      }
      return {
        ...state,
        chatHistory: {
          ...state.chatHistory,
          list: [...tempConvsList],
        },
      };
    case actionConstants.UPDATE_ON_CLEAR_ALL_CONVERSATIONS:
      return {
        ...state,
        chatHistory: {
          ...state.chatHistory,
          list: [],
        },
        chat: { ...state.chat, messages: [] },
        selectedConversationId: "",
        generatedConversationId: generateUUIDv4(),
      };
    case actionConstants.SHOW_CHATHISTORY_CONVERSATION:
      const tempConvList = [...state.chatHistory.list];
      const matchedIndex = tempConvList.findIndex(
        (obj) => obj.id === action.payload.id
      );
      if (matchedIndex > -1) {
        // Update the messages of the matched conversation
        tempConvList[matchedIndex].messages = action.payload.messages;
      }
      return {
        ...state,
        chat: { ...state.chat, messages: action.payload.messages },
        chatHistory: {
          ...state.chatHistory,
          list: tempConvList,
        },
      };
    case actionConstants.UPDATE_CHATHISTORY_CONVERSATION_FLAG:
      return {
        ...state,
        chatHistory: {
          ...state.chatHistory,
          isFetchingConvMessages: action.payload,
        },
      };
    case actionConstants.DELETE_CONVERSATION_FROM_LIST:
      const updatedChatHistoryList = state.chatHistory.list.filter(
        (conversation) => conversation.id !== action.payload
      );
      const isDeletedSelectedConv =
        action.payload === state.selectedConversationId;

      return {
        ...state,
        chatHistory: {
          ...state.chatHistory,
          list: updatedChatHistoryList,
        },
        selectedConversationId: isDeletedSelectedConv
          ? ""
          : state.selectedConversationId,
        chat: {
          ...state.chat,
          messages: isDeletedSelectedConv ? [] : state.chat.messages,
          userMessage: isDeletedSelectedConv ? "" : state.chat.userMessage,
        },
      };
    case actionConstants.STORE_COSMOS_INFO:
      return {
        ...state,
        cosmosInfo: action.payload,
      };
    case actionConstants.ADD_NEW_CONVERSATION_TO_CHAT_HISTORY:
      return {
        ...state,
        chatHistory: {
          ...state.chatHistory,
          list: [action.payload, ...state.chatHistory.list],
        },
      };
    case actionConstants.UPDATE_APP_SPINNER_STATUS:
      return {
        ...state,
        showAppSpinner: action.payload,
      };
    case actionConstants.UPDATE_HISTORY_UPDATE_API_FLAG:
      return {
        ...state,
        chatHistory: {
          ...state.chatHistory,
          isHistoryUpdateAPIPending: action.payload,
        },
      };
    case actionConstants.SET_LAST_RAG_RESPONSE:
      return {
        ...state,
        chat: {
          ...state.chat,
          lastRagResponse: action.payload,
        },
      };
    case actionConstants.UPDATE_MESSAGE_BY_ID:
      const messageID = action.payload.id;
      // console.log("aaction::",action.payload)
      const matchIndex = state.chat.messages.findIndex(
        (obj) => String(obj.id) === String(messageID)
      );
      let tempMessages = [...state.chat.messages];
      if (matchIndex > -1) {
        tempMessages[matchIndex] = action.payload;
      } else {
        tempMessages = [...state.chat.messages, action.payload];
      }
      return {
        ...state,
        chat: {
          ...state.chat,
          messages: tempMessages,
          citations: "",
          isStreamingInProgress: true,
        },
      };
    case actionConstants.UPDATE_STREAMING_FLAG:
      return {
        ...state,
        chat: {
          ...state.chat,
          isStreamingInProgress: action.payload,
        },
      };
    case actionConstants.UPDATE_CHARTS_FETCHING_FLAG:
      return {
        ...state,
        dashboards: {
          ...state.dashboards,
          fetchingCharts: action.payload,
        },
      };
    case actionConstants.UPDATE_FILTERS_FETCHING_FLAG:
      return {
        ...state,
        dashboards: {
          ...state.dashboards,
          fetchingFilters: action.payload,
        },
      };
      case actionConstants.UPDATE_CITATION:
      return {
        ...state,
        citation: {
          ...state.citation,
          activeCitation: action.payload.activeCitation || state.citation.activeCitation,   
          showCitation: action.payload.showCitation,
          currentConversationIdForCitation: action.payload?.currentConversationIdForCitation || state.citation.currentConversationIdForCitation,
        },
      };
    default:
      return state;
  }
};

export { appReducer };
