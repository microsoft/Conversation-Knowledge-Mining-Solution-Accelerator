import React from "react";
import { Spinner, SpinnerSize, ISpinnerStyles } from "@fluentui/react";
import styles from "./CustomSpinner.module.css";

interface CustomSpinnerProps {
  loading: boolean;
  label?: string; // Label is optional
}

const spinnerStyles: ISpinnerStyles = {
  label: {
    fontSize: "20px",
    color: "rgb(91 184 255)",
    fontWeight: 600,
  },
};

const CustomSpinner: React.FC<CustomSpinnerProps> = ({ loading, label }) => {
  if (!loading) return null;

  return (
    <div className={styles.overlay}>
      <Spinner
        label={label || undefined}
        size={SpinnerSize.large}
        styles={spinnerStyles}
      />
    </div>
  );
};

export default CustomSpinner;
