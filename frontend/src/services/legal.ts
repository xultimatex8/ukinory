import { apiUrl } from "../api";

export type LegalDocumentId = number | string;

export type LegalDocumentType = "TERMS" | "PRIVACY";

export interface LegalDocument {
  id: LegalDocumentId;
  type: LegalDocumentType;
  version: string;
  content: string;
  effective_at: string;
}

export async function getCurrentLegalDocuments(): Promise<LegalDocument[]> {
  const response = await fetch(apiUrl("/api/legal/documents/"));

  const result = await response.json();

  if (!response.ok) {
    throw result;
  }

  return result;
}