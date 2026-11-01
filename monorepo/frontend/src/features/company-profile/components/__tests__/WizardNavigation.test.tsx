import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WizardNavigation } from "../WizardNavigation";

function renderNavigation(props: { nextDisabled?: boolean; isLoading?: boolean } = {}) {
  const onNext = vi.fn();
  render(
    <WizardNavigation
      onBack={vi.fn()}
      onNext={onNext}
      isFirstStep={false}
      isLastStep={false}
      {...props}
    />,
  );
  return { onNext };
}

describe("WizardNavigation", () => {
  it("llama a onNext al apretar Siguiente", () => {
    const { onNext } = renderNavigation();

    fireEvent.click(screen.getByRole("button", { name: /Siguiente/ }));

    expect(onNext).toHaveBeenCalledTimes(1);
  });

  it("con nextDisabled el botón queda deshabilitado y no llama a onNext", () => {
    const { onNext } = renderNavigation({ nextDisabled: true });

    const next = screen.getByRole("button", { name: /Siguiente/ });
    fireEvent.click(next);

    expect(next).toBeDisabled();
    expect(onNext).not.toHaveBeenCalled();
  });

  it("sigue deshabilitado mientras carga aunque nextDisabled sea falso", () => {
    renderNavigation({ nextDisabled: false, isLoading: true });

    expect(screen.getByRole("button", { name: /Siguiente/ })).toBeDisabled();
  });
});
