import React, { useEffect, useRef } from "react";
import * as d3 from "d3";

interface BarChartProps {
  title: string;
  data: { category: string; value: number }[];
  yLabel?: string;
  containerHeight: number;
  containerID: string;
}

interface DataWithFullCategoryText {
  category: string;
  value: number;
  fullCategoryText: string; // Added the fullCategoryText property
}

const BarChart: React.FC<BarChartProps> = ({
  title,
  data,
  yLabel,
  containerHeight,
  containerID,
}) => {
  const chartRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const containerWidth =
      document?.getElementById(containerID)!.clientWidth || 200;
    const svg = d3.select(chartRef.current);
    svg.selectAll("*").remove(); // Clear previous render
    d3.selectAll("#tooltip-container").remove(); // Ensuring the previous tooltip is removed.
    const modifiedData: DataWithFullCategoryText[] = data.map((ob) => {
      let truncatedCategory = ob.category;
  
      if (containerWidth <= 500 && truncatedCategory.length>20) {
        truncatedCategory = ob.category.substring(0, 20) + "...";
      }else if(containerWidth >500 && truncatedCategory.length>30){
        truncatedCategory = ob.category.substring(0, 30) + "..."; 
      } else {
        truncatedCategory = ob.category
      }
      return {
        ...ob,
        category: truncatedCategory, 
        fullCategoryText: ob.category, 
      };
    });

    const adjustedContainerHeight = containerHeight - 40;
    const widthOffset = 25;
    const margin = {
      top: 40,
      right: 20,
      bottom: 30,
      left: containerWidth > 500 ? 180 : 120,
    };
    const width = containerWidth - margin.left - margin.right - widthOffset;
    const height = adjustedContainerHeight; 

    const g = svg
      .attr("width", width + margin.left + margin.right)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const x = d3
      .scaleLinear()
      .domain([0, d3.max(modifiedData, (d) => d.value)!])
      .range([0, width]);

    const y = d3
      .scaleBand()
      .domain(modifiedData.map((d) => d.category))
      .range([0, adjustedContainerHeight - margin.top - margin.bottom])
      .padding(0.2);

    const colorScale = d3
      .scaleSequential(d3.interpolateBlues)
      .domain([0, d3.max(modifiedData, (d) => d.value)!]);

    g.append("g")
      .attr("class", "x-axis")
      .call(
        d3
          .axisTop(x)
          .ticks(5)
          .tickFormat((d) => `${d}min`)
      )
      .attr("transform", `translate(0,0)`);

    g.append("g").attr("class", "y-axis").call(d3.axisLeft(y));

    // Create tooltip element
    const tooltip = d3
      .select("body")
      .append("div")
      .attr("id", "tooltip-container") // Ensure only one tooltip exists
      .style("position", "absolute")
      .style("background", "#fff")
      .style("padding", "5px 10px")
      .style("border", "1px solid #ccc")
      .style("border-radius", "4px")
      .style("font-size", "12px")
      .style("pointer-events", "none")
      .style("display", "none");

    g.selectAll(".bar")
      .data(modifiedData)
      .enter()
      .append("rect")
      .attr("class", "bar")
      .attr("x", 0)
      .attr("y", (d) => y(d.category)!)
      .attr("width", (d) => x(d.value))
      .attr("height", y.bandwidth())
      .attr("fill", (d) => colorScale(d.value)) 
      .attr("rx", 8)
      .attr("ry", 8)
      .on("mouseover", (event, d) => {
        tooltip
          .style("display", "block")
          .html(`<strong>${d.fullCategoryText}</strong><br>Value: ${d.value}`);
      })
      .on("mousemove", (event) => {
        tooltip
          .style("left", `${event.pageX + 10}px`)
          .style("top", `${event.pageY - 20}px`);
      })
      .on("mouseout", () => {
        tooltip.style("display", "none");
      });

    if (yLabel) {
      svg
        .append("text")
        .attr(
          "transform",
          `translate(${margin.left - 60},${margin.top + height / 2})rotate(-90)`
        )
        .style("text-anchor", "middle")
        .style("font-size", "12px")
        .text(yLabel);
    }
  }, [data, title, yLabel, containerHeight]);

  return (
    <div style={{ height: "91%" }}>
      <svg ref={chartRef} style={{ overflowY: "auto" }} />
    </div>
  );
};

export default BarChart;
