import {
  createAsyncThunk,
  createSlice,
  type PayloadAction,
} from "@reduxjs/toolkit";
import {
  historyDelete,
  historyDeleteAll,
  historyList,
  historyRead,
  historyRename,
} from "../../api/api";
import { type ChatMessage, type Conversation } from "../../types/AppTypes";

export type ChatHistoryState = {
  list: Conversation[];
  fetchingConversations: boolean;
  isFetchingConvMessages: boolean;
  isHistoryUpdateAPIPending: boolean;
};

const initialState: ChatHistoryState = {
  list: [],
  fetchingConversations: false,
  isFetchingConvMessages: false,
  isHistoryUpdateAPIPending: false,
};

export const fetchConversations = createAsyncThunk<
  Conversation[],
  number,
  { rejectValue: string }
>("chatHistory/fetchConversations", async (offset, { rejectWithValue }) => {
  const conversations = await historyList(offset);

  if (!conversations) {
    return rejectWithValue("Unable to load conversations.");
  }

  return conversations;
});

export const fetchConversationMessages = createAsyncThunk<
  { id: string; messages: ChatMessage[] },
  string,
  { rejectValue: string }
>(
  "chatHistory/fetchConversationMessages",
  async (conversationId, { rejectWithValue }) => {
    try {
      const messages = await historyRead(conversationId);
      return { id: conversationId, messages };
    } catch {
      return rejectWithValue("Unable to load conversation messages.");
    }
  }
);

export const renameConversation = createAsyncThunk<
  { id: string; newTitle: string },
  { id: string; newTitle: string },
  { rejectValue: string }
>("chatHistory/renameConversation", async ({ id, newTitle }, { rejectWithValue }) => {
  const response = await historyRename(id, newTitle);

  if (!response.ok) {
    return rejectWithValue("Unable to rename conversation.");
  }

  return { id, newTitle };
});

export const deleteConversation = createAsyncThunk<
  string,
  string,
  { rejectValue: string }
>("chatHistory/deleteConversation", async (conversationId, { rejectWithValue }) => {
  const response = await historyDelete(conversationId);

  if (!response.ok) {
    return rejectWithValue("Unable to delete conversation.");
  }

  return conversationId;
});

export const clearAllConversations = createAsyncThunk<
  void,
  void,
  { rejectValue: string }
>("chatHistory/clearAllConversations", async (_, { rejectWithValue }) => {
  const response = await historyDeleteAll();

  if (!response.ok) {
    return rejectWithValue("Unable to clear chat history.");
  }
});

const chatHistorySlice = createSlice({
  name: "chatHistory",
  initialState,
  reducers: {
    setFetchingConversations(state, action: PayloadAction<boolean>) {
      state.fetchingConversations = action.payload;
    },
    setConversationMessagesFetching(state, action: PayloadAction<boolean>) {
      state.isFetchingConvMessages = action.payload;
    },
    setHistoryUpdateApiPending(state, action: PayloadAction<boolean>) {
      state.isHistoryUpdateAPIPending = action.payload;
    },
    addConversationToHistory(state, action: PayloadAction<Conversation>) {
      const existingConversation = state.list.find(
        (conversation) => conversation.id === action.payload.id
      );

      if (!existingConversation) {
        state.list.unshift(action.payload);
      }
    },
    appendConversations(state, action: PayloadAction<Conversation[]>) {
      const existingIds = new Set(state.list.map((conversation) => conversation.id));
      action.payload.forEach((conversation) => {
        if (!existingIds.has(conversation.id)) {
          state.list.push(conversation);
          existingIds.add(conversation.id);
        }
      });
    },
    updateConversationTitleInState(
      state,
      action: PayloadAction<{ id: string; newTitle: string }>
    ) {
      const targetConversation = state.list.find(
        (conversation) => conversation.id === action.payload.id
      );

      if (targetConversation) {
        targetConversation.title = action.payload.newTitle;
      }
    },
    removeConversationFromList(state, action: PayloadAction<string>) {
      state.list = state.list.filter(
        (conversation) => conversation.id !== action.payload
      );
    },
    clearChatHistoryState(state) {
      state.list = [];
      state.fetchingConversations = false;
      state.isFetchingConvMessages = false;
      state.isHistoryUpdateAPIPending = false;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchConversations.pending, (state) => {
        state.fetchingConversations = true;
      })
      .addCase(fetchConversations.fulfilled, (state, action) => {
        state.fetchingConversations = false;
        const existingIds = new Set(state.list.map((conversation) => conversation.id));

        action.payload.forEach((conversation) => {
          if (!existingIds.has(conversation.id)) {
            state.list.push(conversation);
            existingIds.add(conversation.id);
          }
        });
      })
      .addCase(fetchConversations.rejected, (state) => {
        state.fetchingConversations = false;
      })
      .addCase(fetchConversationMessages.pending, (state) => {
        state.isFetchingConvMessages = true;
      })
      .addCase(fetchConversationMessages.fulfilled, (state, action) => {
        state.isFetchingConvMessages = false;
        const conversation = state.list.find(
          (item) => item.id === action.payload.id
        );

        if (conversation) {
          conversation.messages = action.payload.messages;
        }
      })
      .addCase(fetchConversationMessages.rejected, (state) => {
        state.isFetchingConvMessages = false;
      })
      .addCase(renameConversation.fulfilled, (state, action) => {
        const conversation = state.list.find(
          (item) => item.id === action.payload.id
        );

        if (conversation) {
          conversation.title = action.payload.newTitle;
        }
      })
      .addCase(deleteConversation.fulfilled, (state, action) => {
        state.list = state.list.filter(
          (conversation) => conversation.id !== action.payload
        );
      })
      .addCase(clearAllConversations.fulfilled, (state) => {
        state.list = [];
        state.fetchingConversations = false;
        state.isFetchingConvMessages = false;
        state.isHistoryUpdateAPIPending = false;
      });
  },
});

export const {
  setFetchingConversations,
  setConversationMessagesFetching,
  setHistoryUpdateApiPending,
  addConversationToHistory,
  appendConversations,
  updateConversationTitleInState,
  removeConversationFromList,
  clearChatHistoryState,
} = chatHistorySlice.actions;

export default chatHistorySlice.reducer;
