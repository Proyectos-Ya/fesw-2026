import React from "react";
import { createRoot } from "react-dom/client";
import { ProposalView } from "../../src/features/proposals/components/ProposalView";
import "../../src/app/globals.css";

createRoot(document.getElementById("root")!).render(
  <main className="p-4 sm:p-8"><ProposalView tenderId="t-1" /></main>,
);
