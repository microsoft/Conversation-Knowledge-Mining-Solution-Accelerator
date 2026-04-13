import { createAsyncThunk, createSlice, type PayloadAction } from "@reduxjs/toolkit";
import { generateUUIDv4 } from "../../configs/Utils";
import { getLayoutConfig, historyEnsure } from "../../api/api";
import {
  type AppConfig,
  type ChartConfigItem,
  type CosmosDBHealth,
} from "../../types/AppTypes";

export type AppSliceState = {
  selectedConversationId: string;
  generatedConversationId: string;
  config: {
    appConfig: AppConfig;
    charts: ChartConfigItem[];
  };
  cosmosInfo: CosmosDBHealth;
  showAppSpinner: boolean;
};

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

export const fetchLayoutConfig = createAsyncThunk(
  "app/fetchLayoutConfig",
  async () => getLayoutConfig()
);

export const ensureHistoryReady = createAsyncThunk(
  "app/ensureHistoryReady",
  async () => historyEnsure()
);

const appSlice = createSlice({
  name: "app",
  initialState,
  reducers: {
    setSelectedConversationId(state, action: PayloadAction<string>) {
      state.selectedConversationId = action.payload;
    },
    setGeneratedConversationId(state, action: PayloadAction<string>) {
      state.generatedConversationId = action.payload;
    },
    startNewConversation(state) {
      state.selectedConversationId = "";
      state.generatedConversationId = generateUUIDv4();
    },
    setShowAppSpinner(state, action: PayloadAction<boolean>) {
      state.showAppSpinner = action.payload;
    },
    setCosmosInfo(state, action: PayloadAction<CosmosDBHealth>) {
      state.cosmosInfo = action.payload;
    },
    setConfig(
      state,
      action: PayloadAction<{ appConfig: AppConfig; charts: ChartConfigItem[] }>
    ) {
      state.config = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchLayoutConfig.fulfilled, (state, action) => {
        state.config = action.payload;
      })
      .addCase(ensureHistoryReady.fulfilled, (state, action) => {
        state.cosmosInfo = action.payload;
      });
  },
});

export const {
  setSelectedConversationId,
  setGeneratedConversationId,
  startNewConversation,
  setShowAppSpinner,
  setCosmosInfo,
  setConfig,
} = appSlice.actions;

export default appSlice.reducer;
