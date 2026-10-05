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
