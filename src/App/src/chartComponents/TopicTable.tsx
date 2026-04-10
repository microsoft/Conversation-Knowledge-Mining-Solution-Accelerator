import React from "react";
import {
  Table,
  TableHeader,
  TableRow,
  TableBody,
  TableCell,
  TableHeaderCell,
  TableCellLayout,
  Caption1,
  Body1Strong,
} from "@fluentui/react-components";
import { colors } from "../configs/Utils";

interface TopicTableProps {
  columns: string[];
  columnKeys: string[];
  rows: { [key: string]: string | number }[];
  containerHeight: number;
}

const TopicTable: React.FC<TopicTableProps> = ({
  columns,
  rows,
  columnKeys,
}) => {
  return (
    <div
      tabIndex={0}
      style={{
        ...tableStyles.container,
        height: "91%",
      }}
    >
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((column, index) => (
              <TableHeaderCell
                key={index}
                style={{
                  ...tableStyles.header,
                  position: "sticky",
                  top: 0,
                  backgroundColor: "#f4f4f4",
                  zIndex: 1, // Ensures header stays above content
                }}
              >
                <Body1Strong>{column}</Body1Strong>
              </TableHeaderCell>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody style={{ overflowY: "auto",  maxHeight: "calc(91% - 50px)", width: "100%" }}>
          {rows.map((row, index) => (
            <TableRow key={index}>
              {columnKeys.map((columnKey) => (
                <TableCell key={columnKey} style={tableStyles.cell}>
                  <TableCellLayout>
                    {columnKey === "average_sentiment" ? (
                      <div style={{ display: "flex", alignItems: "center", textTransform: "capitalize" }}>
                        <div
                          style={{
                            backgroundColor:
                              colors[row[columnKey] as string] || colors.default,
                            width: "20px",
                            height: "20px",
                            marginRight: "10px",
                            borderRadius: "4px",
                          }}
                        ></div>
                        <Caption1>{row[columnKey]}</Caption1>
                      </div>
                    ) : (
                      <Caption1>{row[columnKey]}</Caption1>
                    )}
                  </TableCellLayout>
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};

export default TopicTable;

const tableStyles: { [key: string]: React.CSSProperties } = {
  container: {
    overflowY: "auto",
    backgroundColor: "#fff",
    borderRadius: "2px",
    boxShadow: "0px 1px 5px rgba(0, 0, 0, 0.1)",
  },
  header: {
    backgroundColor: "#f4f4f4",
    fontWeight: "bold",
    textAlign: "left",
    padding: "2px",
    fontSize: "calc(0.6rem + 0.3vw)",
  },
  cell: {
    borderBottom: "1px solid #ddd",
    padding: "2px",
    textTransform: "capitalize",
    fontSize: "calc(0.5rem + 0.3vw)",
  },
};
