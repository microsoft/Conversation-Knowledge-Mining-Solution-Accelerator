import React, { useMemo, useState } from "react";
import {
  Stack,
  DefaultButton,
  PrimaryButton,
  DirectionalHint,
  IContextualMenuListProps,
  IContextualMenuItem,
  IRenderFunction,
  SearchBox,
  Icon,
  VerticalDivider,
} from "@fluentui/react";
import "./ChartFilter.css";
import { type SelectedFilters } from "../../types/AppTypes";
import { defaultSelectedFilters, sentimentIcons } from "../../configs/Utils";
import { useAppContext } from "../../state/useAppContext";
import { actionConstants } from "../../state/ActionConstants";
import {
  ArrowClockwise20Regular,
  CalendarLtr20Regular,
  ChatMultiple20Regular,
  Emoji20Regular,
  EmojiMeh20Regular,
  EmojiMultiple20Regular,
  EmojiSad20Regular,
} from "@fluentui/react-icons";
interface FilterComponentProps {
  applyFilters: (updatedFilters: SelectedFilters) => void;
  acceptFilters: string[];
  fetchingCharts: boolean;
}

const ChartFilter: React.FC<FilterComponentProps> = (props) => {
  const { state, dispatch } = useAppContext();
  const { selectedFilters, filtersMeta } = state.dashboards;
  const { applyFilters, fetchingCharts } = props;
  const initialDateRange = typeof Array.isArray(selectedFilters.DateRange)
    ? selectedFilters.DateRange
    : [""];

  const [selectedDateRange, setSelectedDateRange] = useState<string[]>(
    initialDateRange as string[]
  );
  const [selectedCsat, setSelectedCsat] = useState<string[]>(
    selectedFilters.Sentiment as string[]
  );
  const [selectedTopics, setSelectedTopics] = useState<string[]>(
    selectedFilters.Topic as string[]
  );

  const [isDateMenuOpen, setIsDateMenuOpen] = useState(false);
  const [isCsatMenuOpen, setIsCsatMenuOpen] = useState(false);
  const [isTopicsMenuOpen, setIsTopicsMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const filteredTopics = filtersMeta?.Topic?.filter((option) =>
    option.displayValue.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const onSearchChange = (
    ev: React.KeyboardEvent<HTMLInputElement>,
    newValue: string
  ) => {
    setSearchQuery(newValue || "");
  };

  const handleTopicSelection = (e: any, key: string) => {
    e.preventDefault();
    setSelectedTopics((prevSelected) =>
      prevSelected.includes(key)
        ? prevSelected.filter((topic) => topic !== key)
        : [...prevSelected, key]
    );
  };

  const handleDateSelection = (key: string) => {
    setSelectedDateRange([key]);
    setIsDateMenuOpen(false);
  };

  const handleCsatSelection = (key: string) => {
    setSelectedCsat([key]);
    setIsCsatMenuOpen(false);
  };

  const handleApplyFilters = () => {
    const startDate = selectedDateRange || [""];
    const updatedFilters: SelectedFilters = {};
    updatedFilters.Topic = selectedTopics;
    updatedFilters.Sentiment = selectedCsat;
    updatedFilters.DateRange = startDate;
    applyFilters(updatedFilters);
    dispatch({
      type: actionConstants.UPDATE_SELECTED_FILTERS,
      payload: updatedFilters,
    });
  };

  const handleResetFilters = () => {
    setSelectedDateRange(defaultSelectedFilters.DateRange as string[]);
    setSelectedCsat(defaultSelectedFilters.Sentiment); // Assuming "all" is the key for the "all" sentiment
    setSelectedTopics(defaultSelectedFilters.Topic as []);
  };
  const getDisplayValue = (
    filterList: { key: string; displayValue: string }[],
    key: string
  ) => {
    const matched = filterList?.find(
      (ob: any) => String(ob?.key) === String(key)
    );
    if (matched?.displayValue) {
      return matched.displayValue as string;
    }
    return "";
  };

  const onTopicsMenuOpen = () => {
    setSearchQuery(""); // Clear the search query when the menu opens
    setTimeout(() => {
      const element = document.getElementById("SEARCH_TOPICS");
      if (element) {
        element.focus();
      }
    }, 100);
  };
  const renderMenuList: IRenderFunction<IContextualMenuListProps> = (
    menuListProps,
    defaultRender
  ) => (
    <div>
      <button
        className="options resetTopicsButton"
        onClick={handleDeselectAll}
        disabled={selectedTopics.length === 0}
      >
        <div>
          <i aria-hidden="true" className="deselectIcon"></i>
          <span> Reset topics</span>
        </div>
      </button>
      <div style={{ borderBottom: "1px solid #ccc" }}></div>
      {defaultRender ? defaultRender(menuListProps) : null}
      <div style={{ borderBottom: "1px solid #ccc" }}> </div>
      <SearchBox
        className="searchTopics"
        ariaLabel="Filter topics"
        placeholder="Search topics"
        onClear={() => {
          setSearchQuery("");
        }} // Clear search query when the "X" is clicked
        onKeyUp={(e) => {
          onSearchChange(e, (e.target as HTMLInputElement).value);
        }}
        iconProps={{ iconName: "Search" }}
        styles={{ root: { margin: "8px" } }}
        id="SEARCH_TOPICS"
        showIcon
        autoComplete="off"
        autoFocus
      />
    </div>
  );

  const handleDeselectAll = (ev: React.MouseEvent<HTMLElement>) => {
    ev.preventDefault();
    setSelectedTopics([]); // Deselect all items
  };

  const topicMenuProps = useMemo(
    () => ({
      onRenderMenuList: renderMenuList,
      items: filteredTopics.length
        ? (filteredTopics?.map((option) => ({
            key: option.key,
            text: option.displayValue,
            canCheck: true,
            shouldFocusOnMount: true,
            checked: selectedTopics.includes(option.key),
            onClick: (e) => handleTopicSelection(e, option.key),
          })) as IContextualMenuItem[])
        : ([
            {
              key: "no_results",
              onRender: () => (
                <div key="no_results" className="no-result">
                  <Icon iconName="SearchIssue" title="No result found" />
                  <span>No topics found</span>
                </div>
              ),
            },
          ] as IContextualMenuItem[]),
      directionalHint: DirectionalHint.bottomLeftEdge,
      onMenuOpened: () => onTopicsMenuOpen(),
    }),
    [filteredTopics, selectedTopics]
  );

  return (
    <Stack
      horizontal
      tokens={{ childrenGap: 10 }}
      className="filters-container"
    >
      <div className="filterOuterContainer">
        <DefaultButton
          onRenderIcon={() => <CalendarLtr20Regular />}
          text={getDisplayValue(
            filtersMeta?.DateRange,
            selectedDateRange[0] || ""
          )}
          onClick={() => setIsDateMenuOpen(!isDateMenuOpen)}
          menuProps={{
            items: filtersMeta?.DateRange?.map((option) => ({
              key: String(option.key),
              text: option.displayValue,
              canCheck: true,
              checked: option.key === selectedDateRange[0],
              onClick: () => handleDateSelection(String(option.key)),
            })),
            calloutProps: {
              directionalHintFixed: true,
              styles: { calloutMain: { maxHeight: 300, overflowY: "auto" } },
            },
            directionalHint: DirectionalHint.topLeftEdge,
            onDismiss: () => setIsDateMenuOpen(false),
          }}
          disabled={fetchingCharts}
        />
        <VerticalDivider />
        <DefaultButton
          className="capitalize-text"
          onClick={() => setIsCsatMenuOpen(!isCsatMenuOpen)}
          menuProps={{
            styles: { root: { minWidth: "13rem" } },
            items: filtersMeta?.Sentiment?.map((option) => ({
              key: String(option.key),
              iconProps: {
                iconName:
                  sentimentIcons[option.key] || "EmojiMultiple20Regular",
              },
              onRenderIcon: (renderIconProps) => {
                switch (renderIconProps?.item.key) {
                  case "Positive":
                    return <Emoji20Regular />;
                  case "Neutral":
                    return <EmojiMeh20Regular />;
                  case "Negative":
                    return <EmojiSad20Regular />;
                  default:
                    return <EmojiMultiple20Regular />;
                }
              },
              text: option.displayValue,
              checked: option.key === selectedCsat?.[0],
              onClick: () => handleCsatSelection(String(option.key)),
            })),
            directionalHint: DirectionalHint.topLeftEdge,
            calloutProps: {
              directionalHintFixed: true,
              styles: { calloutMain: { maxHeight: 300, overflowY: "auto" } },
            },
            onDismiss: () => setIsCsatMenuOpen(false),
          }}
          disabled={fetchingCharts}
        >
          {(() => {
            switch (selectedCsat?.[0]) {
              case "Positive":
                return <Emoji20Regular />;
              case "Neutral":
                return <EmojiMeh20Regular />;
              case "Negative":
                return <EmojiSad20Regular />;
              default:
                return <EmojiMultiple20Regular />;
            }
          })()}
          {getDisplayValue(filtersMeta?.Sentiment, selectedCsat?.[0] || "")}
        </DefaultButton>
        <VerticalDivider />
        <DefaultButton
          onRenderIcon={() => <ChatMultiple20Regular />}
          text={`Topics (${selectedTopics?.length})`}
          onClick={() => setIsTopicsMenuOpen(!isTopicsMenuOpen)}
          disabled={fetchingCharts}
          menuProps={topicMenuProps}
        />
        <VerticalDivider />
        <DefaultButton
          onRenderIcon={() => <ArrowClockwise20Regular />}
          onClick={handleResetFilters}
          styles={{ root: { padding: "0px" } }}
          title="Reset"
          disabled={fetchingCharts}
        />
        <VerticalDivider />
        <DefaultButton
          className="applyBtn"
          onClick={handleApplyFilters}
          disabled={fetchingCharts}
        >
          Apply
        </DefaultButton>
      </div>
    </Stack>
  );
};

export default ChartFilter;
