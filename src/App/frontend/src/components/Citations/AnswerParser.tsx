
import { cloneDeep } from "lodash-es";
import { AskResponse, Citation } from "../../types/AppTypes";


type ParsedAnswer = {
    citations: Citation[];
    markdownFormatText: string;
};

let filteredCitations = [] as Citation[];

// Define a function to check if a citation with the same Chunk_Id already exists in filteredCitations
const isDuplicate = (citation: Citation,citationIndex:string) => {
    console.log("citation::",citation);
    console.log("citationIndex 16::",citationIndex);
    console.log("filteredCitations 17::",filteredCitations);
    console.log("filteredCitations.some((c) => c.chunk_id === citation.chunk_id)::", filteredCitations.some((c) => c.chunk_id === citation.chunk_id))
    return filteredCitations.some((c) => c.chunk_id === citation.chunk_id) ;
};

export function parseAnswer(answer: AskResponse): ParsedAnswer {
    let answerText = answer.answer;
    const citationLinks = answerText.match(/\[(doc\d\d?\d?)]/g);
    console.log("citationLinks::",citationLinks);
    const lengthDocN = "[doc".length;

    filteredCitations = [] as Citation[];
    let citationReindex = 0;
    citationLinks?.forEach(link => {
        // Replacing the links/citations with number
        let citationIndex = link.slice(lengthDocN, link.length - 1);
        console.log("citationIndex::",citationIndex);
        let citation = cloneDeep(answer.citations[Number(citationIndex) - 1]) as Citation;
        console.log("citation::",citation);
        if (citation !== undefined ) { //&& !isDuplicate(citation, citationIndex)
            console.log("inside::");
          answerText = answerText.replaceAll(link, ` ^${++citationReindex}^ `);
          citation.id = citationIndex; // original doc index to de-dupe
          citation.reindex_id = citationReindex.toString(); // reindex from 1 for display
          console.log("citationReindex::",citationReindex);
          filteredCitations.push(citation);
        
        }else{
            // Replacing duplicate citation with original index
            let matchingCitation = filteredCitations.find((ct) => citation?.chunk_id == ct?.chunk_id);
            if (matchingCitation) {
                answerText= answerText.replaceAll(link, ` ^${matchingCitation.reindex_id}^ `)
            }
        }
    })

    console.log(" answer.citations::",  answer.citations)
    console.log("answerText::", answerText)
    console.log("answer.answer::", answer.answer)
    return {
        citations: answer.citations,
        markdownFormatText:  answerText
    };
}
// 3,4,1,3
// [3,4,1]
// 3,3,4,4,3,1,4,1
//3,1,4,4,3,1,4,1
// []