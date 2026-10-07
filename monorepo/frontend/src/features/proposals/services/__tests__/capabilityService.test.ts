import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "@/features/shared/api/client";
import { addCapabilityEvidence } from "../capabilityService";

vi.mock("@/features/shared/api/client", () => ({ apiFetch: vi.fn() }));

const fetchMock = vi.mocked(apiFetch);

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue({});
});

describe("capabilityService", () => {
  it("agrega un proyecto que respalda un Sí de experiencia", async () => {
    await addCapabilityEvidence("q-viales", {
      title: "Repavimentación calle Prat",
      year: 2024,
      buyer: "Municipalidad de Pica",
      amount_clp: 12_000_000,
      description: null,
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/capabilities/questions/q-viales/evidence");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      title: "Repavimentación calle Prat",
      year: 2024,
      buyer: "Municipalidad de Pica",
      amount_clp: 12_000_000,
      description: null,
    });
  });
});
