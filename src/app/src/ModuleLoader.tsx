import React from "react";
import uiConfig from "./config/ui-config.json";

interface ModuleLoaderProps {
  moduleName: string;
  children: React.ReactNode;
}

/**
 * Conditionally renders a module based on ui-config.json settings.
 * Usage: <ModuleLoader moduleName="chat"><ChatInterface /></ModuleLoader>
 */
const ModuleLoader: React.FC<ModuleLoaderProps> = ({ moduleName, children }) => {
  const modules = uiConfig.modules as Record<string, { enabled: boolean; label: string }>;
  const moduleConfig = modules[moduleName];

  if (!moduleConfig || !moduleConfig.enabled) {
    return null;
  }

  return <>{children}</>;
};

export default ModuleLoader;
