import React from "react";
import ReactDOM from "react-dom/client";
import { FluentProvider, webLightTheme } from "@fluentui/react-components";

import "./design-tokens.css";
import App from "./App";
import { initializeAuthentication } from "./auth/msalConfig";

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement
);

initializeAuthentication().then(() => {
  root.render(
    <React.StrictMode>
      <FluentProvider theme={webLightTheme}>
        <App />
      </FluentProvider>
    </React.StrictMode>
  );
}).catch((error: unknown) => {
  root.render(
    <div role="alert">
      Authentication setup failed: {error instanceof Error ? error.message : "Unable to initialize sign-in."}
    </div>
  );
});