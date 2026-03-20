import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { Conversation } from "../../types/AppTypes";
import {
  fetchChatHistory,
  loadConversation,
  deleteConversation,
  clearAllChatHistory,
  renameConversation,
} from "../thunks/chatHistoryThunks";

export interface ChatHistoryState {
  list: Conversation[];
  fetchingConversations: boolean;
  isFetchingConvMessages: boolean;
  isHistoryUpdateAPIPending: boolean;
}

const initialState: ChatHistoryState = {
  list: [],
  fetchingConversations: false,
  isFetchingConvMessages: false,
  isHistoryUpdateAPIPending: false,
};

const chatHistorySlice = createSlice({
  name: "chatHistory",
  initialState,
  reducers: {
    setHistoryUpdateAPIPending(state, action: PayloadAction<boolean>) {
      state.isHistoryUpdateAPIPending = action.payload;
    },
    addNewConversation(state, action: PayloadAction<Conversation>) {
      state.list.unshift(action.payload);
    },
  },
  extraReducers: (builder) => {
    // ── fetchChatHistory ──
    builder
      .addCase(fetchChatHistory.pending, (state) => {
        state.fetchingConversations = true;
      })
      .addCase(fetchChatHistory.fulfilled, (state, action) => {
        if (action.payload) {
          state.list.push(...action.payload);
        }
        state.fetchingConversations = false;
      })
      .addCase(fetchChatHistory.rejected, (state) => {
        state.fetchingConversations = false;
      });

    // ── loadConversation ──
    builder
      .addCase(loadConversation.pending, (state) => {
        state.isFetchingConvMessages = true;
      })
      .addCase(loadConversation.fulfilled, (state, action) => {
        const conv = state.list.find((c) => c.id === action.payload.id);
        if (conv) {
          conv.messages = action.payload.messages;
        }
        state.isFetchingConvMessages = false;
      })
      .addCase(loadConversation.rejected, (state) => {
        state.isFetchingConvMessages = false;
      });

    // ── deleteConversation ──
    builder.addCase(deleteConversation.fulfilled, (state, action) => {
      state.list = state.list.filter(
        (conv) => conv.id !== action.payload.convId
      );
    });

    // ── clearAllChatHistory ──
    builder.addCase(clearAllChatHistory.fulfilled, (state) => {
      state.list = [];
    });

    // ── renameConversation ──
    builder.addCase(renameConversation.fulfilled, (state, action) => {
      const conv = state.list.find((c) => c.id === action.payload.convId);
      if (conv) {
        conv.title = action.payload.title;
      }
    });
  },
});

export const {
  setHistoryUpdateAPIPending,
  addNewConversation,
} = chatHistorySlice.actions;

export default chatHistorySlice.reducer;
