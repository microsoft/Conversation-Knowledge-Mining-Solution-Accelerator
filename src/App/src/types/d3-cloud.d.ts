declare module 'd3-cloud' {
    export interface Word {
      text: string;
      size: number;
      x?: number;
      y?: number;
      rotate?: number;
    }
  
    export interface Cloud {
      size: (size: [number, number]) => Cloud;
      words: (words: Word[]) => Cloud;
      padding: (padding: number) => Cloud;
      rotate: (rotate: () => number) => Cloud;
      font: (font: string) => Cloud;
      fontSize: (size: (word: Word) => number) => Cloud;
      on: (event: 'end', callback: (words: Word[]) => void) => Cloud;
      start: () => void;
    }
  
    export default function cloud(): Cloud;
  }
  