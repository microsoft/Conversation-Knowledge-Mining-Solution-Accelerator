import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export interface CitationState {
  activeCitation: any | null;
  showCitation: boolean;
  currentConversationIdForCitation: string;
}

const initialState: CitationState = {
  activeCitation: null,
  showCitation: false,
  currentConversationIdForCitation: "",
};

const citationSlice = createSlice({
  name: "citation",
  initialState,
  reducers: {
    updateCitation(
      state,
      action: PayloadAction<{
        activeCitation?: any;
        showCitation: boolean;
        currentConversationIdForCitation?: string;
      }>
    ) {
      state.activeCitation =
        action.payload.activeCitation ?? state.activeCitation;
      state.showCitation = action.payload.showCitation;
      state.currentConversationIdForCitation =
        action.payload.currentConversationIdForCitation ??
        state.currentConversationIdForCitation;
    },
  },
});

export const { updateCitation } = citationSlice.actions;
export default citationSlice.reducer;
