import React, { useMemo } from 'react';
import { parseAnswer } from './AnswerParser';
import { useAppContext } from '../../state/useAppContext';
import { actionConstants } from '../../state/ActionConstants';
import "./Citations.css";
import { AskResponse, Citation } from '../../types/AppTypes';
import { fetchCitationContent } from '../../api/api';

interface Props {
    answer: AskResponse;
    onSpeak?: any;
    isActive?: boolean;
    index: number;
}

const Citations = ({ answer, index }: Props) => {
    
    const { state, dispatch } = useAppContext();
    const parsedAnswer = useMemo(() => parseAnswer(answer), [answer]);
    const filePathTruncationLimit = 50;
    const createCitationFilepath = (
        citation: Citation,
        index: number,
        truncate: boolean = false
    ) => {
        let citationFilename = "";
            citationFilename =  citation.title ? (citation.title ?? `Citation ${index}`) : `Citation ${index}`;
        return citationFilename;
    };

    const onCitationClicked = async (
        citation: Citation
    ) => {  
        // let citationv = {
        //     "content": "",
        //     "url": "https://kmpnqiikor537m-search.search.windows.net/indexes/call_transcripts_index/docs/5b8e9e1f-04d4-4f0d-bae6-fc4f8af9486f_01?api-version=2024-07-01&$select=id,content",
        //     "title": "doc_2"
        // }
        const citationContent = await fetchCitationContent(citation);//(citation.url);

        // console.log("Fetched citation content", citationContent)
        // console.log("Citation clicked", citation);
        dispatch({
            type: actionConstants.UPDATE_CITATION,
            payload: { showCitation: true, activeCitation: {...citation, content:citationContent.content.content} },
        });
    };


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
            {parsedAnswer?.citations.map((citation, idx) => {
                return (
                    <span
                        role="button"
                        onKeyDown={(e) =>
                            e.key === " " || e.key === "Enter"
                                ? onCitationClicked(citation)
                                : () => { }
                        }
                        tabIndex={0}
                        title={createCitationFilepath(citation, ++idx)}
                        key={idx}
                        onClick={() => onCitationClicked(citation)}
                     className={"citationContainer"}
                    >
                        <div
                             className={"citation"} 
                            key={idx}>
                            {idx}
                        </div>
                        {createCitationFilepath(citation, idx, true)}
                    </span>
                );
            })}
        </div>)
};


export default Citations;