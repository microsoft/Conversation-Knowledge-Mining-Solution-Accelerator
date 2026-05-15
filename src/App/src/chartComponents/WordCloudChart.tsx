import React, { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import cloud from "d3-cloud";
import { colors, normalize } from "../configs/Utils";
interface WordCloudData {
  words: {
    text: string;
    size: number;
    average_sentiment: "positive" | "negative" | "neutral";
  }[];
}

interface WordCloudChartProps {
  data: WordCloudData;
  title: string;
  containerHeight: number;
  widthInPixels: number;
}

const WordCloudChart: React.FC<WordCloudChartProps> = ({
  data,
  title,
  containerHeight,
  widthInPixels = 300,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({
    width: widthInPixels,
    height: containerHeight,
  });

  const wordsSignature = useMemo(
    () =>
      data.words
        .map((word) => `${word.text}-${word.size}-${word.average_sentiment}`)
        .join(","),
    [data.words]
  );

  useEffect(() => {
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        setDimensions({ width, height });
      }
    });

    const containerElement = containerRef.current;
    if (containerElement) {
      resizeObserver.observe(containerElement);
    }

    return () => {
      if (containerElement) {
        resizeObserver.unobserve(containerElement);
      }
    };
  }, []);

  useEffect(() => {
    const HEIGHT_OFFSET = 30;
    const margin = { top: 10, right: 10, bottom: 10, left: 10 };
    const width = dimensions.width - margin.left - margin.right;
    const height =
      dimensions.height - margin.top - margin.bottom - HEIGHT_OFFSET;

    // Clear previous SVG elements
    d3.select("#wordcloud").selectAll("*").remove();

    // calculate min and max
    function getMinMax(arr: any) {
      const minMax = arr.reduce(
        (acc: any, curr: any) => {
          if (acc.min === -Infinity) acc.min = curr.size;
          if (curr.size < acc.min) acc.min = curr.size;
          if (curr.size > acc.max) acc.max = curr.size;
          return acc;
        },
        { min: Infinity, max: -Infinity }
      );
      return [minMax.min, minMax.max];
    }

    const result = getMinMax(data.words) as number[];
    const ref = [15, 39];

    // Prepare words data
    const words = data.words.map((d) => ({
      text: d.text,
      size: d.size,
      color: colors[d.average_sentiment],
    }));

    const layout = cloud()
      .size([width, height])
      .words(words)
      .padding(5)
      .fontSize((d) => normalize(d.size, result, ref))
      .rotate(() => 0) // Fix rotation to 0
      .on("end", (words: any) => {
        draw(words);
      });

    layout.start();

    function draw(
      words: {
        text: string;
        size: number;
        x: number;
        y: number;
        rotate: number;
        color: string;
      }[]
    ) {

      const svg = d3
        .select("#wordcloud")
        .append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .append("g")
        .attr("transform", `translate(${width / 2}, ${height / 2})`);
      const padding = 8;
      svg
        .selectAll("text")
        .data(words)
        .enter()
        .append("text")
        .style("font-size", (d) => `${d.size}px`)
        .style("fill", (d) => d.color || "#69b3a2")
        .attr("text-anchor", "middle")
        .attr(
          "transform",
          (d) =>
            `translate(${d.x + padding}, ${d.y + padding}) rotate(${d.rotate})`
        )
        .text((d) => d.text);
    }
  }, [data.words, dimensions, wordsSignature]);

  return (
    <div style={WordCloudStyles.mainContainer} ref={containerRef}>
      <div id="wordcloud" style={{ width: "100%", height: "100%" }} />
    </div>
  );
};

export default WordCloudChart;

const WordCloudStyles = {
  mainContainer: {
    backgroundColor: "#fff",
    borderRadius: "8px",
    boxShadow: "0px 1px 5px rgba(0, 0, 0, 0.1)",
    width: "100%",
    height: "90%",
    overflow: "hidden",
  },
};
