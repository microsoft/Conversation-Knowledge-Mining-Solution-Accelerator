import { useCallback, useEffect, useState } from "react";
import {
  fetchChartData,
  fetchChartDataWithFilters,
  fetchFilterData,
} from "../../api/api";
import NoData from "../NoData/NoData";
import DonutChart from "../../chartComponents/DonutChart";
import BarChart from "../../chartComponents/HorizontalBarChart";
import WordCloudChart from "../../chartComponents/WordCloudChart";
import TopicTable from "../../chartComponents/TopicTable";
import Card from "../../chartComponents/Card";
import ChartFilter from "../ChartFilter/ChartFilter";

import "./Chart.css";
import {
  type ChartConfigItem,
  type FilterMetaData,
  type SelectedFilters,
} from "../../types/AppTypes";
import { useAppDispatch, useAppSelector } from "../../state/hooks";
import {
  setChartsData,
  setFetchingCharts,
  setFetchingFilters,
  setFiltersMeta,
  setFiltersMetaFetched,
  setInitialChartsDataFetched,
} from "../../state/slices/dashboardSlice";
import {
  ACCEPT_FILTERS,
  defaultSelectedFilters,
  getGridStyles,
} from "../../configs/Utils";
import { Subtitle2, Tag } from "@fluentui/react-components";
import { Spinner, SpinnerSize } from "@fluentui/react";
import { getSentimentColor } from "../../utils/chartUtils";

type ChartProps = {
  layoutWidthUpdated: boolean;
};

const Chart = ({ layoutWidthUpdated }: ChartProps) => {
  const dispatch = useAppDispatch();
  const charts = useAppSelector((state) => state.dashboards.charts);
  const fetchingCharts = useAppSelector(
    (state) => state.dashboards.fetchingCharts
  );
  const fetchingFilters = useAppSelector(
    (state) => state.dashboards.fetchingFilters
  );
  const filtersMetaFetched = useAppSelector(
    (state) => state.dashboards.filtersMetaFetched
  );
  const initialChartsDataFetched = useAppSelector(
    (state) => state.dashboards.initialChartsDataFetched
  );
  const configCharts = useAppSelector((state) => state.app.config.charts);

  const [appliedFetch, setAppliedFetch] = useState<boolean>(false);
  const [widgetsGapInPercentage] = useState<number>(1);
  const [, setWindowSize] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
  });

  const handleResize = useCallback(() => {
    setWindowSize({
      width: window.innerWidth,
      height: window.innerHeight,
    });
  }, []);

  useEffect(() => {
    requestAnimationFrame(() => {
      setTimeout(() => {
        setWindowSize({
          width: window.innerWidth,
          height: window.innerHeight,
        });
      }, 10);
    });
  }, [layoutWidthUpdated]);

  useEffect(() => {
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, [handleResize]);

  const getChartData = useCallback(
    async (requestBody?: SelectedFilters) => {
      dispatch(setFetchingCharts(true));
      const normalizedRequestBody = requestBody
        ? { ...requestBody }
        : undefined;

      if (
        String((normalizedRequestBody as any)?.Sentiment?.[0]).toLowerCase() ===
        "all"
      ) {
        (normalizedRequestBody as any).Sentiment = [];
      }

      try {
        const chartData = normalizedRequestBody
          ? await fetchChartDataWithFilters({
              selected_filters: normalizedRequestBody,
            })
          : await fetchChartData();

        const updatedCharts: ChartConfigItem[] = configCharts
          .map((configChart: any) => {
            if (!configChart?.id) {
              return null;
            }

            const apiData = chartData.find(
              (apiChart: any) =>
                apiChart.id?.toLowerCase() === configChart.id?.toLowerCase()
            );

            const configObject: ChartConfigItem = {
              id: configChart.id,
              domId: configChart.id.replace(/\s+/g, "_").toUpperCase(),
              type: configChart.type,
              title: apiData ? apiData.chart_name : configChart.name || "",
              data: apiData ? apiData.chart_value : [],
              layout: {
                row: configChart.layout?.row,
                col: configChart.layout?.column,
                ...configChart.layout,
              },
            };

            if (configChart.layout?.width) {
              configObject.layout.width = configChart.layout.width;
            }

            return configObject;
          })
          .filter((chart): chart is ChartConfigItem => chart !== null);

        dispatch(setChartsData(updatedCharts));
      } catch {
        dispatch(setChartsData([]));
      } finally {
        dispatch(setFetchingCharts(false));
      }
    },
    [configCharts, dispatch]
  );

  useEffect(() => {
    const loadData = async () => {
      try {
        if (!filtersMetaFetched) {
          dispatch(setFetchingFilters(true));
          const filterResponse = await fetchFilterData();
          const acceptedFilters: FilterMetaData = {};

          filterResponse?.forEach((filter: any) => {
            if (ACCEPT_FILTERS.includes(filter?.filter_name)) {
              acceptedFilters[filter.filter_name] = filter.filter_values;
            }
          });

          dispatch(setFiltersMeta(acceptedFilters));
          dispatch(setFiltersMetaFetched(true));
          dispatch(setFetchingFilters(false));
        }

        if (!initialChartsDataFetched) {
          await getChartData({ ...defaultSelectedFilters });
          dispatch(setInitialChartsDataFetched(true));
        }
      } catch {
        dispatch(setChartsData([]));
        dispatch(setFetchingFilters(false));
      }
    };

    if (configCharts.length > 0) {
      void loadData();
    }
  }, [
    configCharts.length,
    dispatch,
    filtersMetaFetched,
    getChartData,
    initialChartsDataFetched,
  ]);

  const applyFilters = useCallback(
    async (updatedFilters: SelectedFilters) => {
      setAppliedFetch(true);
      await getChartData(updatedFilters);
      setAppliedFetch(false);
    },
    [getChartData]
  );

  const renderChart = (chart: ChartConfigItem, heightInPixels: number) => {
    const hasData = chart.data && chart.data.length > 0;

    switch (chart.type) {
      case "card":
        return hasData ? (
          <Card
            value={chart.data?.[0]?.value || "0"}
            description={chart.data?.[0]?.name || ""}
            unit_of_measurement={chart.data?.[0]?.unit_of_measurement || ""}
            containerHeight={heightInPixels}
          />
        ) : (
          <NoData />
        );
      case "donutchart":
        return hasData ? (
          <DonutChart
            title={chart.title}
            data={chart.data.map((item) => ({
              label: item.name,
              value: parseInt(item.value) || 0,
              color: getSentimentColor(item.name.toLowerCase()),
            }))}
            containerHeight={heightInPixels}
            widthInPixels={document.getElementById(chart.domId)?.clientWidth ?? 0}
            containerID={chart.domId}
          />
        ) : (
          <div
            className="outerNoDataContainer"
            style={{
              height: `calc(${heightInPixels}px - 40px)`,
            }}
          >
            <NoData />
          </div>
        );
      case "bar":
        return hasData ? (
          <BarChart
            title={chart.title}
            data={chart.data.map((item) => ({
              category: item.name,
              value: parseFloat(item.value),
            }))}
            containerHeight={heightInPixels}
            containerID={chart.domId}
          />
        ) : (
          <div
            className="outerNoDataContainer"
            style={{
              height: `calc(${heightInPixels}px - 40px)`,
            }}
          >
            <NoData />
          </div>
        );
      case "table":
        return hasData ? (
          <TopicTable
            columns={["Topic", "Frequency", "Sentiment"]}
            columnKeys={["name", "call_frequency", "average_sentiment"]}
            rows={chart.data.map((item) => ({
              name: item.name,
              call_frequency: item.call_frequency,
              average_sentiment: item.average_sentiment,
            }))}
            containerHeight={heightInPixels}
          />
        ) : (
          <div
            className="outerNoDataContainer"
            style={{
              height: `calc(${heightInPixels}px - 40px)`,
            }}
          >
            <NoData />
          </div>
        );
      case "wordcloud":
        return hasData ? (
          <WordCloudChart
            title={chart.title}
            data={{
              words: chart.data.map((item) => ({
                text: item.text,
                size: item.size,
                average_sentiment: item.average_sentiment,
              })),
            }}
            widthInPixels={document.getElementById(chart.domId)?.clientWidth ?? 0}
            containerHeight={heightInPixels}
          />
        ) : (
          <div
            className="outerNoDataContainer"
            style={{
              height: `calc(${heightInPixels}px - 40px)`,
            }}
          >
            <NoData />
          </div>
        );
      default:
        return null;
    }
  };

  const getHeightInPixels = (vh: number) => (vh / 100) * window.innerHeight;

  const groupedByRows: Record<string, ChartConfigItem[]> = {};
  charts.forEach((chart) => {
    const rowValue = String(chart.layout?.row);
    if (!groupedByRows[rowValue]) {
      groupedByRows[rowValue] = [];
    }
    groupedByRows[rowValue].push(chart);
  });

  const showAIGeneratedContentMessage =
    (!fetchingCharts && !fetchingFilters) || appliedFetch;

  return (
    <>
      {fetchingCharts && !appliedFetch ? (
        <div className="chartsLoaderContainer">
          <Spinner size={SpinnerSize.small} aria-label="Fetching Charts data" />
          <div className="loaderText">Loading Please wait...</div>
        </div>
      ) : (
        <div
          className="all-widgets-container"
          style={{
            filter: `blur(${fetchingCharts && appliedFetch ? "1.5px" : "0px"})`,
          }}
        >
          {Object.values(groupedByRows).map((chartsList, index) => {
            const gridStyles = getGridStyles(
              [...chartsList],
              widgetsGapInPercentage
            );
            let heightInPixels = 240;

            if (
              gridStyles.gridTemplateRows &&
              !Number.isNaN(parseInt(gridStyles.gridTemplateRows))
            ) {
              const heightInVH = parseInt(gridStyles.gridTemplateRows);
              heightInPixels = getHeightInPixels(heightInVH);
            }

            return (
              <div
                key={index}
                className="chart-container"
                style={{ ...gridStyles, gridGap: `${widgetsGapInPercentage}%` }}
              >
                {chartsList
                  .sort((a, b) => a.layout.col - b.layout.col)
                  .map((chart) => (
                    <div
                      key={chart.title}
                      id={chart.domId}
                      className={`chart-item ${chart.type}Container`}
                    >
                      <Subtitle2 className="chart-title">
                        {chart.title}
                      </Subtitle2>
                      {renderChart(chart, heightInPixels)}
                    </div>
                  ))}
              </div>
            );
          })}
        </div>
      )}

      {showAIGeneratedContentMessage && (
        <div style={{ textAlign: "center", gap: "2px" }}>
          <Tag size="extra-small" shape="circular">
            AI-generated content may be incorrect
          </Tag>
        </div>
      )}
      {!fetchingFilters && (
        <ChartFilter
          applyFilters={applyFilters}
          acceptFilters={ACCEPT_FILTERS}
          fetchingCharts={fetchingCharts}
        />
      )}
    </>
  );
};

export default Chart;
