
import { cloneDeep } from "lodash-es";
import { AskResponse, Citation } from "../../types/AppTypes";


type ParsedAnswer = {
    citations: Citation[];
    markdownFormatText: string;
};

const answerTextFormatting = (answer : AskResponse)=> {
    let answerText = answer.answer;
    const docCitations = answerText.match(/\[(doc\d\d?\d?)]/g);
    // console.log("docCitations::",docCitations);
    const lengthDocN = "[doc".length;
    let citationIndexMapping:any ={}
    // ['[doc4]', '[doc5]', '[doc1]','[doc4]']
    //{4: 0, 5:1,1:2,}
    let citationCount = 0;
    docCitations?.forEach(link => {
        // Replacing the links/citations with number
        let citationIndex = link.slice(lengthDocN, link.length - 1);
        // console.log("citationIndex::",citationIndex);
        if(citationIndexMapping[citationIndex] === undefined){
            citationIndexMapping[citationIndex] = citationCount
            citationCount++;
        }
        let citation = cloneDeep(answer.citations[Number(citationIndexMapping[citationIndex])]) as Citation;
        // console.log("citation::",citation);
        if (citation !== undefined ) { 
            // console.log("inside::");
          answerText = answerText.replaceAll(link, ` ^${++citationIndexMapping[citationIndex]}^ `);
        }
       
    })

    // console.log(" answer.citations::",  answer.citations)
    // console.log("answerText::", answerText)
    // console.log("answer.answer::", answer.answer)

    return answerText
}

const UniqueCitationResponse = (answer: AskResponse)=>{
    let citations = answer.citations;
    let citationIndexMapping:any = {}
    let uniqueCitations: Citation[] =[];
    citations.forEach(citation => {
        // Replacing the links/citations with number
        if(!citation.url){
            uniqueCitations.push(citation)
        }else if(citationIndexMapping[citation.url] === undefined){
            citationIndexMapping[citation.url] = 1
            uniqueCitations.push(citation)
        }
    })
    return uniqueCitations;
}

export function parseAnswer(answer: AskResponse): ParsedAnswer {

    let answerText = answerTextFormatting(answer)
    let uniqueCitation = UniqueCitationResponse(answer)
    return {
        citations: uniqueCitation, //answer.citations,
        markdownFormatText:  answerText
    };
}
// 3,4,1,3
// [3,4,1]
// 3,3,4,4,3,1,4,1
//3,1,4,4,3,1,4,1
// []