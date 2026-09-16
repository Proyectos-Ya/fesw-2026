import React from "react";
import { createRoot } from "react-dom/client";
import { QuotationEditor } from "../../src/features/quotations/QuotationEditor";
import "../../src/app/globals.css";

createRoot(document.getElementById("root")!).render(
  <main className="mx-auto max-w-4xl p-4"><QuotationEditor tenderId="22700000-0000-4000-8000-000000000001" tenderCode="227-15-COT26" /></main>,
);
