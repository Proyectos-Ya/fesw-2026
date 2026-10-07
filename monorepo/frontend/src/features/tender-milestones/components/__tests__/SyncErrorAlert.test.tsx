import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SyncErrorAlert } from "../SyncErrorAlert";

describe("SyncErrorAlert", () => {
  it("avisa que la sincronización no pudo completarse y permite reintentar", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <SyncErrorAlert
        message="La sincronización no pudo completarse."
        reconnect={false}
        providerLabel="Google Calendar"
        onRetry={onRetry}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("La sincronización no pudo completarse.");
    await user.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("si hay que reconectar lo ofrece en vez de reintentar", () => {
    render(
      <SyncErrorAlert message="El acceso expiró." reconnect providerLabel="Google Calendar" onRetry={vi.fn()} />,
    );

    expect(screen.getByRole("button", { name: "Reconectar Google Calendar" })).toBeInTheDocument();
  });

  it("nombra al proveedor que hay que reconectar", () => {
    render(
      <SyncErrorAlert message="El acceso expiró." reconnect providerLabel="Outlook Calendar" onRetry={vi.fn()} />,
    );

    expect(screen.getByRole("button", { name: "Reconectar Outlook Calendar" })).toBeInTheDocument();
  });
});
