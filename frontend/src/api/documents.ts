import { http } from "./http";
import type { DocumentListResponse, DocumentSource, StoredDocument } from "./types";

// Mirrors backend: documents/types.py → DocumentType
export type DocumentType = "applicant" | "requirement";

// GET/POST /documents?type=…[&applicant_id=…]: one endpoint for every kind of document
function documentSource(type: DocumentType, applicantId?: string): DocumentSource {
  const params = { type, ...(applicantId ? { applicant_id: applicantId } : {}) };
  return {
    list: async () => (await http.get<DocumentListResponse>("/documents", { params })).data.documents,
    upload: async (file) => {
      const body = new FormData();
      body.append("file", file); // the backend's `file: UploadFile` parameter
      return (await http.post<StoredDocument>("/documents", body, { params })).data;
    },
  };
}

// One applicant's documents (ID, medical report…)
export const applicantDocuments = (applicantId: string) => documentSource("applicant", applicantId);

// The underwriting guidelines (company-wide). Uploading a file with the same name replaces it.
export const requirementDocuments = documentSource("requirement");
