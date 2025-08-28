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

import {
  getUserInfo,
  getLayoutConfig,
  historyDelete,
  historyDeleteAll,
  historyList,
  historyRead,
} from "./api/api";

import { useAppContext } from "./state/useAppContext";
import { actionConstants } from "./state/ActionConstants";
import { ChatMessage, Conversation } from "./types/AppTypes";
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
  const { state, dispatch } = useAppContext();
  const { appConfig } = state.config;
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
        console.log("configData", configData);
        dispatch({ type: actionConstants.SAVE_CONFIG, payload: configData });
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
    }).catch((err) => {
      console.error('Error fetching user info: ', err)
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
  }, [state.config.appConfig]);

  const onHandlePanelStates = (panelName: string) => {
    dispatch({  type: actionConstants.UPDATE_CITATION,payload: { activeCitation: null, showCitation: false }})
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
    if (!hasMoreRecords) {
      return;
    }
    dispatch({
      type: actionConstants.UPDATE_CONVERSATIONS_FETCHING_FLAG,
      payload: true,
    });
    const convs = await historyList(offset);
    if (convs !== null) {
      if (convs.length === OFFSET_INCREMENT) {
        setOffset((offset) => (offset += OFFSET_INCREMENT));
        // Stopping offset increment if there were no records
      } else if (convs.length < OFFSET_INCREMENT) {
        setHasMoreRecords(false);
      }
      dispatch({
        type: actionConstants.ADD_CONVERSATIONS_TO_LIST,
        payload: convs,
      });
    }
    dispatch({
      type: actionConstants.UPDATE_CONVERSATIONS_FETCHING_FLAG,
      payload: false,
    });
  };

  const onClearAllChatHistory = async () => {
    dispatch({
      type: actionConstants.UPDATE_APP_SPINNER_STATUS,
      payload: true,
    });
    dispatch({  type: actionConstants.UPDATE_CITATION,payload: { activeCitation: null, showCitation: false }})
    setClearing(true);
    const response = await historyDeleteAll();
    if (!response.ok) {
      setClearingError(true);
    } else {
      setChowClearAllConfirmationDialog(false);
      dispatch({ type: actionConstants.UPDATE_ON_CLEAR_ALL_CONVERSATIONS });
    }
    setClearing(false);
    dispatch({
      type: actionConstants.UPDATE_APP_SPINNER_STATUS,
      payload: false,
    });
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

  const getLastRagResponse = (messages: ChatMessage[]) => {
    const lastAssistantObj = [...messages]
      .reverse()
      .find((obj) => obj.role === ASSISTANT && typeof obj.content === "string");
    if (typeof lastAssistantObj?.content === "string") {
      return lastAssistantObj.content.trim();
    }
    return null;
  };

  const onSelectConversation = async (id: string) => {
    if (!id) {
      console.error("No conversation ID found");
      return;
    }
    dispatch({
      type: actionConstants.UPDATE_CHATHISTORY_CONVERSATION_FLAG,
      payload: true,
    });
    dispatch({
      type: actionConstants.UPDATE_SELECTED_CONV_ID,
      payload: id,
    });
    dispatch({
      type: actionConstants.SET_LAST_RAG_RESPONSE,
      payload: null,
    });
    try {
      const responseMessages = await historyRead(id);

      if (responseMessages) {
        dispatch({
          type: actionConstants.SHOW_CHATHISTORY_CONVERSATION,
          payload: {
            id,
            messages: responseMessages,
          },
        });
      }
      const lastRagResponse = getLastRagResponse(responseMessages);
      dispatch({
        type: actionConstants.SET_LAST_RAG_RESPONSE,
        payload: lastRagResponse,
      });
    } catch (error) {
      console.error("Error fetching conversation messages:", error);
    } finally {
      dispatch({
        type: actionConstants.UPDATE_CHATHISTORY_CONVERSATION_FLAG,
        payload: false,
      });
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
      <CustomSpinner loading={state.showAppSpinner} label="Please wait.....!" />
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
        {state.citation.showCitation && state.citation.currentConversationIdForCitation !== "" && (
          <div
            style={{
              // width: `${panelWidths[panels.DASHBOARD]}%`,
              width: `${panelWidths[panels.CHATHISTORY] || 17}%`,
              // minWidth: '30%'
            }}
          >
            <CitationPanel activeCitation={state.citation.activeCitation}  />

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
              {/* {useAppContext?.state.isChatHistoryOpen &&
            useAppContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured && <ChatHistoryPanel />} */}
            </div>
          )}
      </div>
    </FluentProvider>
  );
};

export default Dashboard;
