import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as bridge from "@/features/shared/extension/extensionBridge";
import { ExtensionPairingSection } from "../ExtensionPairingSection";

vi.mock("@/features/shared/extension/extensionBridge");

const SUPPLIER = "7d0c1f5e-0f52-4a2e-9f3b-7a1d3a1b2c3d";

describe("ExtensionPairingSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("muestra «no detectada» si la extensión no responde", async () => {
    vi.mocked(bridge.probeExtension).mockResolvedValue({ installed: false });
    render(<ExtensionPairingSection supplierId={SUPPLIER} />);
    expect(await screen.findByText(/No detectamos la extensión/i)).toBeInTheDocument();
  });

  it("muestra el estado real: vinculada, con opción de re-vincular", async () => {
    vi.mocked(bridge.probeExtension).mockResolvedValue({ installed: true, paired: true });
    render(<ExtensionPairingSection supplierId={SUPPLIER} />);
    expect(await screen.findByText(/Extensión vinculada/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Re-vincular" })).toBeInTheDocument();
  });

  it("solo dice vinculada cuando la extensión confirma", async () => {
    vi.mocked(bridge.probeExtension).mockResolvedValue({ installed: true, paired: false });
    vi.mocked(bridge.pairExtension).mockResolvedValue({ ok: true });
    render(<ExtensionPairingSection supplierId={SUPPLIER} />);

    fireEvent.click(await screen.findByRole("button", { name: "Vincular en este navegador" }));

    expect(await screen.findByText(/Extensión vinculada/i)).toBeInTheDocument();
    expect(bridge.pairExtension).toHaveBeenCalledWith(expect.objectContaining({ workspaceId: SUPPLIER }));
  });

  it("si la extensión no confirma, muestra error y no dice vinculada", async () => {
    vi.mocked(bridge.probeExtension).mockResolvedValue({ installed: true, paired: false });
    vi.mocked(bridge.pairExtension).mockResolvedValue({ ok: false, error: "La extensión no confirmó la vinculación." });
    render(<ExtensionPairingSection supplierId={SUPPLIER} />);

    fireEvent.click(await screen.findByRole("button", { name: "Vincular en este navegador" }));

    expect(await screen.findByText("La extensión no confirmó la vinculación.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/Extensión vinculada/i)).not.toBeInTheDocument());
  });
});
