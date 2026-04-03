import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Button,
  Textarea,
  Subtitle2,
  Body1,
} from "@fluentui/react-components";
import "./Chat.css";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import supersub from "remark-supersub";
import { DefaultButton, Spinner, SpinnerSize } from "@fluentui/react";
import { useAppContext } from "../../state/useAppContext";
import { actionConstants } from "../../state/ActionConstants";
import {
  type ChartDataResponse,
  type Conversation,
  type ConversationRequest,
  type ParsedChunk,
  type ChatMessage,
  ToolMessageContent,
} from "../../types/AppTypes";
import { callConversationApi, getIsChartDisplayDefault, historyUpdate } from "../../api/api";
import { ChatAdd24Regular } from "@fluentui/react-icons";
import ChatChart from "../ChatChart/ChatChart";
import Citations from "../Citations/Citations";
import { setUserMessage, clearMessages } from "../../store/slices/chatSlice";
import { newConversationStart } from "../../store/slices/appSlice";
import { updateCitation } from "../../store/slices/citationSlice";
import { useAutoScroll, useChatApi, useChatHistorySave, useTextareaAutoResize } from "../../hooks";

type ChatProps = {
  onHandlePanelStates: (name: string) => void;
  panels: Record<string, string>;
  panelShowStates: Record<string, boolean>;
};

const Chat: React.FC<ChatProps> = ({
  onHandlePanelStates,
  panelShowStates,
  panels,
}) => {
  const dispatch = useAppDispatch();
  const userMessage = useAppSelector((s) => s.chat.userMessage);
  const generatingResponse = useAppSelector((s) => s.chat.generatingResponse);
  const messages = useAppSelector((s) => s.chat.messages);
  const isStreamingInProgress = useAppSelector((s) => s.chat.isStreamingInProgress);
  const selectedConversationId = useAppSelector((s) => s.app.selectedConversationId);
  const generatedConversationId = useAppSelector((s) => s.app.generatedConversationId);
  const isFetchingConvMessages = useAppSelector((s) => s.chatHistory.isFetchingConvMessages);
  const isHistoryUpdateAPIPending = useAppSelector((s) => s.chatHistory.isHistoryUpdateAPIPending);

  const questionInputRef = useRef<HTMLTextAreaElement>(null);
  const [isChartDisplayDefault, setIsChartDisplayDefault] = useState(false);

  // ── Custom hooks ──────────────────────────────
  const { scrollRef, scrollToBottom } = useAutoScroll([generatingResponse]);
  const { saveToDB } = useChatHistorySave();
  const {
    makeApiRequestWithCosmosDB,
    isChartLoading,
    parseCitationFromMessage,
    abortFuncs,
  } = useChatApi({
    scrollToBottom,
    saveToDB,
    questionInputRef,
    isChartDisplayDefault,
  });

  useTextareaAutoResize(questionInputRef, userMessage);

  // ── Derived / memoised values ─────────────────
  const isInputDisabled = useMemo(
    () => generatingResponse || isHistoryUpdateAPIPending,
    [generatingResponse, isHistoryUpdateAPIPending]
  );

  const isSendDisabled = useMemo(
    () => generatingResponse || !userMessage.trim() || isHistoryUpdateAPIPending,
    [generatingResponse, userMessage, isHistoryUpdateAPIPending]
  );

  const showLoadingIndicator = useMemo(
    () => (generatingResponse && !isStreamingInProgress) || isChartLoading,
    [generatingResponse, isStreamingInProgress, isChartLoading]
  );

  // ── Side-effects ──────────────────────────────
  useEffect(() => {
    try {
      const fetchFlag = async () => {
        const cfg = await getIsChartDisplayDefault();
        setIsChartDisplayDefault(cfg.isChartDisplayDefault);
      };
      fetchFlag();
    } catch (error) {
      console.error("Failed to fetch isChartDisplayDefault flag", error);
    }
  }, []);

  const saveToDB = async (newMessages: ChatMessage[], convId: string, reqType: string = 'Text') => {
    if (!convId || !newMessages.length) {
      return;
    }
    const isNewConversation = reqType !== 'graph' ? !state.selectedConversationId : false;
    dispatch({
      type: actionConstants.UPDATE_HISTORY_UPDATE_API_FLAG,
      payload: true,
    });

    if (((reqType !== 'graph' && reqType !== 'error') &&  newMessages[newMessages.length - 1].role !== ERROR) && isCharthDisplayDefault ){
      setIsChartLoading(true);
      setTimeout(()=>{
        makeApiRequestForChart('show in a graph by default', convId, newMessages[newMessages.length - 1].content as string)
      },5000)
      
    }
    await historyUpdate(newMessages, convId)
      .then(async (res) => {
        if (!res.ok) {
          if (!messages) {
            let err: Error = {
              ...new Error(),
              message: "Failure fetching current chat state.",
            };
            throw err;
          }
        }     
        let responseJson = await res.json();
        if (isNewConversation && responseJson?.success) {
          const newConversation: Conversation = {
            id: responseJson?.data?.conversation_id,
            title: responseJson?.data?.title,
            messages: state.chat.messages,
            date: responseJson?.data?.date,
            updatedAt: responseJson?.data?.date,
          };
          dispatch({
            type: actionConstants.ADD_NEW_CONVERSATION_TO_CHAT_HISTORY,
            payload: newConversation,
          });
          dispatch({
            type: actionConstants.UPDATE_SELECTED_CONV_ID,
            payload: responseJson?.data?.conversation_id,
          });
        }
        dispatch({
          type: actionConstants.UPDATE_HISTORY_UPDATE_API_FLAG,
          payload: false,
        });
        return res as Response;
      })
      .catch((err) => {
        console.error("Error: while saving data", err);
      })
      .finally(() => {
        dispatch({
          type: actionConstants.UPDATE_GENERATING_RESPONSE_FLAG,
          payload: false,
        });
        dispatch({
          type: actionConstants.UPDATE_HISTORY_UPDATE_API_FLAG,
          payload: false,
        });  
      });
  };


  const parseCitationFromMessage = (message : any) => {

      try {
        message = '{'+ message 
        const toolMessage = JSON.parse(message as string) as ToolMessageContent;
        
        return toolMessage.citations;
      } catch {
        // Silently ignore parse errors for incomplete JSON chunks. This is expected during streaming
      }
    return [];
  };
  const isChartQuery = (query: string) => {
    const chartKeywords = ["chart", "graph", "visualize", "plot"];
    return chartKeywords.some((keyword) =>
      query.toLowerCase().includes(keyword)
    );
  };

  useEffect(() => {
    if (generatingResponse || isStreamingInProgress) {
      const chatAPISignal = abortFuncs.current.shift();
      if (chatAPISignal) {
        chatAPISignal.abort("Chat Aborted due to switch to other conversation while generating");
      }
    }
  }, [selectedConversationId]);

  useEffect(() => {
    if (
      !state.chatHistory.isFetchingConvMessages &&
      chatMessageStreamEnd.current
    ) {
      setTimeout(() => {
        chatMessageStreamEnd.current?.scrollIntoView({ behavior: "auto" });
      }, 100);
    }
  }, [state.chatHistory.isFetchingConvMessages]);

  const scrollChatToBottom = () => {
    if (chatMessageStreamEnd.current) {
      setTimeout(() => {
        chatMessageStreamEnd.current?.scrollIntoView({ behavior: "smooth" });
      }, 100);
    }
  };

  useEffect(() => {
    scrollChatToBottom();
  }, [state.chat.generatingResponse]);

  const makeApiRequestForChart = async (
    question: string,
    conversationId: string,
    lrg: string
  ) => {
    if (generatingResponse || !question.trim()) {
      return;
    }

    const newMessage: ChatMessage = {
      id: generateUUIDv4(),
      role: "user",
      content: question,
      date: new Date().toISOString()
    };
    dispatch({
      type: actionConstants.UPDATE_GENERATING_RESPONSE_FLAG,
      payload: true,
    });
    scrollChatToBottom();
    dispatch({
      type: actionConstants.UPDATE_MESSAGES,
      payload: [newMessage],
    });
    dispatch({
      type: actionConstants.UPDATE_USER_MESSAGE,
      payload:  questionInputRef?.current?.value || "",
    });
    const abortController = new AbortController();
    abortFuncs.current.unshift(abortController);

    const request: ConversationRequest = {
      id: conversationId,
      query: question
    };

    const streamMessage: ChatMessage = {
      id: generateUUIDv4(),
      date: new Date().toISOString(),
      role: ASSISTANT,
      content: "",
    };
    let updatedMessages: ChatMessage[] = [];
    try {
      const response = await callConversationApi(
        request,
        abortController.signal
      );


      if (response?.body) {
        let isChartResponseReceived = false;
        const reader = response.body.getReader();
        let runningText = "";
        let hasError = false;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const text = new TextDecoder("utf-8").decode(value);
          try {
            const textObj = JSON.parse(text);
            if (textObj?.object?.data) {
              runningText = text;
              isChartResponseReceived = true;
            }
            if (textObj?.error) {
              hasError = true;
              runningText = text;
            }
          } catch (e) {
            // Silently ignore parse errors for incomplete JSON chunks. This is expected during streaming
          }

        }
        // END OF STREAMING
        if (hasError) {
          const errorMsg = JSON.parse(runningText).error;
          const errorMessage: ChatMessage = {
            id: generateUUIDv4(),
            role: ERROR,
            content: errorMsg,
            date: new Date().toISOString(),
          };
          updatedMessages = [newMessage, errorMessage];
          dispatch({
            type: actionConstants.UPDATE_MESSAGES,
            payload: [errorMessage],
          });
          scrollChatToBottom();
        } else if (isChartQuery(question)) {
          try {
            const parsedChartResponse = JSON.parse(runningText);
            if (
              "object" in parsedChartResponse &&
              parsedChartResponse?.object?.type &&
              parsedChartResponse?.object?.data
            ) {
              // CHART CHECKING
              try {
                const chartMessage: ChatMessage = {
                  id: generateUUIDv4(),
                  role: ASSISTANT,
                  content:
                    parsedChartResponse.object as unknown as ChartDataResponse,
                  date: new Date().toISOString(),
                };
                updatedMessages = [newMessage, chartMessage];
                // Update messages with the response content
                dispatch({
                  type: actionConstants.UPDATE_MESSAGES,
                  payload: [chartMessage],
                });
                scrollChatToBottom();
              } catch (e) {
                console.error("Error handling assistant response:", e);
                const chartMessage: ChatMessage = {
                  id: generateUUIDv4(),
                  role: ASSISTANT,
                  content: "Error while generating Chart.",
                  date: new Date().toISOString(),
                };
                updatedMessages = [newMessage, chartMessage];
                dispatch({
                  type: actionConstants.UPDATE_MESSAGES,
                  payload: [chartMessage],
                });
                scrollChatToBottom();
              }
            } else if (
              parsedChartResponse.error 
            ) {
              const errorMsg =
                parsedChartResponse.error ||
                parsedChartResponse?.object?.message;
              const errorMessage: ChatMessage = {
                id: generateUUIDv4(),
                role: ERROR,
                content: errorMsg,
                date: new Date().toISOString(),
              };
              updatedMessages = [
                ...state.chat.messages,
                newMessage,
                errorMessage,
              ];
              dispatch({
                type: actionConstants.UPDATE_MESSAGES,
                payload: [errorMessage],
              });
              scrollChatToBottom();
            }
          } catch (e) {
            // Silently ignore parse errors for incomplete JSON chunks for chart response. This is expected during streaming
          }
        }
      }
      saveToDB(updatedMessages, conversationId, 'graph');
    } catch (e) {
      console.log("Caught with an error while chat and save", e);
      if (abortController.signal.aborted) {
        if (streamMessage.content) {
          updatedMessages = [newMessage, streamMessage];
        } else {
          updatedMessages = [newMessage];
        }
        console.log(
          "@@@ Abort Signal detected: Formed updated msgs",
          updatedMessages
        );
        saveToDB(updatedMessages, conversationId, 'graph');
      }

      if (!abortController.signal.aborted) {
        if (e instanceof Error) {
          alert(e.message);
        } else {
          alert(
            "An error occurred. Please try again. If the problem persists, please contact the site administrator."
          );
        }
      }
    } finally {


      dispatch({
        type: actionConstants.UPDATE_GENERATING_RESPONSE_FLAG,
        payload: false,
      });
      dispatch({
        type: actionConstants.UPDATE_STREAMING_FLAG,
        payload: false,
      });
      setIsChartLoading(false);
    }
    return abortController.abort();
  };

  const makeApiRequestWithCosmosDB = async (
    question: string,
    conversationId: string
  ) => {
    if (generatingResponse || !question.trim()) {
      return;
    }
    const isChatReq = isChartQuery(userMessage) ? "graph" : "Text"
    const newMessage: ChatMessage = {
      id: generateUUIDv4(),
      role: "user",
      content: question,
      date: new Date().toISOString(),
    };
    dispatch({
      type: actionConstants.UPDATE_GENERATING_RESPONSE_FLAG,
      payload: true,
    });
    scrollChatToBottom();
    dispatch({
      type: actionConstants.UPDATE_MESSAGES,
      payload: [newMessage],
    });
    dispatch({
      type: actionConstants.UPDATE_USER_MESSAGE,
      payload: "",
    });
    const abortController = new AbortController();
    abortFuncs.current.unshift(abortController);

    const request: ConversationRequest = {
      id: conversationId,
      query: question
    };

    const streamMessage: ChatMessage = {
      id: generateUUIDv4(),
      date: new Date().toISOString(),
      role: ASSISTANT,
      content: "",
      citations:"",
    };
    let updatedMessages: ChatMessage[] = [];
    try {
      const response = await callConversationApi(
        request,
        abortController.signal
      );

      if (response?.body) {
        let isChartResponseReceived = false;
        const reader = response.body.getReader();
        let runningText = "";
        let hasError = false;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const text = new TextDecoder("utf-8").decode(value);
          try {
            const textObj = JSON.parse(text);
            if (textObj?.object?.data) {
              runningText = text;
              isChartResponseReceived = true;
            }
            if (textObj?.object?.message) {
              runningText = text;
              isChartResponseReceived = true;
            }
            if (textObj?.error) {
              hasError = true;
              runningText = text;
            }
          } catch (e) {
            // Ignore - will process individual chunks after splitting
          }
          if (!isChartResponseReceived) {
            //text based streaming response
            const objects = text.split("\n").filter((val) => val !== "");
            let answerText='';
            let citationString ='';
            let answerTextStart  = 0;
            objects.forEach((textValue, index) => {
              try {
                if (textValue !== "" && textValue !== "{}") {
                  const parsed: ParsedChunk = JSON.parse(textValue);
                  if (parsed?.error && !hasError) {
                    hasError = true;
                    runningText = parsed?.error;
                  } else if (isChartQuery(userMessage) && !hasError) {
                    runningText = runningText + textValue;
                  } else if (typeof parsed === "object" && !hasError) {
                    const responseContent  = parsed?.choices?.[0]?.messages?.[0]?.content;
                     
                    const answerKey = `"answer":`;
                    const answerStartIndex  = responseContent.indexOf(answerKey);

                    if (answerStartIndex  !== -1) {
                      answerTextStart  =responseContent .indexOf(`"answer":`) +9;
                    } 
                 
                    const citationsKey = `"citations":`;
                    const citationsStartIndex = responseContent.indexOf(citationsKey);

                    if(citationsStartIndex > answerTextStart ){
                      answerText = responseContent .substring(answerTextStart, citationsStartIndex).trim();
                      citationString = responseContent .substring(citationsStartIndex).trim();
                    }else{
                      answerText = responseContent .substring(answerTextStart).trim();
                    }

                      answerText = answerText.replace(/^"+|"+$|,$/g, '');// first ""
                      answerText = answerText.replace(/[",]+$/, ''); // last ",
                      answerText = answerText.replace(/\\n/g, "  \n");
                    
                    
                    streamMessage.content = answerText || "";
                    streamMessage.role =
                      parsed?.choices?.[0]?.messages?.[0]?.role || ASSISTANT;

                    streamMessage.citations = citationString;
                    dispatch({
                      type: actionConstants.UPDATE_MESSAGE_BY_ID,
                      payload: streamMessage,
                    });
                    scrollChatToBottom();
                  }
                }
              } catch (e) {
                // Skip incomplete JSON chunks in stream
              }
            });
            if (hasError) {
              console.log("STOPPED DUE TO ERROR FROM API RESPONSE");
              break;
            }
          }
        }
        // END OF STREAMING
        if (hasError) {
          const errorMsg = JSON.parse(runningText).error === "Attempted to access streaming response content, without having called `read()`."?"An error occurred. Please try again later.": JSON.parse(runningText).error;
          
          const errorMessage: ChatMessage = {
            id: generateUUIDv4(),
            role: ERROR,
            content: errorMsg,
            date: new Date().toISOString(),
          };
          updatedMessages = [newMessage, errorMessage];
          dispatch({
            type: actionConstants.UPDATE_MESSAGES,
            payload: [errorMessage],
          });
          scrollChatToBottom();
        } else if (isChartQuery(userMessage)) {
          try {
            const splitRunningText = runningText.split("}{");
            let parsedChartResponse: any = {};
            parsedChartResponse= JSON.parse("{" + splitRunningText[splitRunningText.length - 1]);
            let chartResponse : any = {};
            try {
              chartResponse = JSON.parse(parsedChartResponse?.choices[0]?.messages[0]?.content)
            } catch (e) {
              chartResponse = parsedChartResponse?.choices[0]?.messages[0]?.content;
            }
            
            if (typeof chartResponse === 'object' &&  'answer' in chartResponse) {
              if (
                chartResponse.answer === "" ||
                chartResponse.answer === undefined ||
                (typeof chartResponse.answer === "object" && Object.keys(chartResponse.answer).length === 0)
              ) {
                chartResponse = "Chart can't be generated, please try again.";
              } else {
                chartResponse = chartResponse.answer;
              }
            }
            
            if (
              chartResponse?.type &&
              chartResponse?.data
            ) {
              // CHART CHECKING
              try {
                const chartMessage: ChatMessage = {
                  id: generateUUIDv4(),
                  role: ASSISTANT,
                  content:
                    chartResponse as unknown as ChartDataResponse,
                  date: new Date().toISOString(),
                };
                updatedMessages = [newMessage, chartMessage];
                // Update messages with the response content
                dispatch({
                  type: actionConstants.UPDATE_MESSAGES,
                  payload: [chartMessage],
                });
                scrollChatToBottom();
              } catch (e) {
                console.error("Error handling assistant response:", e);
                const chartMessage: ChatMessage = {
                  id: generateUUIDv4(),
                  role: ASSISTANT,
                  content: "Error while generating Chart.",
                  date: new Date().toISOString(),
                };
                updatedMessages = [newMessage, chartMessage];
                dispatch({
                  type: actionConstants.UPDATE_MESSAGES,
                  payload: [chartMessage],
                });
                scrollChatToBottom();
              }
            } else if (
              parsedChartResponse?.error ||
              parsedChartResponse?.choices[0]?.messages[0]?.content
            ) {
              let content = parsedChartResponse?.choices[0]?.messages[0]?.content;
              let displayContent = content;
              try {
                const parsed = typeof content === "string" ? JSON.parse(content) : content;
                if (parsed && typeof parsed === "object" && "answer" in parsed) {
                  displayContent = parsed.answer;
                }
              } catch {
                displayContent = content;
              }
              const errorMsg =
                parsedChartResponse?.error ||
                parsedChartResponse?.choices[0]?.messages[0]?.content
              const errorMessage: ChatMessage = {
                id: generateUUIDv4(),
                role: ERROR,
                content: errorMsg,
                date: new Date().toISOString(),
              };
              updatedMessages = [newMessage, errorMessage];
              dispatch({
                type: actionConstants.UPDATE_MESSAGES,
                payload: [errorMessage],
              });
              scrollChatToBottom();
            }
          } catch (e) {
            console.log("Error while parsing charts response", e);
          }
        } else if (!isChartResponseReceived) {
          updatedMessages = [newMessage, streamMessage];
        }
      }
      if (updatedMessages[updatedMessages.length-1]?.role !== "error") {
        saveToDB(updatedMessages, conversationId, isChatReq);
      }
    } catch (e) {
      console.log("Caught with an error while chat and save", e);
      if (abortController.signal.aborted) {
        if (streamMessage.content) {
          updatedMessages = [newMessage, streamMessage];
        } else {
          updatedMessages = [newMessage];
        }
        console.log(
          "@@@ Abort Signal detected: Formed updated msgs",
          updatedMessages
        );
        saveToDB(updatedMessages, conversationId, 'error');
      }

      if (!abortController.signal.aborted) {
        if (e instanceof Error) {
          alert(e.message);
        } else {
          alert(
            "An error occurred. Please try again. If the problem persists, please contact the site administrator."
          );
        }
      }
    } finally {
      dispatch({
        type: actionConstants.UPDATE_GENERATING_RESPONSE_FLAG,
        payload: false,
      });
      dispatch({
        type: actionConstants.UPDATE_STREAMING_FLAG,
        payload: false,
      });
      
    }
    return abortController.abort();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const conversationId =
        state?.selectedConversationId || state.generatedConversationId;
      if (userMessage) {
        makeApiRequestWithCosmosDB(userMessage, conversationId);
      }
      if (questionInputRef?.current) {
        questionInputRef?.current.focus();
      }
    },
    [selectedConversationId, generatedConversationId, userMessage, makeApiRequestWithCosmosDB]
  );

  const onClickSend = useCallback(() => {
    const conversationId = selectedConversationId || generatedConversationId;
    if (userMessage) {
      makeApiRequestWithCosmosDB(userMessage, conversationId);
    }
    questionInputRef?.current?.focus();
  }, [selectedConversationId, generatedConversationId, userMessage, makeApiRequestWithCosmosDB]);

  const setUserMessageValue = useCallback(
    (value: string) => {
      dispatch(setUserMessage(value));
    },
    [dispatch]
  );

  const onNewConversation = useCallback(() => {
    dispatch(newConversationStart());
    dispatch(clearMessages());
    dispatch(updateCitation({ activeCitation: null, showCitation: false }));
  }, [dispatch]);
  return (
    <div className="chat-container">
      <div className="chat-header">
        <Subtitle2>Chat</Subtitle2>
        <span>
          <Button
            appearance="outline"
            onClick={() => onHandlePanelStates(panels.CHATHISTORY)}
            className="hide-chat-history"
          >
            {`${panelShowStates?.[panels.CHATHISTORY] ? "Hide" : "Show"
              } Chat History`}
          </Button>
        </span>
      </div>
      <div className="chat-messages">
        {Boolean(isFetchingConvMessages) && (
          <div>
            <Spinner
              size={SpinnerSize.small}
              aria-label="Fetching Chat messages"
            />
          </div>
        )}
        {!Boolean(isFetchingConvMessages) &&
          messages.length === 0 && (
            <div className="initial-msg">
              {/* <SparkleRegular fontSize={32} /> */}
              <h2>✨</h2>
              <Subtitle2>Start Chatting</Subtitle2>
              <Body1 style={{ textAlign: "center" }}>
                You can ask questions around customers calls, call topics and
                call sentiments.
              </Body1>
            </div>
          )}
        {!Boolean(isFetchingConvMessages) &&
          messages.map((msg, index: number) => (
            <div key={index} className={`chat-message ${msg.role}`}>
              {(() => {
                 const isLastAssistantMessage =
                 msg.role === "assistant" && index === messages.length - 1;
                if ((msg.role === "user") && typeof msg.content === "string") {
                  if (msg.content == "show in a graph by default") return null;
                    return (
                      <div className="user-message">
                        <span>{msg.content}</span>
                      </div>
                    );

                }
                msg.content = msg.content as ChartDataResponse;
                if (msg?.content?.type && msg?.content?.data) {
                  return (
                    <div className="assistant-message chart-message">
                      <ChatChart chartContent={msg.content} />
                      <div className="answerDisclaimerContainer">
                        <span className="answerDisclaimer">
                          AI-generated content may be incorrect
                        </span>
                      </div>
                    </div>
                  );
                }
                if (typeof msg.content === "string") {
                  return (
                    <div className="assistant-message">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm, supersub]}
                        children={msg.content}
                      />
                     {/* Citation Loader: Show only while citations are fetching */}
                      {isLastAssistantMessage && generatingResponse ? (
                        <div className="typing-indicator">
                          <span className="dot"></span>
                          <span className="dot"></span>
                          <span className="dot"></span>
                        </div>
                      ) : (
                        <Citations
                            answer={{
                              answer: msg.content,
                              citations:
                                msg.role === "assistant" && msg.citations
                                  ? typeof msg.citations === "string"
                                    ? parseCitationFromMessage(msg.citations)
                                    : Array.isArray(msg.citations)
                                      ? msg.citations
                                      : []
                                  : [],
                            }}
                            index={index}
                          />
                      )}

                      <div className="answerDisclaimerContainer">
                        <span className="answerDisclaimer">
                          AI-generated content may be incorrect
                        </span>
                      </div>
                    </div>
                  );
                }
              })()}
            </div>
          ))}
        {showLoadingIndicator && (
          <div className="assistant-message loading-indicator">
            <div className="typing-indicator">
              <span className="generating-text">{isChartLoading ? "Generating chart if possible with the provided data" : "Generating answer"} </span>
              <span className="dot"></span>
              <span className="dot"></span>
              <span className="dot"></span>
            </div>
          </div>
        )}
        <div data-testid="streamendref-id" ref={scrollRef} />
      </div>
      <div className="chat-footer">
        <Button
          className="btn-create-conv"
          shape="circular"
          appearance="primary"
          icon={<ChatAdd24Regular />}
          onClick={onNewConversation}
          title="Create new Conversation"
          disabled={isInputDisabled}
        />
        <div className="text-area-container">
          <Textarea
            className="textarea-field"
            value={userMessage}
            onChange={(e, data) => setUserMessageValue(data.value || "")}
            placeholder="Ask a question..."
            onKeyDown={handleKeyDown}
            ref={questionInputRef}
            rows={2}
            style={{ resize: "none" }}
            appearance="outline"
          />
          <DefaultButton
            iconProps={{ iconName: "Send" }}
            role="button"
            onClick={onClickSend}
            disabled={isSendDisabled}
            className="send-button"
            aria-disabled={isSendDisabled}
            title="Send Question"
          />
        </div>
      </div>
    </div>
  );
};

Chat.displayName = "Chat";

export default Chat;
