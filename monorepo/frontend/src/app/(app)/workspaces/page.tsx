import { Metadata } from "next";
import { WorkspaceSelectionScreen } from "@/features/workspaces/components/WorkspaceSelectionScreen";

export const metadata: Metadata = {
  title: "Espacios de trabajo | Chiripa",
  description: "Selecciona el espacio de trabajo con el que deseas operar en Chiripa.",
};

export default function WorkspacesPage() {
  return <WorkspaceSelectionScreen />;
}
