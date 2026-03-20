import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type {
  ChartConfigItem,
  FilterMetaData,
  SelectedFilters,
} from "../../types/AppTypes";
import { defaultSelectedFilters } from "../../utils/chartUtils";

export interface DashboardsState {
  filtersMetaFetched: boolean;
  initialChartsDataFetched: boolean;
  filtersMeta: FilterMetaData;
  charts: ChartConfigItem[];
  selectedFilters: SelectedFilters;
  fetchingFilters: boolean;
  fetchingCharts: boolean;
}

const initialState: DashboardsState = {
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

const dashboardsSlice = createSlice({
  name: "dashboards",
  initialState,
  reducers: {
    setFilters(state, action: PayloadAction<FilterMetaData>) {
      state.filtersMeta = action.payload;
    },
    setFiltersMetaFetched(state, action: PayloadAction<boolean>) {
      state.filtersMetaFetched = action.payload;
    },
    setChartsData(state, action: PayloadAction<ChartConfigItem[]>) {
      state.charts = action.payload;
    },
    setInitialChartsFetched(state, action: PayloadAction<boolean>) {
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
  },
});

export const {
  setFilters,
  setFiltersMetaFetched,
  setChartsData,
  setInitialChartsFetched,
  setSelectedFilters,
  setFetchingCharts,
  setFetchingFilters,
} = dashboardsSlice.actions;

export default dashboardsSlice.reducer;
