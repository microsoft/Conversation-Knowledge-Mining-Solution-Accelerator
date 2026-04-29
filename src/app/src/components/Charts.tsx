import React from "react";
import { Doughnut, Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
} from "chart.js";

import { COLORS } from "../utils/constants";

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement);

interface DonutChartProps {
  data: Array<{ label: string; value: number }>;
  title?: string;
  height?: number;
}

export const DonutChart: React.FC<DonutChartProps> = ({ data, title, height = 220 }) => {
  const chartData = {
    labels: data.map((d) => d.label),
    datasets: [
      {
        data: data.map((d) => d.value),
        backgroundColor: data.map((_, i) => COLORS[i % COLORS.length]),
        borderWidth: 0,
        hoverOffset: 4,
      },
    ],
  };

  return (
    <div style={{ height, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <Doughnut
        data={chartData}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          cutout: "60%",
          plugins: {
            legend: { position: "right", labels: { boxWidth: 10, padding: 12, font: { size: 11 } } },
            tooltip: { bodyFont: { size: 12 } },
          },
        }}
      />
    </div>
  );
};

interface BarChartProps {
  data: Array<{ label: string; value: number }>;
  title?: string;
  height?: number;
  horizontal?: boolean;
  color?: string;
}

export const BarChart: React.FC<BarChartProps> = ({ data, title, height = 200, horizontal = false, color = "#2563eb" }) => {
  const chartData = {
    labels: data.map((d) => d.label),
    datasets: [
      {
        data: data.map((d) => d.value),
        backgroundColor: color + "cc",
        borderColor: color,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.7,
      },
    ],
  };

  return (
    <div style={{ height }}>
      <Bar
        data={chartData}
        options={{
          indexAxis: horizontal ? "y" : "x",
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { bodyFont: { size: 12 } },
          },
          scales: {
            x: { grid: { display: false }, ticks: { font: { size: 10 } } },
            y: { grid: { color: "#f1f5f9" }, ticks: { font: { size: 10 } } },
          },
        }}
      />
    </div>
  );
};
