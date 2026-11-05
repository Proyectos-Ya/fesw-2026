import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { chiripaTokensCss } from "../../ui/design-tokens";

const tokens = document.createElement("style");
tokens.textContent = `${chiripaTokensCss(":root")}
body { margin: 0; background: var(--ch-bg-page); font-family: var(--ch-font-sans); }`;
document.head.appendChild(tokens);

const rootEl = document.getElementById("root");
if (rootEl) {
  ReactDOM.createRoot(rootEl).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
