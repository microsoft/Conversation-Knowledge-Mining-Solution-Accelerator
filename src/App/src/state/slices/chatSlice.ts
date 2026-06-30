import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import { type ChatMessage } from "../../types/AppTypes";

export type ChatState = {
  generatingResponse: boolean;
  messages: ChatMessage[];
  userMessage: string;
  isStreamingInProgress: boolean;
  citations: string | null;
};

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
    setGeneratingResponse(state, action: PayloadAction<boolean>) {
      state.generatingResponse = action.payload;
    },
    setMessages(state, action: PayloadAction<ChatMessage[]>) {
      state.messages = action.payload;
    },
    appendMessages(state, action: PayloadAction<ChatMessage[]>) {
      state.messages.push(...action.payload);
    },
    setUserMessage(state, action: PayloadAction<string>) {
      state.userMessage = action.payload;
    },
    updateMessageById(state, action: PayloadAction<ChatMessage>) {
      const messageIndex = state.messages.findIndex(
        (message) => message.id === action.payload.id
      );

      if (messageIndex === -1) {
        state.messages.push(action.payload);
        return;
      }

      state.messages[messageIndex] = {
        ...state.messages[messageIndex],
        ...action.payload,
      };
    },
    setStreamingInProgress(state, action: PayloadAction<boolean>) {
      state.isStreamingInProgress = action.payload;
    },
    setChatCitations(state, action: PayloadAction<string | null>) {
      state.citations = action.payload;
    },
    resetChatState() {
      return { ...initialState };
    },
  },
});

export const {
  setGeneratingResponse,
  setMessages,
  appendMessages,
  setUserMessage,
  updateMessageById,
  setStreamingInProgress,
  setChatCitations,
  resetChatState,
} = chatSlice.actions;

export default chatSlice.reducer;
