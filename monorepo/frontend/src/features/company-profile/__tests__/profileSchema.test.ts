import { describe, expect, it } from "vitest";
import {
  certificationName,
  formatCertificationDate,
  formatRut,
  isValidRut,
  normalizeCertification,
  step1Schema,
  step3Schema,
} from "../profileSchema";

describe("formatRut", () => {
  it("devuelve vacío para una entrada vacía", () => {
    expect(formatRut("")).toBe("");
  });

  it("deja un solo carácter tal cual", () => {
    expect(formatRut("7")).toBe("7");
  });

  it("separa el dígito verificador con guion desde el segundo carácter", () => {
    expect(formatRut("76")).toBe("7-6");
    expect(formatRut("7612")).toBe("761-2");
  });

  it("agrega puntos de miles al cuerpo", () => {
    expect(formatRut("7654321")).toBe("765.432-1");
    expect(formatRut("76123456")).toBe("7.612.345-6");
    expect(formatRut("761234560")).toBe("76.123.456-0");
  });

  it("es idempotente con un RUT ya formateado", () => {
    expect(formatRut("76.123.456-0")).toBe("76.123.456-0");
  });

  it("reformatea un RUT escrito sin puntos", () => {
    expect(formatRut("76123456-0")).toBe("76.123.456-0");
  });

  it("pone la K del dígito verificador en mayúscula", () => {
    expect(formatRut("20347878k")).toBe("20.347.878-K");
  });

  it("descarta una K que no está al final", () => {
    expect(formatRut("76k1234560")).toBe("76.123.456-0");
  });

  it("descarta caracteres que no son dígitos", () => {
    expect(formatRut("76-12a3.456 0")).toBe("76.123.456-0");
  });

  it("no pasa de 8 dígitos de cuerpo más el verificador", () => {
    expect(formatRut("7612345601")).toBe("76.123.456-0");
  });
});

describe("isValidRut", () => {
  it("acepta un RUT con puntos y dígito verificador correcto", () => {
    expect(isValidRut("12.345.678-5")).toBe(true);
  });

  it("acepta un RUT sin puntos y dígito verificador correcto", () => {
    expect(isValidRut("12345678-5")).toBe(true);
  });

  it("acepta dígito verificador K en mayúscula o minúscula", () => {
    expect(isValidRut("20.347.878-K")).toBe(true);
    expect(isValidRut("20.347.878-k")).toBe(true);
  });

  it("rechaza un RUT con dígito verificador incorrecto", () => {
    expect(isValidRut("12.345.678-9")).toBe(false);
  });

  it("rechaza cadenas sin formato de RUT", () => {
    expect(isValidRut("")).toBe(false);
    expect(isValidRut("abc")).toBe(false);
    expect(isValidRut("12.345.678")).toBe(false);
  });
});

describe("step1Schema (rut)", () => {
  const base = { legal_name: "Constructora Pérez Ltda." };

  it("acepta un RUT válido", () => {
    const result = step1Schema.safeParse({ ...base, rut: "76.123.456-0" });
    expect(result.success).toBe(true);
  });

  it("rechaza un RUT con formato válido pero dígito verificador incorrecto", () => {
    const result = step1Schema.safeParse({ ...base, rut: "76.123.456-7" });
    expect(result.success).toBe(false);
  });

  it("rechaza un RUT con formato inválido", () => {
    const result = step1Schema.safeParse({ ...base, rut: "76123456" });
    expect(result.success).toBe(false);
  });
});

describe("step3Schema (certifications)", () => {
  const base = {
    sectors: ["Construcción"],
    keywords: [],
    description: "Constructora especializada en obras civiles menores.",
  };

  it("acepta certificaciones como strings", () => {
    const result = step3Schema.safeParse({ ...base, certifications: ["ISO 9001"] });
    expect(result.success).toBe(true);
  });

  it("acepta certificaciones como objeto con fecha de vencimiento", () => {
    const result = step3Schema.safeParse({
      ...base,
      certifications: [{ name: "ISO 9001", expires_at: "2026-12-31" }],
    });
    expect(result.success).toBe(true);
  });

  it("acepta un objeto sin fecha o con fecha nula", () => {
    const result = step3Schema.safeParse({
      ...base,
      certifications: [{ name: "ISO 9001" }, { name: "SEC", expires_at: null }],
    });
    expect(result.success).toBe(true);
  });

  it("acepta strings y objetos mezclados", () => {
    const result = step3Schema.safeParse({
      ...base,
      certifications: ["SEC", { name: "ISO 9001", expires_at: "2026-12-31" }],
    });
    expect(result.success).toBe(true);
  });

  it("rechaza un objeto con nombre vacío", () => {
    const result = step3Schema.safeParse({
      ...base,
      certifications: [{ name: "  " }],
    });
    expect(result.success).toBe(false);
  });

  it("rechaza una fecha que no es YYYY-MM-DD", () => {
    const result = step3Schema.safeParse({
      ...base,
      certifications: [{ name: "ISO 9001", expires_at: "31/12/2026" }],
    });
    expect(result.success).toBe(false);
  });

  it("rechaza elementos que no son string ni objeto", () => {
    const result = step3Schema.safeParse({ ...base, certifications: [42] });
    expect(result.success).toBe(false);
  });
});

describe("helpers de certificación", () => {
  it("normalizeCertification convierte un string en objeto sin fecha", () => {
    expect(normalizeCertification("ISO 9001")).toEqual({ name: "ISO 9001", expires_at: null });
  });

  it("normalizeCertification conserva un objeto con fecha", () => {
    expect(normalizeCertification({ name: "ISO 9001", expires_at: "2026-12-31" })).toEqual({
      name: "ISO 9001",
      expires_at: "2026-12-31",
    });
  });

  it("normalizeCertification pone null cuando falta la fecha", () => {
    expect(normalizeCertification({ name: "SEC" })).toEqual({ name: "SEC", expires_at: null });
  });

  it("certificationName devuelve el nombre de ambos formatos", () => {
    expect(certificationName("ISO 9001")).toBe("ISO 9001");
    expect(certificationName({ name: "SEC", expires_at: "2026-12-31" })).toBe("SEC");
  });

  it("formatCertificationDate entrega DD/MM/AAAA", () => {
    expect(formatCertificationDate("2026-12-31")).toBe("31/12/2026");
  });

  it("formatCertificationDate acepta un datetime ISO", () => {
    expect(formatCertificationDate("2026-03-05T00:00:00Z")).toBe("05/03/2026");
  });

  it("formatCertificationDate devuelve el texto original si no reconoce el formato", () => {
    expect(formatCertificationDate("pronto")).toBe("pronto");
  });
});
