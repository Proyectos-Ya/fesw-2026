import type {
  AttachmentFile,
  DigestCitation,
  DigestDiscrepancy,
  OfficialAttachment,
  TenderAttachments,
  TenderDigest,
  TenderDigestData,
  UploadTicket,
} from "./types";

export function buildOfficialAttachment(
  overrides: Partial<OfficialAttachment> = {},
): OfficialAttachment {
  return {
    id: "a-1",
    mp_document_id: 1931002,
    name: "Anexo 3 Composición personalidad juridica.xlsx",
    name_normalized: "anexo 3 composicion personalidad juridica.xlsx",
    ext: "xlsx",
    status: "missing",
    processing: null,
    file: null,
    ...overrides,
  };
}

export function buildTenderAttachments(
  overrides: Partial<TenderAttachments> = {},
): TenderAttachments {
  return {
    official: [buildOfficialAttachment()],
    list_synced_at: "2026-09-28T16:28:00Z",
    quota: null,
    can_upload: false,
    max_upload_size_bytes: 52428800,
    processing_enabled: false,
    ...overrides,
  };
}

export function buildAttachmentFile(overrides: Partial<AttachmentFile> = {}): AttachmentFile {
  return {
    id: "f-1",
    size_bytes: 2048,
    source: "manual",
    visibility: "private",
    trust: "pending",
    status: "stored",
    status_reason: null,
    is_mine: true,
    created_at: "2026-10-03T15:00:00Z",
    ...overrides,
  };
}

export function buildUploadTicket(overrides: Partial<UploadTicket> = {}): UploadTicket {
  return {
    deduplicated: false,
    upload_id: "u-1",
    url: "https://almacen.test/put",
    method: "PUT",
    headers: {
      "x-amz-checksum-sha256": "siHZ27CDp/M0KNfCo8MZiuklYU1wIQ4ocWzKp81N23k=",
      "Content-Type": "application/pdf",
    },
    expires_at: "2026-10-03T15:15:00Z",
    ...overrides,
  };
}

export function buildDigestCitation(overrides: Partial<DigestCitation> = {}): DigestCitation {
  return {
    documento: "Bases.pdf",
    pagina_u_hoja: "Pág 4",
    cita: "El plazo de entrega es de 45 días corridos.",
    verificada: true,
    ...overrides,
  };
}

export function buildDigestDiscrepancy(
  overrides: Partial<DigestDiscrepancy> = {},
): DigestDiscrepancy {
  return {
    tipo: "anexo_vs_api",
    campo: "fecha_cierre_primer_llamado",
    tema: "Cierre del primer llamado",
    descripcion:
      "Mercado Público informa 04-10-2026 15:00 como cierre del primer llamado, pero «Bases.pdf» dice 05-10-2026 15:00.",
    campo_api: "first_call_closing_at",
    valor_api: "04-10-2026 15:00",
    valores_anexos: ["05-10-2026 15:00"],
    fuentes: [buildDigestCitation()],
    ...overrides,
  };
}

export function buildTenderDigest(
  overrides: Partial<TenderDigest> = {},
): TenderDigest & { data: TenderDigestData } {
  const citaBase = buildDigestCitation();
  return {
    id: "d-1",
    tender_id: "t-1",
    scope: "shared",
    version: 1,
    status: "ready",
    pending_sources: 0,
    created_at: "2026-10-04T12:00:00Z",
    data: {
      campos: {
        presupuesto: {
          valor: {
            monto_clp: 5000000,
            incluye_iva: true,
            monto_texto: "$5.000.000 (IVA incluido)",
          },
          en_conflicto: false,
          alternativas: [],
          citas: [citaBase],
        },
        fecha_publicacion: null,
        fecha_cierre_primer_llamado: {
          valor: { fecha: "2026-10-05", hora: "15:00" },
          en_conflicto: false,
          alternativas: [],
          citas: [citaBase],
        },
        fecha_cierre_segundo_llamado: null,
        visita_tecnica: null,
      },
      requisitos: [
        {
          descripcion: "Certificación ISO 9001 vigente",
          tipo: "técnico",
          obligatorio: true,
          citas: [citaBase],
        },
      ],
      items: [
        {
          descripcion: "Mantención de bombas",
          cantidad: 2,
          unidad: "unidades",
          citas: [citaBase],
        },
      ],
      entregables: [
        {
          descripcion: "Informe final de mantención",
          plazo: "10 días",
          citas: [citaBase],
        },
      ],
      puntos_a_tener_en_cuenta: [
        {
          descripcion: "Técnico residente con experiencia mínima de 3 años.",
          citas: [citaBase],
        },
      ],
      resumenes: [
        {
          anexo_id: "a-1",
          documento: "Bases.pdf",
          texto: "Resumen de las bases administrativas del proyecto.",
          citas: [citaBase],
        },
      ],
      otras_citas: [],
      discrepancias: [buildDigestDiscrepancy()],
      fuentes: [
        {
          anexo_id: "a-1",
          archivo_id: "f-1",
          documento: "Bases.pdf",
          visibilidad: "shared",
          citas_total: 14,
          citas_verificadas: 12,
          texto_disponible: true,
          modelo: "gemini-3.1-flash-lite",
          prompt_version: "anexos-v1",
          procesado_en: "2026-10-04T12:00:00Z",
        },
      ],
    },
    ...overrides,
  };
}
