import React, { useCallback, useEffect, useState } from "react";
import Chart from "./components/Chart/Chart";
import Chat from "./components/Chat/Chat";
import {
  Avatar,
  Body2,
  Button,
  FluentProvider,
  Subtitle2,
  webLightTheme,
} from "@fluentui/react-components";
import { SparkleRegular } from "@fluentui/react-icons";
import "./App.css";
import { ChatHistoryPanel } from "./components/ChatHistoryPanel/ChatHistoryPanel";
import { getUserInfo } from "./api/api";
import { useAppDispatch, useAppSelector } from "./state/hooks";
import {
  ensureHistoryReady,
  fetchLayoutConfig,
  setSelectedConversationId,
  setShowAppSpinner,
  startNewConversation,
} from "./state/slices/appSlice";
import {
  clearAllConversations,
  fetchConversationMessages,
  fetchConversations,
} from "./state/slices/chatHistorySlice";
import { resetChatState, setMessages } from "./state/slices/chatSlice";
import { hideCitation } from "./state/slices/citationSlice";
import { AppLogo } from "./components/Svg/Svg";
import CustomSpinner from "./components/CustomSpinner/CustomSpinner";
import CitationPanel from "./components/CitationPanel/CitationPanel";

const panels = {
  DASHBOARD: "DASHBOARD",
  CHAT: "CHAT",
  CHATHISTORY: "CHATHISTORY",
};

const defaultThreeColumnConfig: Record<string, number> = {
  [panels.DASHBOARD]: 60,
  [panels.CHAT]: 40,
  [panels.CHATHISTORY]: 20,
};
const defaultSingleColumnConfig: Record<string, number> = {
  [panels.DASHBOARD]: 100,
  [panels.CHAT]: 100,
  [panels.CHATHISTORY]: 100,
};

const defaultPanelShowStates = {
  [panels.DASHBOARD]: true,
  [panels.CHAT]: true,
  [panels.CHATHISTORY]: false,
};

const Dashboard: React.FC = () => {
  const dispatch = useAppDispatch();
  const appConfig = useAppSelector((state) => state.app.config.appConfig);
  const showAppSpinner = useAppSelector((state) => state.app.showAppSpinner);
  const activeCitation = useAppSelector((state) => state.citation.activeCitation);
  const showCitation = useAppSelector((state) => state.citation.showCitation);
  const currentConversationIdForCitation = useAppSelector(
    (state) => state.citation.currentConversationIdForCitation
  );
  const isFetchingConversations = useAppSelector(
    (state) => state.chatHistory.fetchingConversations
  );

  const [panelShowStates, setPanelShowStates] = useState<
    Record<string, boolean>
  >({ ...defaultPanelShowStates });
  const [panelWidths, setPanelWidths] = useState<Record<string, number>>({
    ...defaultThreeColumnConfig,
  });
  const [layoutWidthUpdated, setLayoutWidthUpdated] = useState<boolean>(false);
  const [showClearAllConfirmationDialog, setChowClearAllConfirmationDialog] =
    useState(false);
  const [clearing, setClearing] = useState(false);
  const [clearingError, setClearingError] = useState(false);
  const [offset, setOffset] = useState<number>(0);
  const [hasMoreRecords, setHasMoreRecords] = useState<boolean>(true);
  const [name, setName] = useState<string>("");
  const OFFSET_INCREMENT = 25;

  useEffect(() => {
    void dispatch(fetchLayoutConfig());
    void dispatch(ensureHistoryReady());
  }, [dispatch]);

  useEffect(() => {
    const hydrateUser = async () => {
      const userInfo = await getUserInfo();
      const displayName: string =
        userInfo[0]?.user_claims?.find((claim: any) => claim.typ === "name")
          ?.val ?? "";
      setName(displayName);
    };

    void hydrateUser();
  }, []);

  const updateLayoutWidths = useCallback(
    (newState: Record<string, boolean>) => {
      const noOfWidgetsOpen = Object.values(newState).filter(Boolean).length;
      if (appConfig === null) {
        return;
      }

      if (
        noOfWidgetsOpen === 1 ||
        (noOfWidgetsOpen === 2 && !newState[panels.CHAT])
      ) {
        setPanelWidths(defaultSingleColumnConfig);
        return;
      }

      if (noOfWidgetsOpen === 2 && newState[panels.CHAT]) {
        const panelsInOpenState = Object.keys(newState).filter(
          (key) => newState[key]
        );
        const twoColumnLayouts = Object.keys(appConfig.TWO_COLUMN) as string[];

        for (const layoutKey of twoColumnLayouts) {
          const panelNames = layoutKey.split("_");
          const isMatched = panelsInOpenState.every((value) =>
            panelNames.includes(value)
          );
          const twoColumnConfig = appConfig.TWO_COLUMN as Record<
            string,
            Record<string, number>
          >;

          if (isMatched) {
            setPanelWidths({ ...twoColumnConfig[layoutKey] });
            return;
          }
        }
      }

      const threeColumn = {
        ...(appConfig.THREE_COLUMN as Record<string, number>),
      };
      threeColumn.DASHBOARD =
        threeColumn.DASHBOARD > 55 ? threeColumn.DASHBOARD : 55;
      setPanelWidths(threeColumn);
    },
    [appConfig]
  );

  useEffect(() => {
    updateLayoutWidths(panelShowStates);
  }, [panelShowStates, updateLayoutWidths]);

  const onHandlePanelStates = useCallback(
    (panelName: string) => {
      dispatch(hideCitation());
      setLayoutWidthUpdated((previousFlag) => !previousFlag);
      const nextState = {
        ...panelShowStates,
        [panelName]: !panelShowStates[panelName],
      };
      const isHiddenBoth = !nextState[panels.DASHBOARD] && !nextState[panels.CHAT];

      if (isHiddenBoth && panelName === panels.CHAT) {
        nextState[panels.DASHBOARD] = true;
      } else if (isHiddenBoth && panelName === panels.DASHBOARD) {
        nextState[panels.CHAT] = true;
      }

      updateLayoutWidths(nextState);
      setPanelShowStates(nextState);
    },
    [dispatch, panelShowStates, updateLayoutWidths]
  );

  const getHistoryListData = useCallback(async () => {
    if (!hasMoreRecords || isFetchingConversations) {
      return;
    }

    const result = await dispatch(fetchConversations(offset));
    if (fetchConversations.fulfilled.match(result)) {
      const conversations = result.payload;
      if (conversations.length === OFFSET_INCREMENT) {
        setOffset((currentOffset) => currentOffset + OFFSET_INCREMENT);
      } else if (conversations.length < OFFSET_INCREMENT) {
        setHasMoreRecords(false);
      }
    }
  }, [
    dispatch,
    hasMoreRecords,
    isFetchingConversations,
    offset,
    OFFSET_INCREMENT,
  ]);

  useEffect(() => {
    void getHistoryListData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onClearAllChatHistory = useCallback(async () => {
    dispatch(setShowAppSpinner(true));
    dispatch(hideCitation());
    setClearing(true);
    setClearingError(false);

    const result = await dispatch(clearAllConversations());
    if (clearAllConversations.rejected.match(result)) {
      setClearingError(true);
    } else {
      setChowClearAllConfirmationDialog(false);
      dispatch(resetChatState());
      dispatch(startNewConversation());
    }

    setClearing(false);
    dispatch(setShowAppSpinner(false));
  }, [dispatch]);

  const onSelectConversation = useCallback(
    async (id: string) => {
      if (!id) {
        return;
      }

      dispatch(hideCitation());
      dispatch(setSelectedConversationId(id));
      const result = await dispatch(fetchConversationMessages(id));

      if (fetchConversationMessages.fulfilled.match(result)) {
        dispatch(setMessages(result.payload.messages));
      }
    },
    [dispatch]
  );

  const onClickClearAllOption = useCallback(() => {
    setChowClearAllConfirmationDialog((previousFlag) => !previousFlag);
  }, []);

  const onHideClearAllDialog = useCallback(() => {
    setChowClearAllConfirmationDialog((previousFlag) => !previousFlag);
    setTimeout(() => {
      setClearingError(false);
    }, 1000);
  }, []);

  return (
    <FluentProvider
      theme={webLightTheme}
      style={{ height: "100%", backgroundColor: "#F5F5F5" }}
    >
      <CustomSpinner loading={showAppSpinner} label="Please wait.....!" />
      <div className="header">
        <div className="header-left-section">
          <AppLogo />
          <Subtitle2>
            Woodgrove <Body2 style={{ gap: "10px" }}>| Call Analysis</Body2>
          </Subtitle2>
        </div>
        <div className="header-right-section">
          <Button
            appearance="subtle"
            onClick={() => onHandlePanelStates(panels.DASHBOARD)}
          >
            {`${
              panelShowStates[panels.DASHBOARD] ? "Hide" : "Show"
            } Dashboard`}
          </Button>
          <Button
            icon={<SparkleRegular />}
            appearance="subtle"
            onClick={() => onHandlePanelStates(panels.CHAT)}
          >
            {`${panelShowStates[panels.CHAT] ? "Hide" : "Show"} Chat`}
          </Button>
          <div>
            <Avatar name={name} title={name} />
          </div>
        </div>
      </div>
      <div className="main-container">
        {panelShowStates[panels.DASHBOARD] && (
          <div
            className="left-section"
            style={{ width: `${panelWidths[panels.DASHBOARD]}%` }}
          >
            <Chart layoutWidthUpdated={layoutWidthUpdated} />
          </div>
        )}
        {panelShowStates[panels.CHAT] && (
          <div
            style={{
              width: `${panelWidths[panels.CHAT]}%`,
            }}
          >
            <Chat
              onHandlePanelStates={onHandlePanelStates}
              panels={panels}
              panelShowStates={panelShowStates}
            />
          </div>
        )}
        {showCitation && currentConversationIdForCitation !== "" && (
          <div
            style={{
              width: `${panelWidths[panels.CHATHISTORY] || 17}%`,
            }}
          >
            <CitationPanel activeCitation={activeCitation} />
          </div>
        )}
        {panelShowStates[panels.CHAT] &&
          panelShowStates[panels.CHATHISTORY] && (
            <div
              style={{
                width: `${panelWidths[panels.CHATHISTORY]}%`,
              }}
            >
              <ChatHistoryPanel
                clearing={clearing}
                clearingError={clearingError}
                handleFetchHistory={getHistoryListData}
                onClearAllChatHistory={onClearAllChatHistory}
                onClickClearAllOption={onClickClearAllOption}
                onHideClearAllDialog={onHideClearAllDialog}
                onSelectConversation={onSelectConversation}
                showClearAllConfirmationDialog={showClearAllConfirmationDialog}
              />
            </div>
          )}
      </div>
    </FluentProvider>
  );
};

export default Dashboard;
