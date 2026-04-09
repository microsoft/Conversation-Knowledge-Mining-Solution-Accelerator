import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type {
  AppConfig,
  ChartConfigItem,
  CosmosDBHealth,
} from "../../types/AppTypes";
import { generateUUIDv4 } from "../../utils/messageUtils";
import {
  loadConversation,
  deleteConversation,
  clearAllChatHistory,
} from "../thunks/chatHistoryThunks";

export interface AppSliceState {
  selectedConversationId: string;
  generatedConversationId: string;
  config: {
    appConfig: AppConfig;
    charts: ChartConfigItem[];
  };
  cosmosInfo: CosmosDBHealth;
  showAppSpinner: boolean;
}

const initialState: AppSliceState = {
  selectedConversationId: "",
  generatedConversationId: generateUUIDv4(),
  config: {
    appConfig: null,
    charts: [],
  },
  cosmosInfo: { cosmosDB: false, status: "" },
  showAppSpinner: false,
};

const appSlice = createSlice({
  name: "app",
  initialState,
  reducers: {
    setSelectedConversationId(state, action: PayloadAction<string>) {
      state.selectedConversationId = action.payload;
    },
    regenerateConversationId(state) {
      state.generatedConversationId = generateUUIDv4();
    },
    saveConfig(
      state,
      action: PayloadAction<{ appConfig: AppConfig; charts: ChartConfigItem[] }>
    ) {
      state.config = { ...state.config, ...action.payload };
    },
    storeCosmosInfo(state, action: PayloadAction<CosmosDBHealth>) {
      state.cosmosInfo = action.payload;
    },
    setAppSpinnerStatus(state, action: PayloadAction<boolean>) {
      state.showAppSpinner = action.payload;
    },
    newConversationStart(state) {
      state.selectedConversationId = "";
      state.generatedConversationId = generateUUIDv4();
    },
  },
  extraReducers: (builder) => {
    // ── loadConversation ──
    builder.addCase(loadConversation.pending, (state, action) => {
      state.selectedConversationId = action.meta.arg;
    });

    // ── deleteConversation ──
    builder
      .addCase(deleteConversation.pending, (state) => {
        state.showAppSpinner = true;
      })
      .addCase(deleteConversation.fulfilled, (state, action) => {
        if (action.payload.wasSelected) {
          state.selectedConversationId = "";
        }
        state.showAppSpinner = false;
      })
      .addCase(deleteConversation.rejected, (state) => {
        state.showAppSpinner = false;
      });

    // ── clearAllChatHistory ──
    builder
      .addCase(clearAllChatHistory.pending, (state) => {
        state.showAppSpinner = true;
      })
      .addCase(clearAllChatHistory.fulfilled, (state) => {
        state.selectedConversationId = "";
        state.generatedConversationId = generateUUIDv4();
        state.showAppSpinner = false;
      })
      .addCase(clearAllChatHistory.rejected, (state) => {
        state.showAppSpinner = false;
      });
  },
});

export const {
  setSelectedConversationId,
  regenerateConversationId,
  saveConfig,
  storeCosmosInfo,
  setAppSpinnerStatus,
  newConversationStart,
} = appSlice.actions;

export default appSlice.reducer;
