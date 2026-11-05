import { z } from "zod";

export const CapabilitiesSchema = z.object({
  enabled: z.boolean(),
  min_version: z.string(),
  latest_version: z.string(),
  mp_adapter_enabled: z.boolean(),
  fetch_jobs_enabled: z.boolean(),
  postulation_enabled: z.boolean(),
  max_daily_fetches: z.number(),
  polling_interval_seconds: z.number(),
  supported_mp_hosts: z.array(z.string()),
  message: z.string().nullable(),
});
export type Capabilities = z.infer<typeof CapabilitiesSchema>;

export const BridgePairingMessageSchema = z.object({
  target: z.literal("CHIRIPA_EXTENSION"),
  type: z.literal("PAIR_SESSION"),
  nonce: z.string().uuid(),
  payload: z.object({
    pairing_ticket: z.string(),
    api_url: z.string(),
    workspace_id: z.string().uuid().nullable().optional(),
    access_token: z.string(),
    refresh_token: z.string().optional(),
    timestamp: z.number(),
  }),
});
export type BridgePairingMessage = z.infer<typeof BridgePairingMessageSchema>;

export const MpDocumentItemSchema = z.object({
  mp_document_id: z.string(),
  name: z.string(),
  size_bytes: z.number().optional(),
  download_url: z.string().optional(),
});
export type MpDocumentItem = z.infer<typeof MpDocumentItemSchema>;

export const MpFichaDataSchema = z.object({
  tender_code: z.string(),
  call_number: z.union([z.literal(1), z.literal(2)]),
  first_call_closing_at: z.string().nullable().optional(),
  second_call_closing_at: z.string().nullable().optional(),
  documents: z.array(MpDocumentItemSchema),
});
export type MpFichaData = z.infer<typeof MpFichaDataSchema>;

export const ExtensionJobSchema = z.object({
  job_id: z.string().uuid(),
  tender_id: z.string().uuid(),
  tender_code: z.string(),
  lease_expires_at: z.string(),
});
export type ExtensionJob = z.infer<typeof ExtensionJobSchema>;

export const ExtensionJobResultSchema = z.object({
  installation_id: z.string().uuid(),
  status: z.enum(["completed", "failed", "skipped"]),
  error_code: z.string().nullable().optional(),
  error_detail: z.string().nullable().optional(),
  result_summary: z.record(z.string(), z.unknown()).nullable().optional(),
});
export type ExtensionJobResult = z.infer<typeof ExtensionJobResultSchema>;

// --- Postulación en Mercado Público (HU-032) ---

export const PostulationFileAttachmentSchema = z.object({
  name: z.string().min(1),
  type: z.string(),
  size: z.number().nonnegative(),
  data_base64: z.string(),
});
export type PostulationFileAttachment = z.infer<typeof PostulationFileAttachmentSchema>;

export const PostulationItemPayloadSchema = z.object({
  line_number: z.number().int().positive(),
  product_code: z.string().nullable().optional(),
  name: z.string().min(1),
  quantity: z.number().positive(),
  unit: z.string().optional(),
  unit_price: z.number().int().nonnegative(),
  total_price: z.number().int().nonnegative(),
  technical_spec: z.string().nullable().optional(),
});
export type PostulationItemPayload = z.infer<typeof PostulationItemPayloadSchema>;

export const PostulationPackagePayloadSchema = z.object({
  tender_code: z.string().min(1),
  tender_title: z.string().optional(),
  company_rut: z.string().min(1),
  company_name: z.string().min(1),
  contact_name: z.string().nullable().optional(),
  contact_email: z.string().nullable().optional(),
  contact_phone: z.string().nullable().optional(),
  items: z.array(PostulationItemPayloadSchema),
  total_clp: z.number().int().nonnegative(),
  observations: z.string().max(500).default(""),
  validity_days: z.number().int().positive().default(30),
  delivery_term_days: z.number().int().positive().default(15),
  shipping_clp: z.number().int().nonnegative().nullable().optional(),
  files: z.array(PostulationFileAttachmentSchema).default([]),
});
export type PostulationPackagePayload = z.infer<typeof PostulationPackagePayloadSchema>;

export const BridgeOpenPostulationMessageSchema = z.object({
  target: z.literal("CHIRIPA_EXTENSION"),
  type: z.literal("OPEN_POSTULATION"),
  nonce: z.string().uuid(),
  payload: z.object({
    tender_code: z.string().min(1),
    mp_url: z.string().url().optional(),
  }),
});
export type BridgeOpenPostulationMessage = z.infer<typeof BridgeOpenPostulationMessageSchema>;

export const BridgeConfirmPostulationMessageSchema = z.object({
  target: z.literal("CHIRIPA_EXTENSION"),
  type: z.literal("CONFIRM_POSTULATION"),
  nonce: z.string().uuid(),
  payload: PostulationPackagePayloadSchema,
});
export type BridgeConfirmPostulationMessage = z.infer<typeof BridgeConfirmPostulationMessageSchema>;

export const BridgeFocusTabMessageSchema = z.object({
  target: z.literal("CHIRIPA_EXTENSION"),
  type: z.literal("FOCUS_POSTULATION_TAB"),
  nonce: z.string().uuid(),
  payload: z.object({
    tender_code: z.string().min(1),
  }),
});
export type BridgeFocusTabMessage = z.infer<typeof BridgeFocusTabMessageSchema>;

