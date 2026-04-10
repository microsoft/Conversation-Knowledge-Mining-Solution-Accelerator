import React, { useCallback, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import { Stack } from '@fluentui/react';
import { DismissRegular } from '@fluentui/react-icons';
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { useAppDispatch } from '../../store/hooks';
import { updateCitation } from '../../store/slices/citationSlice';
import "./CitationPanel.css";
interface Props {
    activeCitation: any
}

const CitationPanel: React.FC<Props> = React.memo(({ activeCitation }) => {
    const dispatch = useAppDispatch()

    const onCloseCitation = useCallback(() => {
        dispatch(updateCitation({ activeCitation: null, showCitation: false }))
    }, [dispatch])

    const remarkPluginsMemo = useMemo(() => [remarkGfm], []);
    const rehypePluginsMemo = useMemo(() => [rehypeRaw], []);
    return (
        <div className='citationPanel'>

            <Stack.Item
            
            >
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
                            fontSize: '16px'
                        }}
                        >

                    Citations
                    </div>
                    <DismissRegular
                        role="button"
                        onKeyDown={(e) =>
                            e.key === " " || e.key === "Enter"
                                ? onCloseCitation()
                                : () => { }
                        }
                        tabIndex={0}
                        onClick={onCloseCitation}
                    />
                </Stack>
                <h5
                  
                >
                    {activeCitation.title}
                </h5>
              
                <ReactMarkdown
                children={activeCitation?.content}
                remarkPlugins={remarkPluginsMemo}
                rehypePlugins={rehypePluginsMemo}
              />
            </Stack.Item>
        </div>)
});

CitationPanel.displayName = "CitationPanel";

export default CitationPanel;