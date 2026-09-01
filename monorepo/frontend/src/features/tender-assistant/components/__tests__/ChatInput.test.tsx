import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ChatInput } from "../ChatInput";

describe("ChatInput", () => {
  it("muestra el contador de caracteres inicial 0 / 1000", () => {
    render(<ChatInput onSend={vi.fn()} isAsking={false} />);
    expect(screen.getByText("0 / 1000")).toBeInTheDocument();
  });

  it("actualiza el contador de caracteres al escribir", async () => {
    const user = userEvent.setup();
    render(<ChatInput onSend={vi.fn()} isAsking={false} />);

    const textarea = screen.getByPlaceholderText(/Haz una pregunta sobre esta licitación/i);
    await user.type(textarea, "¿Cuál es el plazo de entrega?");

    expect(screen.getByText("29 / 1000")).toBeInTheDocument();
  });

  it("deshabilita el botón de envío y muestra alerta si supera los 1000 caracteres", () => {
    render(<ChatInput onSend={vi.fn()} isAsking={false} />);

    const textarea = screen.getByPlaceholderText(/Haz una pregunta sobre esta licitación/i);
    const longText = "a".repeat(1001);
    fireEvent.change(textarea, { target: { value: longText } });

    expect(screen.getByText("1001 / 1000")).toBeInTheDocument();
    expect(
      screen.getByText(/La consulta supera los 1000 caracteres/i),
    ).toBeInTheDocument();

    const submitBtn = screen.getByRole("button", { name: /enviar/i });
    expect(submitBtn).toBeDisabled();
  });

  it("llama a onSend con la pregunta y limpia el campo al enviar", async () => {
    const onSendMock = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ChatInput onSend={onSendMock} isAsking={false} />);

    const textarea = screen.getByPlaceholderText(/Haz una pregunta sobre esta licitación/i);
    await user.type(textarea, "¿Dónde queda la obra?");

    const submitBtn = screen.getByRole("button", { name: /enviar/i });
    await user.click(submitBtn);

    expect(onSendMock).toHaveBeenCalledWith("¿Dónde queda la obra?");
    expect(textarea).toHaveValue("");
    expect(screen.getByText("0 / 1000")).toBeInTheDocument();
  });

  it("deshabilita el botón mientras isAsking es true", () => {
    render(<ChatInput onSend={vi.fn()} isAsking={true} />);

    const submitBtn = screen.getByRole("button", { name: /enviando/i });
    expect(submitBtn).toBeDisabled();
  });

  it("deshabilita el textarea y el botón cuando disabled es true", () => {
    render(<ChatInput onSend={vi.fn()} disabled={true} />);

    const textarea = screen.getByPlaceholderText(/Haz una pregunta sobre esta licitación/i);
    expect(textarea).toBeDisabled();

    const submitBtn = screen.getByRole("button", { name: /enviar/i });
    expect(submitBtn).toBeDisabled();
  });
});

