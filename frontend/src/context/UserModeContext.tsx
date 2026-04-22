import React, { createContext, useContext, useState, useCallback } from "react";

export type UserMode = "basic" | "power" | "advanced";

interface UserModeContextType {
  mode: UserMode;
  setMode: (mode: UserMode) => void;
  isAtLeast: (minMode: UserMode) => boolean;
}

const hierarchy: Record<UserMode, number> = { basic: 0, power: 1, advanced: 2 };

const UserModeContext = createContext<UserModeContextType>({
  mode: "basic",
  setMode: () => {},
  isAtLeast: () => false,
});

export const UserModeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mode, setMode] = useState<UserMode>(
    (localStorage.getItem("user_mode") as UserMode) || "basic"
  );

  const handleSetMode = useCallback((m: UserMode) => {
    setMode(m);
    localStorage.setItem("user_mode", m);
  }, []);

  const isAtLeast = useCallback(
    (minMode: UserMode) => hierarchy[mode] >= hierarchy[minMode],
    [mode]
  );

  return (
    <UserModeContext.Provider value={{ mode, setMode: handleSetMode, isAtLeast }}>
      {children}
    </UserModeContext.Provider>
  );
};

export const useUserMode = () => useContext(UserModeContext);
