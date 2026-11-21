import { http } from "./http";
import type { ApplicationDocument, DocumentListResponse } from "./types";

export async function listDocuments(applicationId: string): Promise<ApplicationDocument[]> {
  const { data } = await http.get<DocumentListResponse>(`/applications/${applicationId}/documents`);
  return data.documents;
}

export async function uploadDocument(applicationId: string, file: File): Promise<ApplicationDocument> {
  const body = new FormData();
  body.append("file", file); // the backend's `file: UploadFile` parameter
  const { data } = await http.post<ApplicationDocument>(
    `/applications/${applicationId}/documents`,
    body,
  );
  return data;
}
