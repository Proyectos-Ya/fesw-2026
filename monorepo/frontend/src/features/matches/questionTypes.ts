export interface Question {
  id: string;
  provider_id: string;
  discrepancy_type: string | null;
  tender_requirement: string | null;
  question: string;
  target_profile_field: string;
  answered: boolean;
  answer: string | null;
  omitted: boolean;
  generated_at: string;
  answered_at: string | null;
  target_category: string;
  options: string[];
}
