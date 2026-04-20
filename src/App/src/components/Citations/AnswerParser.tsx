import { AskResponse, Citation } from "../../types/AppTypes";

type ParsedAnswer = {
  citations: Citation[];
  markdownFormatText: string;
};

export function parseAnswer(answer: AskResponse): ParsedAnswer {
  return {
    citations: answer.citations,
    markdownFormatText: answer.answer,
  };
}
