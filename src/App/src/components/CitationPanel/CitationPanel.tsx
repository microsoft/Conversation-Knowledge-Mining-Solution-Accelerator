import React, { useCallback } from "react";
import ReactMarkdown from "react-markdown";
import { Stack } from "@fluentui/react";
import { DismissRegular } from "@fluentui/react-icons";
import remarkGfm from "remark-gfm";
import { useAppDispatch } from "../../state/hooks";
import { hideCitation } from "../../state/slices/citationSlice";
import "./CitationPanel.css";

interface Props {
  activeCitation: any;
}

const CitationPanelComponent: React.FC<Props> = ({ activeCitation }) => {
  const dispatch = useAppDispatch();

  const handleCloseCitation = useCallback(() => {
    dispatch(hideCitation());
  }, [dispatch]);

  return (
    <div className="citationPanel">
      <Stack.Item>
        <Stack
          horizontal
          horizontalAlign="space-between"
          verticalAlign="center"
        >
          <div
            role="heading"
            aria-level={2}
            style={{
              fontWeight: "600",
              fontSize: "16px",
            }}
          >
            Citations
          </div>
          <DismissRegular
            role="button"
            onKeyDown={(event) => {
              if (event.key === " " || event.key === "Enter") {
                event.preventDefault();
                handleCloseCitation();
              }
            }}
            tabIndex={0}
            onClick={handleCloseCitation}
          />
        </Stack>
        <h5>{activeCitation.title}</h5>

        <ReactMarkdown
          children={activeCitation?.content}
          remarkPlugins={[remarkGfm]}
        />
      </Stack.Item>
    </div>
  );
};

const CitationPanel = React.memo(CitationPanelComponent);
CitationPanel.displayName = "CitationPanel";

export default CitationPanel;