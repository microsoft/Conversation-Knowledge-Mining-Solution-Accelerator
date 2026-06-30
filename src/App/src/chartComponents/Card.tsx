import { Subtitle2 } from "@fluentui/react-components";
import React from "react";

interface CardProps {
  value: number | string;
  description: string;
  unit_of_measurement: string;
  containerHeight: number;
}

const Card: React.FC<CardProps> = ({
  value,
  description,
  unit_of_measurement,
  containerHeight,
}) => {
  if (unit_of_measurement === "") {
    value = value.toLocaleString("en-US");
  }
  return (
    <div>
      <Subtitle2>{`${value}${unit_of_measurement}`}</Subtitle2>
    </div>
  );
};

export default Card;
