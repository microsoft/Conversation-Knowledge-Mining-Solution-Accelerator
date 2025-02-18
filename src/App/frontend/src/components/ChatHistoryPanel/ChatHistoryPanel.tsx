import React, { useState } from "react";
import {
  CommandBarButton,
  ContextualMenu,
  DefaultButton,
  Dialog,
  DialogFooter,
  DialogType,
  ICommandBarStyles,
  IContextualMenuItem,
  PrimaryButton,
  Stack,
  StackItem,
  Text,
} from "@fluentui/react";

import styles from "./ChatHistoryPanel.module.css";
import { type Conversation } from "../../types/AppTypes";
import { ChatHistoryListItemGroups } from "../ChatHistoryListItemGroups/ChatHistoryListItemGroups";
import { useAppContext } from "../../state/useAppContext";

const commandBarStyle: ICommandBarStyles = {
  root: {
    padding: "0",
    display: "flex",
    justifyContent: "center",
    backgroundColor: "transparent",
  },
};

export type ChatHistoryPanelProps = {
  clearingError: boolean;
  clearing: boolean;
  onHideClearAllDialog?: () => void;
  onClearAllChatHistory?: () => Promise<void>;
  handleFetchHistory: () => Promise<void>;
  onSelectConversation: (id: string) => Promise<void>;
  showClearAllConfirmationDialog: boolean;
  onClickClearAllOption: () => void;
};

const modalProps = {
  titleAriaId: "labelId",
  subtitleAriaId: "subTextId",
  isBlocking: true,
  styles: { main: { maxWidth: 450 } },
};

export const ChatHistoryPanel: React.FC<ChatHistoryPanelProps> = (props) => {
  const {
    clearingError,
    clearing,
    onHideClearAllDialog,
    onClearAllChatHistory,
    handleFetchHistory,
    onSelectConversation,
    showClearAllConfirmationDialog,
    onClickClearAllOption,
  } = props;
  const { state, dispatch } = useAppContext();
  const { chatHistory } = state;
  const [showClearAllContextMenu, setShowClearAllContextMenu] =
    useState<boolean>(false);

  const { generatingResponse } = state?.chat;
  const clearAllDialogContentProps = {
    type: DialogType.close,
    title: !clearingError
      ? "Are you sure you want to clear all chat history?"
      : "Error deleting all of chat history",
    closeButtonAriaLabel: "Close",
    subText: !clearingError
      ? "All chat history will be permanently removed."
      : "Please try again. If the problem persists, please contact the site administrator.",
  };

  const disableClearAllChatHistory =
    !chatHistory.list.length ||
    generatingResponse ||
    state.chatHistory.fetchingConversations;
  const menuItems: IContextualMenuItem[] = [
    {
      key: "clearAll",
      text: "Clear all chat history",
      disabled: disableClearAllChatHistory,
      iconProps: { iconName: "Delete" },
      onClick: () => {
        onClickClearAllOption();
      },
    },
  ];

  const handleClearAllContextualMenu = () => {
    setShowClearAllContextMenu((prev) => !prev);
  };

  return (
    <section
      className={styles.historyContainer}
      data-is-scrollable
      aria-label={"chat history panel"}
    >
      <Stack
        horizontal
        horizontalAlign="space-between"
        verticalAlign="center"
        wrap
        aria-label="chat history header"
        className={styles.chatHistoryHeader}
      >
        <div
          role="heading"
          aria-level={2}
          style={{
            fontWeight: "600",
          }}
        >
          Chat history
        </div>
        <Stack horizontal className={styles.historyPanelTopRightButtons}>
          <Stack horizontal>
            <CommandBarButton
              iconProps={{ iconName: "More" }}
              title={"Clear all chat history"}
              onClick={handleClearAllContextualMenu}
              aria-label={"clear all chat history"}
              styles={commandBarStyle}
              role="button"
              id="moreButton"
            />
            <ContextualMenu
              items={menuItems}
              hidden={!showClearAllContextMenu}
              target={"#moreButton"} 
              onDismiss={handleClearAllContextualMenu}
            />
          </Stack>

        </Stack>
      </Stack>
      <Stack
        aria-label="chat history panel content"
        style={{
          display: "flex",
          height: "calc(100% - 3rem)",
        }}
      >
        <Stack className={styles.chatHistoryListContainer}>
          <ChatHistoryListItemGroups
            handleFetchHistory={handleFetchHistory}
            onSelectConversation={onSelectConversation}
          />
        </Stack>
      </Stack>
      <Dialog
        hidden={!showClearAllConfirmationDialog}
        onDismiss={clearing ? () => {} : onHideClearAllDialog}
        dialogContentProps={clearAllDialogContentProps}
        modalProps={modalProps}
      >
        <DialogFooter>
          {!clearingError && (
            <PrimaryButton
              onClick={onClearAllChatHistory}
              disabled={clearing}
              text="Clear All"
            />
          )}
          <DefaultButton
            onClick={onHideClearAllDialog}
            disabled={clearing}
            text={!clearingError ? "Cancel" : "Close"}
          />
        </DialogFooter>
      </Dialog>
    </section>
  );
};
