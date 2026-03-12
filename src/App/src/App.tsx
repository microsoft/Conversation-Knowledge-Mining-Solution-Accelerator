import React, { useEffect, useState, useRef } from "react";
import Chart from "./components/Chart/Chart";
import Chat from "./components/Chat/Chat";
import {
  Button,
  FluentProvider,
  Subtitle2,
  Body2,
  webLightTheme,
  Avatar,
  Tag,
} from "@fluentui/react-components";
import { SparkleRegular } from "@fluentui/react-icons";
import "./App.css";
import { ChatHistoryPanel } from "./components/ChatHistoryPanel/ChatHistoryPanel";

import { getUserInfo, getLayoutConfig } from "./api/api";

import { useAppDispatch, useAppSelector } from "./store/hooks";
import { AppLogo } from "./components/Svg/Svg";
import CustomSpinner from "./components/CustomSpinner/CustomSpinner";
import CitationPanel from "./components/CitationPanel/CitationPanel";
import { saveConfig } from "./store/slices/appSlice";
import { updateCitation } from "./store/slices/citationSlice";
import {
  fetchChatHistory,
  loadConversation,
  clearAllChatHistory,
} from "./store/thunks/chatHistoryThunks";
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
  const appConfig = useAppSelector((s) => s.app.config.appConfig);
  const showAppSpinner = useAppSelector((s) => s.app.showAppSpinner);
  const showCitation = useAppSelector((s) => s.citation.showCitation);
  const activeCitation = useAppSelector((s) => s.citation.activeCitation);
  const currentConversationIdForCitation = useAppSelector((s) => s.citation.currentConversationIdForCitation);
  const [panelShowStates, setPanelShowStates] = useState<
    Record<string, boolean>
  >({ ...defaultPanelShowStates });
  const [panelWidths, setPanelWidths] = useState<Record<string, number>>({
    ...defaultThreeColumnConfig,
  });
  const [layoutWidthUpdated, setLayoutWidthUpdated] = useState<boolean>(false);
  const [showClearAllConfirmationDialog, setChowClearAllConfirmationDialog] =
    useState(false);
  const [clearing, setClearing] = React.useState(false);
  const [clearingError, setClearingError] = React.useState(false);
  const [isInitialAPItriggered, setIsInitialAPItriggered] = useState(false);
  const [showAuthMessage, setShowAuthMessage] = useState<boolean | undefined>();
  const [offset, setOffset] = useState<number>(0);
  const OFFSET_INCREMENT = 25;
  const [hasMoreRecords, setHasMoreRecords] = useState<boolean>(true);
  const [name, setName] = useState<string>("");

  useEffect(() => {
    try {
      const fetchConfig = async () => {
        const configData = await getLayoutConfig();
        dispatch(saveConfig(configData));
      };
      fetchConfig();
    } catch (error) {
      console.error("Failed to fetch chart configuration:", error);
    }
  }, []);

  const getUserInfoList = async () => {
    const userInfoList = await getUserInfo();
    if (
      userInfoList.length === 0 &&
      window.location.hostname !== "localhost" &&
      window.location.hostname !== "127.0.0.1"
    ) {
      setShowAuthMessage(true);
    } else {
      setShowAuthMessage(false);
    }
  };

  useEffect(() => {
    getUserInfoList();
  }, []);

  useEffect(() => {
    getUserInfo().then((res) => {
      const name: string = res[0]?.user_claims?.find((claim: any) => claim.typ === 'name')?.val ?? ''
      setName(name)
    }).catch(() => {
      console.error('Error fetching user info')
    })
  }, [])

  const updateLayoutWidths = (newState: Record<string, boolean>) => {
    const noOfWidgetsOpen = Object.values(newState).filter((val) => val).length;
    if (appConfig === null) {
      return;
    }

    if (
      noOfWidgetsOpen === 1 ||
      (noOfWidgetsOpen === 2 && !newState[panels.CHAT])
    ) {
      setPanelWidths(defaultSingleColumnConfig);
    } else if (noOfWidgetsOpen === 2 && newState[panels.CHAT]) {
      const panelsInOpenState = Object.keys(newState).filter(
        (key) => newState[key]
      );
      const twoColLayouts = Object.keys(appConfig.TWO_COLUMN) as string[];
      for (let i = 0; i < twoColLayouts.length; i++) {
        const key = twoColLayouts[i] as string;
        const panelNames = key.split("_");
        const isMatched = panelsInOpenState.every((val) =>
          panelNames.includes(val)
        );
        const TWO_COLUMN = appConfig.TWO_COLUMN as Record<
          string,
          Record<string, number>
        >;
        if (isMatched) {
          setPanelWidths({ ...TWO_COLUMN[key] });
          break;
        }
      }
    } else {
      const threeColumn = appConfig.THREE_COLUMN as Record<string, number>;
      threeColumn.DASHBOARD =
        threeColumn.DASHBOARD > 55 ? threeColumn.DASHBOARD : 55;
      setPanelWidths({ ...threeColumn });
    }
  };

  useEffect(() => {
    updateLayoutWidths(panelShowStates);
  }, [appConfig]);

  const onHandlePanelStates = (panelName: string) => {
    dispatch(updateCitation({ activeCitation: null, showCitation: false }))
    setLayoutWidthUpdated((prevFlag) => !prevFlag);
    const newState = {
      ...panelShowStates,
      [panelName]: !panelShowStates[panelName],
    };
    const isHiddenBoth = !newState[panels.DASHBOARD] && !newState[panels.CHAT];
    if (isHiddenBoth && panelName === panels.CHAT) {
      newState[panels.DASHBOARD] = true;
    } else if (isHiddenBoth && panelName === panels.DASHBOARD) {
      newState[panels.CHAT] = true;
    }
    updateLayoutWidths(newState);
    setPanelShowStates(newState);
  };

  const getHistoryListData = async () => {
    if (!hasMoreRecords) return;
    const convs = await dispatch(fetchChatHistory(offset)).unwrap();
    if (convs !== null) {
      if (convs.length === OFFSET_INCREMENT) {
        setOffset((o) => o + OFFSET_INCREMENT);
      } else if (convs.length < OFFSET_INCREMENT) {
        setHasMoreRecords(false);
      }
    }
  };

  const onClearAllChatHistory = async () => {
    dispatch(updateCitation({ activeCitation: null, showCitation: false }));
    setClearing(true);
    try {
      await dispatch(clearAllChatHistory()).unwrap();
      setChowClearAllConfirmationDialog(false);
    } catch {
      setClearingError(true);
    }
    setClearing(false);
  };

  useEffect(() => {
    setIsInitialAPItriggered(true);
  }, []);

  useEffect(() => {
    if (isInitialAPItriggered) {
      (async () => {
        getHistoryListData();
      })();
    }
  }, [isInitialAPItriggered]);

  const [ASSISTANT, TOOL, ERROR, USER] = ["assistant", "tool", "error", "user"];

  const onSelectConversation = async (id: string) => {
    if (!id) {
      console.error("No conversation ID found");
      return;
    }
    try {
      await dispatch(loadConversation(id)).unwrap();
    } catch (error) {
      console.error("Error fetching conversation messages:", error);
    }
  };

  const onClickClearAllOption = () => {
    setChowClearAllConfirmationDialog((prevFlag) => !prevFlag);
  };

  const onHideClearAllDialog = () => {
    setChowClearAllConfirmationDialog((prevFlag) => !prevFlag);
    setTimeout(() => {
      setClearingError(false);
    }, 1000);
  };

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
              panelShowStates?.[panels.DASHBOARD] ? "Hide" : "Show"
            } Dashboard`}
          </Button>
          <Button
            icon={<SparkleRegular />}
            appearance="subtle"
            onClick={() => onHandlePanelStates(panels.CHAT)}
          >
            {`${panelShowStates?.[panels.CHAT] ? "Hide" : "Show"} Chat`}
          </Button>
          <div>
            <Avatar name={name} title={name} />
          </div>
        </div>
      </div>
      <div className="main-container">
        {/* LEFT PANEL: DASHBOARD */}
        {panelShowStates?.[panels.DASHBOARD] && (
          <div
            className="left-section"
            style={{ width: `${panelWidths[panels.DASHBOARD]}%` }}
          >
            <Chart layoutWidthUpdated={layoutWidthUpdated} />
          </div>
        )}
        {/* MIDDLE PANEL: CHAT */}
        {panelShowStates?.[panels.CHAT] && (
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
              // width: `${panelWidths[panels.DASHBOARD]}%`,
              width: `${panelWidths[panels.CHATHISTORY] || 17}%`,
              // minWidth: '30%'
            }}
          >
            <CitationPanel activeCitation={activeCitation}  />

          </div>
        )}
        {/* RIGHT PANEL: CHAT HISTORY */}
        {panelShowStates?.[panels.CHAT] &&
          panelShowStates?.[panels.CHATHISTORY] && (
            <div
              style={{
                width: `${panelWidths[panels.CHATHISTORY]}%`,
              }}
            >
              <ChatHistoryPanel
                clearing={clearing}
                clearingError={clearingError}
                handleFetchHistory={() => getHistoryListData()}
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
