import { useContext } from "react";
import { AppContext } from "./AppProvider";

export const useAppContext = () => {
  return useContext(AppContext);
};
