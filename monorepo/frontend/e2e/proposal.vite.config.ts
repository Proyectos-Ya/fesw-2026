import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

/**
 * Monta `ProposalView` sola, sin Next ni sesión, para el e2e de la postulación.
 * La API se simula en el spec con `page.route`. Las dos piezas que dependen de
 * Next o de la sesión se reemplazan por dobles: el router (lo usa `BackLink`) y
 * el espacio de trabajo (lo usa `useCanWriteProposal`). Los alias específicos
 * van antes que "@" para ganarle.
 */
export default defineConfig({
  root: path.resolve(__dirname, "proposal-fixture"),
  plugins: [react()],
  resolve: {
    alias: [
      {
        find: "next/navigation",
        replacement: path.resolve(__dirname, "proposal-fixture/next-navigation.ts"),
      },
      {
        find: "@/features/workspaces/WorkspaceContext",
        replacement: path.resolve(__dirname, "proposal-fixture/workspace.ts"),
      },
      { find: "@", replacement: path.resolve(__dirname, "../src") },
    ],
  },
  server: { host: "127.0.0.1", port: 3108, strictPort: true },
});
