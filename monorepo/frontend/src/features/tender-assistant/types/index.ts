export type TenderChatRole = "user" | "assistant";

export type SupportedDocumentType = "pdf" | "xlsx" | "png";

export const MAX_ATTACHED_DOCUMENTS = 10;

export interface Citation {
  document_name: string;
  page_or_sheet: string | null;
  quote: string;
}

export interface DocumentDiscrepancy {
  topic: string;
  description: string;
  conflicting_sources: Citation[];
}

export interface TenderChatSession {
  id: string;
  tender_id: string;
  user_id: string;
  title: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TenderChatMessage {
  id: string;
  session_id?: string | null;
  tender_id: string;
  user_id: string;
  role: TenderChatRole;
  content: string;
  citations: Citation[];
  discrepancies?: DocumentDiscrepancy[];
  warnings?: string[];
  unbacked_aspects?: string[];
  has_sufficient_info?: boolean;
  created_at: string;
}

export interface TenderChatDocument {
  id: string;
  tender_id: string;
  file_name: string;
  file_type: SupportedDocumentType;
  file_size_bytes: number;
  created_at: string;
}

export interface AskQuestionRequest {
  question: string;
  session_id?: string | null;
}

export interface CreateChatSessionRequest {
  title?: string;
}
