import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SearchPagination } from "../SearchPagination";

describe("SearchPagination", () => {
  it("no renderiza nada si solo hay 1 página", () => {
    const { container } = render(
      <SearchPagination
        page={1}
        total={15}
        pageSize={20}
        onPageChange={vi.fn()}
      />,
    );

    expect(container.firstChild).toBeNull();
  });

  it("renderiza controles de paginación y navega a la siguiente página", () => {
    const handlePageChange = vi.fn();
    render(
      <SearchPagination
        page={1}
        total={45}
        pageSize={20}
        onPageChange={handlePageChange}
      />,
    );

    expect(screen.getByText(/Página/)).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument(); // 45 / 20 = 3 pages

    const prevButton = screen.getByRole("button", { name: /anterior/i });
    const nextButton = screen.getByRole("button", { name: /siguiente/i });

    expect(prevButton).toBeDisabled();
    expect(nextButton).not.toBeDisabled();

    fireEvent.click(nextButton);
    expect(handlePageChange).toHaveBeenCalledWith(2);
  });

  it("deshabilita el botón siguiente en la última página", () => {
    render(
      <SearchPagination
        page={3}
        total={45}
        pageSize={20}
        onPageChange={vi.fn()}
      />,
    );

    const nextButton = screen.getByRole("button", { name: /siguiente/i });
    expect(nextButton).toBeDisabled();
  });
});
