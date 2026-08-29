import { describe, expect, it } from "vitest";
import { isValidRut, step1Schema } from "../profileSchema";

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
