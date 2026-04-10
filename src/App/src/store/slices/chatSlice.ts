import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { ChatMessage } from "../../types/AppTypes";
import {
  loadConversation,
  deleteConversation,
  clearAllChatHistory,
} from "../thunks/chatHistoryThunks";

export interface ChatState {
  generatingResponse: boolean;
  messages: ChatMessage[];
  userMessage: string;
  isStreamingInProgress: boolean;
  citations: string | null;
}

const initialState: ChatState = {
  generatingResponse: false,
  messages: [],
  userMessage: "",
  citations: "",
  isStreamingInProgress: false,
};

const chatSlice = createSlice({
  name: "chat",
  initialState,
  reducers: {
    setUserMessage(state, action: PayloadAction<string>) {
      state.userMessage = action.payload;
    },
    setGeneratingResponse(state, action: PayloadAction<boolean>) {
      state.generatingResponse = action.payload;
    },
    appendMessages(state, action: PayloadAction<ChatMessage[]>) {
      state.messages.push(...action.payload);
    },
    updateMessageById(state, action: PayloadAction<ChatMessage>) {
      const messageID = action.payload.id;
      const matchIndex = state.messages.findIndex(
        (obj) => String(obj.id) === String(messageID)
      );
      if (matchIndex > -1) {
        state.messages[matchIndex] = action.payload;
      } else {
        state.messages.push(action.payload);
      }
      state.citations = "";
      state.isStreamingInProgress = true;
    },
    setStreamingFlag(state, action: PayloadAction<boolean>) {
      state.isStreamingInProgress = action.payload;
    },
    clearMessages(state) {
      state.messages = [];
    },
    setMessages(state, action: PayloadAction<ChatMessage[]>) {
      state.messages = action.payload;
    },
  },
  extraReducers: (builder) => {
    // ── loadConversation ──
    builder.addCase(loadConversation.fulfilled, (state, action) => {
      state.messages = action.payload.messages;
    });

    // ── deleteConversation ──
    builder.addCase(deleteConversation.fulfilled, (state, action) => {
      if (action.payload.wasSelected) {
        state.messages = [];
        state.userMessage = "";
      }
    });

    // ── clearAllChatHistory ──
    builder.addCase(clearAllChatHistory.fulfilled, (state) => {
      state.messages = [];
    });
  },
});

export const {
  setUserMessage,
  setGeneratingResponse,
  appendMessages,
  updateMessageById,
  setStreamingFlag,
  clearMessages,
  setMessages,
} = chatSlice.actions;

export default chatSlice.reducer;
