import { describe, expect, it, vi } from "vitest";
import {
  INVALID_LOGO_ERROR_MESSAGE,
  MAX_COMPANY_LOGO_BYTES,
  uploadMySupplierLogo,
  validateCompanyLogoFile,
} from "../services/supplierService";
import { apiFetch } from "@/features/shared/api/client";

vi.mock("@/features/shared/api/client", () => ({
  apiFetch: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      message: string,
    ) {
      super(message);
    }
  },
  TimeoutError: class TimeoutError extends Error {},
}));

describe("Company Logo Validation & Upload Service", () => {
  it("acepta archivos PNG y JPEG válidos menores o iguales a 5MB", () => {
    const validPng = new File([new ArrayBuffer(1024)], "logo.png", {
      type: "image/png",
    });
    const validJpg = new File([new ArrayBuffer(1024)], "logo.jpg", {
      type: "image/jpeg",
    });

    expect(validateCompanyLogoFile(validPng)).toBeNull();
    expect(validateCompanyLogoFile(validJpg)).toBeNull();
  });

  it("rechaza archivos con peso mayor a 5MB", () => {
    const oversizedFile = new File(
      [new ArrayBuffer(MAX_COMPANY_LOGO_BYTES + 10)],
      "heavy.png",
      { type: "image/png" },
    );

    expect(validateCompanyLogoFile(oversizedFile)).toBe(
      INVALID_LOGO_ERROR_MESSAGE,
    );
  });

  it("rechaza tipos MIME no soportados (PDF, WebP, SVG, etc.)", () => {
    const pdfFile = new File([new ArrayBuffer(500)], "doc.pdf", {
      type: "application/pdf",
    });
    const webpFile = new File([new ArrayBuffer(500)], "image.webp", {
      type: "image/webp",
    });
    const svgFile = new File([new ArrayBuffer(500)], "vector.svg", {
      type: "image/svg+xml",
    });

    expect(validateCompanyLogoFile(pdfFile)).toBe(INVALID_LOGO_ERROR_MESSAGE);
    expect(validateCompanyLogoFile(webpFile)).toBe(INVALID_LOGO_ERROR_MESSAGE);
    expect(validateCompanyLogoFile(svgFile)).toBe(INVALID_LOGO_ERROR_MESSAGE);
  });

  it("uploadMySupplierLogo rechaza inmediatamente archivos inválidos antes de invocar la API", async () => {
    const invalidFile = new File([new ArrayBuffer(100)], "doc.pdf", {
      type: "application/pdf",
    });

    await expect(uploadMySupplierLogo(invalidFile)).rejects.toThrow(
      INVALID_LOGO_ERROR_MESSAGE,
    );
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("uploadMySupplierLogo envía FormData con el archivo a POST /suppliers/me/logo", async () => {
    const validFile = new File([new ArrayBuffer(2048)], "brand.png", {
      type: "image/png",
    });
    const mockSupplier = {
      id: "sup-123",
      user_id: "user-123",
      rut: "76.086.428-5",
      legal_name: "Empresa Test SpA",
      trade_name: "Test",
      logo_url: "/api/suppliers/sup-123/logo/abc1234567890123.png",
      created_at: "2026-10-29T00:00:00Z",
      updated_at: "2026-10-29T00:00:00Z",
    };

    vi.mocked(apiFetch).mockResolvedValueOnce(mockSupplier);

    const result = await uploadMySupplierLogo(validFile);

    expect(apiFetch).toHaveBeenCalledTimes(1);
    const [endpoint, options] = vi.mocked(apiFetch).mock.calls[0];
    expect(endpoint).toBe("/suppliers/me/logo");
    expect(options?.method).toBe("POST");
    expect(options?.body).toBeInstanceOf(FormData);
    expect(result).toEqual(mockSupplier);
  });
});
