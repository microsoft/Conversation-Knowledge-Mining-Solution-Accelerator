import React, { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Stack } from '@fluentui/react';
import { DismissRegular } from '@fluentui/react-icons';
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { useAppContext } from '../../state/useAppContext';
import { actionConstants } from '../../state/ActionConstants';
import "./CitationPanel.css";
interface Props {
    activeCitation: any
}

const CitationPanel = ({ activeCitation }: Props) => {
    const { dispatch } = useAppContext()
  
    const onCloseCitation = () => {
        dispatch({  type: actionConstants.UPDATE_CITATION,payload: { activeCitation: null, showCitation: false }})
    }
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
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw]}
              />
            </Stack.Item>
        </div>)
};


export default CitationPanel;