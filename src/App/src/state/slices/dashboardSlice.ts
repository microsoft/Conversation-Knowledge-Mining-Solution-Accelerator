import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import {
  type ChartConfigItem,
  type FilterMetaData,
  type SelectedFilters,
} from "../../types/AppTypes";
import { defaultSelectedFilters } from "../../configs/Utils";

export type DashboardState = {
  filtersMetaFetched: boolean;
  initialChartsDataFetched: boolean;
  filtersMeta: FilterMetaData;
  charts: ChartConfigItem[];
  selectedFilters: SelectedFilters;
  fetchingFilters: boolean;
  fetchingCharts: boolean;
};

const initialState: DashboardState = {
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
  fetchingFilters: true,
};

const dashboardSlice = createSlice({
  name: "dashboards",
  initialState,
  reducers: {
    setFiltersMeta(state, action: PayloadAction<FilterMetaData>) {
      state.filtersMeta = action.payload;
    },
    setFiltersMetaFetched(state, action: PayloadAction<boolean>) {
      state.filtersMetaFetched = action.payload;
    },
    setChartsData(state, action: PayloadAction<ChartConfigItem[]>) {
      state.charts = action.payload;
    },
    setInitialChartsDataFetched(state, action: PayloadAction<boolean>) {
      state.initialChartsDataFetched = action.payload;
    },
    setSelectedFilters(state, action: PayloadAction<SelectedFilters>) {
      state.selectedFilters = action.payload;
    },
    setFetchingCharts(state, action: PayloadAction<boolean>) {
      state.fetchingCharts = action.payload;
    },
    setFetchingFilters(state, action: PayloadAction<boolean>) {
      state.fetchingFilters = action.payload;
    },
    resetSelectedFilters(state) {
      state.selectedFilters = { ...defaultSelectedFilters };
    },
  },
});

export const {
  setFiltersMeta,
  setFiltersMetaFetched,
  setChartsData,
  setInitialChartsDataFetched,
  setSelectedFilters,
  setFetchingCharts,
  setFetchingFilters,
  resetSelectedFilters,
} = dashboardSlice.actions;

export default dashboardSlice.reducer;
