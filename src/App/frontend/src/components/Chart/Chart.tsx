import { useEffect, useLayoutEffect, useState } from "react";
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
  SelectedFilters,
  type FilterMetaData,
} from "../../types/AppTypes";
import { useAppContext } from "../../state/useAppContext";
import { actionConstants } from "../../state/ActionConstants";
import {
  ACCEPT_FILTERS,
  defaultSelectedFilters,
  getGridStyles,
} from "../../configs/Utils";
// import { ChartsResponse } from "../../configs/StaticData";
import { Subtitle2, Tag } from "@fluentui/react-components";
import { Spinner, SpinnerSize } from "@fluentui/react";
// import { ChartsResponse } from "../../configs/StaticData";

type ChartProps = {
  layoutWidthUpdated: boolean;
};

const Chart = (props: ChartProps) => {
  const { state, dispatch } = useAppContext();
  const {
    charts,
    fetchingCharts,
    fetchingFilters,
    filtersMetaFetched,
    initialChartsDataFetched,
  } = state.dashboards;
  const { config: layoutConfig } = state;
  const { layoutWidthUpdated } = props;

  const [widths, setWidths] = useState<Record<string, number>>({});
  const [appliedFetch, setAppliedFetch] = useState<boolean>(false);
  const [widgetsGapInPercentage, setWidgetsGapInPercentage] =
    useState<number>(1);

  const [windowSize, setWindowSize] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
  });

  const handleResize = () => {
    setWindowSize({
      width: window.innerWidth,
      height: window.innerHeight,
    });
  };

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
  }, []);

  const getChartData = async (reqBody: any) => {
    dispatch({
      type: actionConstants.UPDATE_CHARTS_FETCHING_FLAG,
      payload: true,
    });
    if (String(reqBody?.Sentiment?.[0]).toLowerCase() === "all") {
      reqBody.Sentiment = [];
    }
    try {
      let chartData: any;
      if (reqBody) {
        chartData = await fetchChartDataWithFilters({
          selected_filters: reqBody,
        });
      } else {
        chartData = await fetchChartData();
      }
      // Update charts with data
      const updatedCharts: ChartConfigItem[] = layoutConfig.charts
        .map((configChart: any) => {
          if (!configChart || !configChart.id) {
            console.warn(
              "Config chart or config chart name is undefined:",
              configChart
            );
            return null; // Skip this chart if the name is missing
          }

          const apiData = chartData.find(
            (apiChart: any) =>
              apiChart.id?.toLowerCase() === configChart?.id?.toLowerCase()
          );
          const configObj = {
            id: configChart?.id,
            domId: configChart?.id.replace(/\s+/g, "_").toUpperCase(),
            type: configChart?.type,
            title: apiData ? apiData?.chart_name : configChart.name || "",
            data: apiData ? apiData?.chart_value : [],
            layout: {
              row: configChart?.layout?.row,
              col: configChart?.layout?.column,
              ...configChart?.layout,
            },
          } as ChartConfigItem;
          if (configChart?.layout?.width) {
            configObj.layout.width = configChart?.layout?.width;
          }
          return configObj;
        })
        .filter((chart): chart is ChartConfigItem => chart !== null);
      dispatch({
        type: actionConstants.UPDATE_CHARTS_DATA,
        payload: updatedCharts,
      });
      dispatch({
        type: actionConstants.UPDATE_CHARTS_FETCHING_FLAG,
        payload: false,
      });
    } catch (e) {
      dispatch({
        type: actionConstants.UPDATE_CHARTS_FETCHING_FLAG,
        payload: false,
      });
      console.log("Error while fetching charts data", e);
    }
  };

  // Fetch chart data and filters
  useEffect(() => {
    const loadData = async () => {
      try {
        if (!filtersMetaFetched) {
          dispatch({
            type: actionConstants.UPDATE_FILTERS_FETCHING_FLAG,
            payload: true,
          });
          const filterResponse = await fetchFilterData();
          const acceptedFilters: FilterMetaData = {};
          filterResponse?.forEach((obj: any) => {
            if (ACCEPT_FILTERS.includes(obj?.filter_name)) {
              const { filter_name, filter_values } = obj;
              acceptedFilters[filter_name] = filter_values;
            }
          });
          dispatch({
            type: actionConstants.SET_FILTERS,
            payload: acceptedFilters,
          });
          dispatch({
            type: actionConstants.UPDATE_FILTERS_FETCHED_FLAG,
            payload: true,
          });
          dispatch({
            type: actionConstants.UPDATE_FILTERS_FETCHING_FLAG,
            payload: false,
          });
        }
        if (!initialChartsDataFetched) {
          await getChartData({ ...defaultSelectedFilters });
          dispatch({
            type: actionConstants.UPDATE_INITIAL_CHARTS_FETCHED_FLAG,
            payload: true,
          });
        }
      } catch (error) {
        console.error("Error loading data:", error);
        dispatch({ type: actionConstants.UPDATE_CHARTS_DATA, payload: [] });
        dispatch({
          type: actionConstants.UPDATE_FILTERS_FETCHING_FLAG,
          payload: false,
        });
      }
    };
    if (state.config.charts.length > 0) {
      loadData();
    }
  }, [state.config.charts]);

  const applyFilters = async (updatedFilters: SelectedFilters) => {
    setAppliedFetch(true);
    await getChartData(updatedFilters);
    setAppliedFetch(false);
  };

  const renderChart = (chart: ChartConfigItem, heightInPixels: number) => {
    const getColorForLabel = (label: string): string => {
      switch (label) {
        case "positive":
          return "#6576F9"; // Blue
        case "neutral":
          return "#B2BBFC"; // Light Blue
        case "negative":
          return "#FF749B"; // Red
        default:
          return "#ccc"; // Default color
      }
    };

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
              color: getColorForLabel(item.name.toLowerCase()),
            }))}
            containerHeight={heightInPixels}
            widthInPixels={document?.getElementById(chart?.domId)!?.clientWidth}
            containerID={chart?.domId}
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
            containerID={chart?.domId}
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
            widthInPixels={document?.getElementById(chart?.domId)!?.clientWidth}
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
        console.warn(`Unknown chart type: ${chart.type}`);
        return null;
    }
  };

  useLayoutEffect(() => {
    const updateWidths = () => {
      const newWidths: Record<string, number> = {};
      charts.forEach((chartObj) => {
        const element = document.getElementById(chartObj?.domId);
        if (element) {
          newWidths[chartObj?.domId] = element!?.clientWidth;
        }
      });
      setWidths(newWidths);
    };
    return updateWidths();
  }, [charts, windowSize.height, windowSize.width, layoutWidthUpdated]);

  const getHeightInPixels = (vh: number) => (vh / 100) * window.innerHeight;

  const groupedByRows: any = {};
  charts.forEach((obj) => {
    const rowValue = String(obj?.layout?.row);
    if (!groupedByRows[rowValue]) {
      groupedByRows[rowValue] = [];
    }
    groupedByRows[rowValue].push(obj);
  });
  const showAIGeneratedContentMessage =
    (!fetchingCharts && !fetchingFilters) || appliedFetch;
  return (
    <>
      {fetchingCharts && !appliedFetch ? (
        <div className={"chartsLoaderContainer"}>
          <Spinner size={SpinnerSize.small} aria-label="Fetching Charts data" />
          <div className="loaderText">Loading Please wait...</div>
        </div>
      ) : (
        <div
          className="all-widgets-container"
          style={{
            filter: `blur(${
              fetchingCharts && appliedFetch ? "1.5px" : "0px"
            } )`,
          }}
        >
          {Object.values(groupedByRows).map((chartsList: any, index) => {
            const gridStyles = getGridStyles(
              [...chartsList],
              widgetsGapInPercentage
            );
            let heightInPixels = 240;
            if (gridStyles.gridTemplateRows) {
              if (!isNaN(parseInt(gridStyles.gridTemplateRows))) {
                const heightInVH = parseInt(gridStyles.gridTemplateRows);
                heightInPixels = getHeightInPixels(heightInVH);
              }
            }
            return (
              <div
                key={index}
                className="chart-container"
                style={{ ...gridStyles, gridGap: `${widgetsGapInPercentage}%` }}
              >
                {chartsList
                  .sort(
                    (a: ChartConfigItem, b: ChartConfigItem) =>
                      a?.layout.col - b?.layout?.col
                  )
                  .map((chart: any) => (
                    <div
                      key={chart.title}
                      id={chart?.domId}
                      className={`chart-item ${chart.type}Container`}
                    >
                      {/* <div className="chart-title">{chart.title}</div> */}
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
