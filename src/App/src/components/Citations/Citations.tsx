import React, { useCallback, useMemo } from "react";
import { parseAnswer } from "./AnswerParser";
import { useAppDispatch, useAppSelector } from "../../state/hooks";
import { setCitationState } from "../../state/slices/citationSlice";
import "./Citations.css";
import { AskResponse, Citation } from "../../types/AppTypes";
import { fetchCitationContent } from "../../api/api";

interface Props {
  answer: AskResponse;
  onSpeak?: unknown;
  isActive?: boolean;
  index: number;
}

const CitationsComponent: React.FC<Props> = ({ answer, index }) => {
  const dispatch = useAppDispatch();
  const selectedConversationId = useAppSelector(
    (state) => state.app.selectedConversationId
  );
  const parsedAnswer = useMemo(() => parseAnswer(answer), [answer]);

  const createCitationFilepath = useCallback(
    (citation: Citation, citationIndex: number) =>
      citation.title ? citation.title : `Citation ${citationIndex}`,
    []
  );

  const handleCitationClicked = useCallback(
    async (citation: Citation) => {
      const citationContent = await fetchCitationContent(citation);
      dispatch(
        setCitationState({
          showCitation: true,
          activeCitation: {
            ...citation,
            content: citationContent.content,
            title: citationContent.title,
          },
          currentConversationIdForCitation: selectedConversationId,
        })
      );
    },
    [dispatch, selectedConversationId]
  );

  return (
    <div
      style={{
        marginTop: 8,
        display: "flex",
        flexDirection: "column",
        height: "100%",
        gap: "4px",
        maxWidth: "100%",
      }}
    >
      {parsedAnswer.citations.map((citation, citationOffset) => {
        const displayIndex = citationOffset + 1;

        return (
          <span
            role="button"
            onKeyDown={(event) =>
              event.key === " " || event.key === "Enter"
                ? handleCitationClicked(citation)
                : undefined
            }
            tabIndex={0}
            title={createCitationFilepath(citation, displayIndex)}
            key={`${index}-${displayIndex}-${citation.chunk_id ?? citation.id}`}
            onClick={() => handleCitationClicked(citation)}
            className="citationContainer"
          >
            <div className="citation">{displayIndex}</div>
            {createCitationFilepath(citation, displayIndex)}
          </span>
        );
      })}
    </div>
  );
};

const Citations = React.memo(CitationsComponent);
Citations.displayName = "Citations";

export default Citations;