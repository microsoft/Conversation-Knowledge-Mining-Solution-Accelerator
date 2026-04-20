import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export type CitationState = {
  activeCitation?: unknown;
  showCitation: boolean;
  currentConversationIdForCitation?: string;
};

const initialState: CitationState = {
  activeCitation: null,
  showCitation: false,
  currentConversationIdForCitation: "",
};

const citationSlice = createSlice({
  name: "citation",
  initialState,
  reducers: {
    setCitationState(state, action: PayloadAction<Partial<CitationState>>) {
      Object.assign(state, action.payload);
    },
    hideCitation(state) {
      state.activeCitation = null;
      state.showCitation = false;
      state.currentConversationIdForCitation = "";
    },
  },
});

export const { setCitationState, hideCitation } = citationSlice.actions;

export default citationSlice.reducer;
